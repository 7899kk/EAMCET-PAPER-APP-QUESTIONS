import io,json,subprocess,pathlib
import pytest,pymupdf as f,pikepdf
from PIL import Image
from fastapi.testclient import TestClient
from backend.app import app,sessions
from backend import content,engine
from tests.test_engine import fixture

@pytest.fixture
def client():
 with TestClient(app) as c: yield c
 sessions.clear()

def upload(c,data=None):
 r=c.post('/api/documents',files={'file':('test.pdf',data or fixture(),'application/pdf')}); assert r.status_code==200,r.text
 return r.json(),{'X-Session':r.json()['token']}

def test_http_full_roundtrip(client):
 c=client;info,h=upload(c)
 assert c.get('/api/document/pdf',headers=h).content.startswith(b'%PDF')
 spans=c.get('/api/document/page/0/text',headers=h).json()['spans']; s=spans[0]; assert s['editable']
 for op,args in [('replace',{'id':s['id'],'text':'Verified contract'}),('text',{'text':'Added through API','x':72,'y':150}),('pages',{'indices':[0,2]}),('rotate',{'page':1})]:
  r=c.post('/api/document/operation',headers=h,json={'operation':op,'args':args}); assert r.status_code==200,r.text
 assert c.post('/api/document/history/undo',headers=h).json()['pages'][1]['rotation']==0
 assert c.post('/api/document/history/redo',headers=h).json()['pages'][1]['rotation']==90
 r=c.post('/api/document/export',headers=h,json={'kind':'pdf'}); assert r.status_code==200
 output=pathlib.Path(__file__).parent/'artifacts'/'api-downloaded.pdf'; output.write_bytes(r.content)
 with f.open(stream=r.content,filetype='pdf') as doc:
  assert len(doc)==2 and doc[1].rotation==90
  assert 'Verified contract' in doc[0].get_text() and 'Added through API' in doc[0].get_text()
  assert 'Original contract' not in doc[0].get_text()
 independent=subprocess.check_output(['pdftotext',str(output),'-'],text=True)
 assert 'Verified contract' in independent and 'Original contract' not in independent
 assert c.get('/api/document/search?q=Verified',headers=h).json()['results'][0]['page']==0
 assert c.get('/api/document/page/0/thumbnail',headers=h).content.startswith(b'\x89PNG')
 assert c.delete('/api/document',headers=h).status_code==200
 assert c.get('/api/document',headers=h).status_code==404

def test_invalid_and_security(client):
 c=client
 assert c.post('/api/documents',files={'file':('fake.pdf',b'not a pdf')}).status_code==422
 assert c.post('/api/documents',headers={'Origin':'https://evil.invalid'},files={'file':('test.pdf',fixture())}).status_code==403
 _,h=upload(c)
 assert c.post('/api/document/operation',headers=h,json={'operation':'pages','args':{'indices':[]}}).status_code==422
 assert c.post('/api/document/operation',headers=h,json={'operation':'imaginary'}).status_code==422
 assert c.get('/api/document',headers={'X-Session':'bad'}).status_code==404
 assert c.get('/api/document',headers=h).headers['cache-control']=='no-store'

@pytest.mark.parametrize('op,args',[
 ('text',{'text':'new text','x':40,'y':180}),('stamp',{'text':'APPROVED','x':40,'y':220}),
 ('rectangle',{'rect':[40,200,180,260]}),('line',{'rect':[40,200,180,260]}),
 ('highlight',{'rect':[70,80,210,105],'color':'#ffff00'}),('comment',{'text':'Review this','x':50,'y':50}),
 ('crop',{'rect':[20,20,550,800]}),('numbers',{}),('watermark',{'text':'DRAFT'}),
 ('metadata',{'metadata':{'title':'Test title','author':'Local user'}}),('compress',{}),
 ('find-replace',{'find':'Original','replacement':'Revised'})])
def test_each_api_operation(client,op,args):
 c=client;original=fixture();_,h=upload(c,original)
 before=c.get('/api/document/pdf',headers=h).content
 r=c.post('/api/document/operation',headers=h,json={'operation':op,'args':args}); assert r.status_code==200,r.text
 data=c.get('/api/document/pdf',headers=h).content; assert data!=before
 with f.open(stream=data,filetype='pdf') as doc:
  p=doc[0]
  if op in ('text','stamp'): assert args['text'] in p.get_text()
  elif op in ('rectangle','line'): assert p.get_drawings()
  elif op in ('highlight','comment'): assert list(p.annots())
  elif op=='crop': assert p.rect.width==530
  elif op=='numbers': assert '1' in p.get_text()
  elif op=='watermark': assert 'DRAFT' in p.get_text()
  elif op=='metadata': assert doc.metadata['title']=='Test title'
  elif op=='find-replace': assert 'Revised contract' in p.get_text() and 'Original' not in p.get_text()

