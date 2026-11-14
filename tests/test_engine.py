import io
import pymupdf as f
from backend import engine,content

def fixture():
 d=f.open()
 for text in ['Original contract','Delete this page','Rotate this page']:
  p=d.new_page(); p.insert_text((72,100),text,fontsize=16)
 return d.tobytes()

def test_genuine_content_replacement():
 data=fixture(); spans=content.inspect(data,0); assert spans[0]['editable']
 out=content.replace(data,0,spans[0]['id'],'Revised contract',18,'#112233')
 with f.open(stream=out,filetype='pdf') as d:
  assert 'Revised contract' in d[0].get_text(); assert 'Original contract' not in d[0].get_text()
  assert len(d[0].get_drawings())==0 # No cover rectangles.
  assert d[0].get_text('dict')['blocks'][0]['lines'][0]['spans'][0]['size']==18

def test_workflow():
 data=engine.validate(fixture()); span=content.inspect(data,0)[0]
 data=engine.apply(data,'replace',{'page':0,'id':span['id'],'text':'Updated contract'})
 data=engine.apply(data,'text',{'page':0,'text':'Added note','x':72,'y':140})
 data=engine.apply(data,'pages',{'indices':[0,2]})
 data=engine.apply(data,'rotate',{'page':1})
 data,mime,ext=engine.export(data,'pdf',{})
 with f.open(stream=data,filetype='pdf') as d:
  assert len(d)==2; assert d[1].rotation==90
  assert 'Updated contract' in d[0].get_text(); assert 'Added note' in d[0].get_text()
  assert 'Original contract' not in ''.join(p.get_text() for p in d)

def test_page_tools():
 data=fixture(); data=engine.apply(data,'pages',{'indices':[2,0,0]})
 data=engine.apply(data,'merge',{},fixture())
 with f.open(stream=data,filetype='pdf') as d: assert len(d)==6
 for kind in ['text','images','split','extract']:
  out,_,_=engine.export(data,kind,{'indices':[0,1]}); assert len(out)>10
 out,_,_=engine.export(data,'protect',{'password':'secret123'})
 with f.open(stream=out,filetype='pdf') as d: assert d.needs_pass; assert d.authenticate('secret123')
 clean=engine.validate(out,'secret123')
 with f.open(stream=clean,filetype='pdf') as d: assert not d.needs_pass

def test_redaction():
 data=fixture(); data=engine.apply(data,'redact',{'rect':[60,70,300,115]})
 with f.open(stream=data,filetype='pdf') as d: assert 'Original contract' not in d[0].get_text()

def test_engine_independently():
 import pathlib
 out=pathlib.Path(__file__).parent/'artifacts'; out.mkdir(exist_ok=True)
 data=fixture(); (out/'selectable.pdf').write_bytes(data)
 doc=f.open(); p=doc.new_page(); p.insert_text((40,80),'SCANNED INVOICE',fontsize=26); pix=p.get_pixmap(dpi=150); doc.close()
 scan=f.open(); p=scan.new_page(); p.insert_image(p.rect,stream=pix.tobytes('png')); scanned=scan.tobytes(); scan.close(); (out/'scanned.pdf').write_bytes(scanned)
 assert content.inspect(scanned,0)==[]
 ocr=engine.apply(scanned,'ocr',{'languages':'eng'})
 with f.open(stream=ocr,filetype='pdf') as d: assert 'SCANNED' in d[0].get_text()
 (out/'searchable.pdf').write_bytes(ocr)
 images=engine.export(scanned,'extract-images',{})[0]; assert len(images)>50
 (out/'images.pdf').write_bytes(scanned)
 doc=f.open(); p=doc.new_page()
 for i,font in enumerate(['helv','tiro','cour','hebo']): p.insert_text((40,60+i*45),f'Font {font} sample',fontname=font,fontsize=12+i*3)
 mixed=doc.tobytes(); (out/'formatted.pdf').write_bytes(mixed)
 spans=content.inspect(mixed,0); assert all(s['editable'] for s in spans)
 edited=content.replace(mixed,0,spans[1]['id'],'Edited serif text'); (out/'formatted-edited.pdf').write_bytes(edited)
 data=fixture(); span=content.inspect(data,0)[0]; data=engine.apply(data,'replace',{'id':span['id'],'text':'Updated contract'}); data=engine.apply(data,'text',{'text':'Added note','x':72,'y':140}); data=engine.apply(data,'pages',{'indices':[0,2]}); data=engine.apply(data,'rotate',{'page':1}); (out/'workflow-result.pdf').write_bytes(data)
