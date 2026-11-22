import io
import pytest,pymupdf as fitz,pikepdf
from fastapi.testclient import TestClient
from backend import metadata,engine,layers
from backend.app import app

def source():
 with fitz.open() as doc:
  for i in range(2):
   p=doc.new_page();p.insert_text((50,80),'Metadata comparison sample - page '+str(i+1),fontsize=18);p.draw_rect((50,150,220,230),color=(.2,.5,.3),fill=(.8,.9,.8))
  a=doc[0].add_text_annot((300,160),'Preserved comment');a.set_info(title='Sample reviewer');a.update()
  doc.set_metadata({'title':'Original title','author':'Original author','subject':'Original subject','keywords':'original, metadata','creator':'Original creator','producer':'Original producer','creationDate':'D:20240102120000Z','modDate':'D:20240103130000Z'})
  data=doc.tobytes()
 with pikepdf.open(io.BytesIO(data)) as pdf:
  pdf.docinfo['/CustomNote']='SAMPLE_CUSTOM_METADATA'
  with pdf.open_metadata(set_pikepdf_as_editor=False,update_docinfo=False) as xmp:
   xmp['dc:title']='Original XMP title';xmp['dc:creator']=['Original XMP author'];xmp['dc:description']='Original XMP subject';xmp['pdf:Keywords']='original XMP keywords';xmp['xmp:CreatorTool']='Original XMP creator';xmp['pdf:Producer']='Original XMP producer'
  out=io.BytesIO();pdf.save(out);return out.getvalue()

VALUES={'title':'Metadata comparison - edited','author':'Edit karo test','subject':'Verified PDF metadata','keywords':'pdf, metadata, comparison','creator':'Metadata comparison tool','producer':'PDF metadata test','creationDate':'2024-01-02T12:00:00Z','modDate':'2024-01-03T13:00:00Z'}

def assert_pages_equal(before,after):
 with fitz.open(stream=before,filetype='pdf') as a,fitz.open(stream=after,filetype='pdf') as b:
  assert len(a)==len(b)
  for old,new in zip(a,b):
   assert old.get_text()==new.get_text()
   assert old.get_pixmap().samples==new.get_pixmap().samples

def test_standard_edit_synchronizes_info_xmp_custom_and_preserves_pages():
 data=source();result=engine.apply(data,'metadata',{'metadata':VALUES,'custom':{'Department':'Creative'}})
 assert metadata.inspect(result)['fields']==VALUES
 with pikepdf.open(io.BytesIO(result)) as p:
  xmp=p.open_metadata(set_pikepdf_as_editor=False);assert str(xmp['dc:title'])==VALUES['title'];assert list(xmp['dc:creator'])==[VALUES['author']]
  assert str(xmp['pdf:Producer'])==VALUES['producer'] and str(p.docinfo['/Department'])=='Creative'
  assert '/CustomNote' not in p.docinfo
 assert_pages_equal(data,result)

def test_clear_removes_info_and_all_xmp_but_preserves_layers_comments_and_pixels():
 data=layers.add(source(),0,{'type':'text','text':'Editable object stays','rect':[50,300,350,350],'font':'helv','size':16})
 with pikepdf.open(io.BytesIO(data)) as p:
  p.pages[0].obj.Metadata=p.make_stream(b'PAGE_LEVEL_METADATA');p.pages[0].obj.Metadata.Type=pikepdf.Name.Metadata;p.pages[0].obj.Metadata.Subtype=pikepdf.Name.XML
  out=io.BytesIO();p.save(out);data=out.getvalue()
 assert metadata.inspect(data)['xmp_packets']==2
 cleared=engine.apply(data,'clear-metadata',{})
 view=metadata.inspect(cleared);assert not any(view['fields'].values()) and view['custom']=={} and view['xmp_packets']==0
 with pikepdf.open(io.BytesIO(cleared)) as p:
  assert '/Info' not in p.trailer and '/Metadata' not in p.Root
  assert all('/Metadata' not in obj for obj in p.objects if isinstance(obj,(pikepdf.Dictionary,pikepdf.Stream)))
  assert not any(b'PAGE_LEVEL_METADATA' in obj.read_bytes() for obj in p.objects if isinstance(obj,pikepdf.Stream))
 assert layers.inspect_layers(cleared,0)==layers.inspect_layers(data,0)
 with fitz.open(stream=cleared,filetype='pdf') as d:assert next(d[0].annots()).info['title']=='Sample reviewer'
 assert_pages_equal(data,cleared)

def test_metadata_api_export_clear_undo_redo():
 with TestClient(app) as c:
  r=c.post('/api/documents',files={'file':('metadata.pdf',source())});h={'X-Session':r.json()['token']}
  assert c.get('/api/document/metadata',headers=h).json()['fields']['title']=='Original title'
  assert c.post('/api/document/operation',headers=h,json={'operation':'metadata','args':{'metadata':VALUES,'custom':{'Department':'Creative'}}}).status_code==200
  assert c.post('/api/document/operation',headers=h,json={'operation':'clear-metadata','args':{}}).status_code==200
  data=c.post('/api/document/export',headers=h,json={'kind':'pdf'}).content
  assert not any(metadata.inspect(data)['fields'].values())
  assert c.post('/api/document/history/undo',headers=h).status_code==200
  assert c.get('/api/document/metadata',headers=h).json()['fields']['title']==VALUES['title']
  assert c.post('/api/document/history/redo',headers=h).status_code==200
  assert c.get('/api/document/metadata',headers=h).json()['custom']=={}

@pytest.mark.parametrize('args',[{'metadata':{'creationDate':'not a date'}},{'metadata':{'title':'a'*2001}},{'metadata':{'author':'bad\x00value'}},{'metadata':{},'custom':{'Title':'not custom'}},{'metadata':{},'custom':{'bad/name':'invalid'}}])
def test_invalid_metadata_does_not_commit(args):
 with TestClient(app) as c:
  r=c.post('/api/documents',files={'file':('metadata.pdf',source())});h={'X-Session':r.json()['token']}
  before=c.get('/api/document/pdf',headers=h).content
  r=c.post('/api/document/operation',headers=h,json={'operation':'metadata','args':args});assert r.status_code==422,r.text
  assert c.get('/api/document/pdf',headers=h).content==before


def test_xmp_only_metadata_is_visible_editable_and_clearable():
 with pikepdf.open(io.BytesIO(source())) as pdf:
  del pdf.trailer['/Info'];output=io.BytesIO();pdf.save(output);data=output.getvalue()
 fields=metadata.inspect(data)['fields'];assert fields['title']=='Original XMP title' and fields['author']=='Original XMP author'
 edited=metadata.edit(data,{'title':'Updated XMP-only PDF'})
 assert metadata.inspect(edited)['fields']['title']=='Updated XMP-only PDF'
 assert not any(metadata.inspect(metadata.clear(edited))['fields'].values())