def test_file_ops_and_conversion(client):
 c=client;_,h=upload(c)
 for operation in ['merge','insert']:
  r=c.post('/api/document/file-operation',headers=h,data={'operation':operation,'args':json.dumps({'at':1})},files={'file':('other.pdf',fixture())}); assert r.status_code==200,r.text
 assert len(r.json()['pages'])==9
 im=Image.new('RGB',(200,100),'red');buf=io.BytesIO();im.save(buf,'PNG'); image=buf.getvalue()
 r=c.post('/api/document/file-operation',headers=h,data={'operation':'image','args':json.dumps({'rect':[50,50,250,150]})},files={'file':('image.png',image)});assert r.status_code==200,r.text
 for kind in ['pdf','text','images','split','extract','extract-images','protect']:
  r=c.post('/api/document/export',headers=h,json={'kind':kind,'args':{'indices':[0],'password':'test1234'}});assert r.status_code==200,r.text
  assert len(r.content)>10
  if kind=='protect':
   bad=c.post('/api/documents',data={'password':'wrong'},files={'file':('locked.pdf',r.content)});assert bad.status_code==422
   good=c.post('/api/documents',data={'password':'test1234'},files={'file':('locked.pdf',r.content)});assert good.status_code==200
 r=c.post('/api/images-to-pdf',files=[('files',('one.png',image)),('files',('two.png',image))]); assert r.status_code==200,r.text;assert len(r.json()['pages'])==2

def test_embedded_unicode_font():
 d=f.open();p=d.new_page();p.insert_font(fontname='custom',fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf');p.insert_text((40,80),'Embedded font sample',fontname='custom',fontsize=17);data=d.tobytes();span=content.inspect(data,0)[0];assert span['editable']
 result=content.replace(data,0,span['id'],'Embedded sample font')
 with f.open(stream=result,filetype='pdf') as out: assert out[0].get_text().strip()=='Embedded sample font'

def test_preserves_following_text_position():
 d=f.open();p=d.new_page();p.insert_text((40,80),'Original',fontsize=16)
 with pikepdf.open(io.BytesIO(d.tobytes())) as pdf:
  stream=b'BT /helv 16 Tf 1 0 0 1 40 760 Tm (Original) Tj 0 1 0 rg (Following) Tj ET'
  pdf.pages[0].Contents=pdf.make_stream(stream);buf=io.BytesIO();pdf.save(buf);data=buf.getvalue()
 spans=content.inspect(data,0); original=next(s for s in spans if s['text']=='Original'); following=next(s for s in spans if s['text']=='Following')
 assert original['editable']
 edited=content.replace(data,0,original['id'],'A much longer replacement',21,'#223355')
 after=next(s for s in content.inspect(edited,0) if s['text']=='Following')
 assert after['bbox']==pytest.approx(following['bbox'],abs=.02)
 assert after['color']==following['color']
 with pikepdf.open(io.BytesIO(edited)) as pdf:
  stream=pdf.pages[0].Contents.read_bytes()
  assert b'Original' not in stream
  assert b're' not in stream.split() # No rectangle operator.

def test_active_content_removed():
 with pikepdf.open(io.BytesIO(fixture())) as pdf:
  pdf.Root.OpenAction=pikepdf.Dictionary(S=pikepdf.Name('/JavaScript'),JS=pikepdf.String('app.alert(1)'))
  buf=io.BytesIO();pdf.save(buf)
 cleaned=engine.validate(buf.getvalue())
 with pikepdf.open(io.BytesIO(cleaned)) as pdf: assert '/OpenAction' not in pdf.Root

def test_built_frontend_assets(client):
 import re
 c=client; response=c.get('/'); assert response.status_code==200;assert '<title>Folio' in response.text
 scripts=re.findall(r'(?:src|href)="(/assets/[^"]+)"',response.text)
 assert scripts
 for path in scripts:
  r=c.get(path);assert r.status_code==200 and len(r.content)>100
 assert c.get('/pdfjs/standard_fonts/LICENSE_LIBERATION').status_code==200
 assert c.get('/pdfjs/cmaps/LICENSE').status_code==200
 assert c.get('/pdfjs/wasm/LICENSE_QCMS').status_code==200

def test_hosted_preview_auth_and_origin(client,monkeypatch):
 c=client
 monkeypatch.setenv('FOLIO_PREVIEW_PASSWORD','unit-test-only')
 monkeypatch.setenv('RENDER_EXTERNAL_URL','https://folio-test.example')
 assert c.get('/').status_code==401
 assert c.get('/api/health').status_code==200
 assert c.post('/api/documents',files={'file':('test.pdf',fixture())}).status_code==401
 auth=('folio','unit-test-only')
 assert c.get('/',auth=auth).status_code==200
 assert c.get('/',auth=('folio','wrong')).status_code==401
 good=c.post('/api/documents',auth=auth,headers={'Origin':'https://folio-test.example'},files={'file':('test.pdf',fixture())})
 assert good.status_code==200,good.text
 blocked=c.post('/api/documents',auth=auth,headers={'Origin':'https://other.example'},files={'file':('test.pdf',fixture())})
 assert blocked.status_code==403

def test_source_archive_excludes_local_documents_and_secrets(tmp_path):
 from scripts.package_source import package
 root=tmp_path/'app'; root.mkdir()
 for name in ['backend','frontend','tests','docs']: (root/name).mkdir()
 (root/'backend'/'app.py').write_text('source')
 (root/'Dockerfile').write_text('FROM python')
 (root/'.dockerignore').write_text('.env')
 (root/'.env').write_text('secret')
 (root/'private.pdf').write_text('private')
 (root/'tests'/'artifacts').mkdir();(root/'tests'/'artifacts'/'user.pdf').write_text('private')
 (root/'frontend'/'node_modules').mkdir();(root/'frontend'/'node_modules'/'dependency.js').write_text('generated')
 dest=tmp_path/'source.zip'; package(root,dest)
 import zipfile
 with zipfile.ZipFile(dest) as archive:
  names=set(archive.namelist()); assert 'pdf-studio/backend/app.py' in names and 'pdf-studio/Dockerfile' in names
  assert not any('.env' in n or '.pdf' in n or 'node_modules' in n for n in names)
