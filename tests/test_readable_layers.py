import io,subprocess,time
from pathlib import Path
import pytest,pymupdf as fitz,pikepdf
from PIL import Image
from fastapi.testclient import TestClient
from backend import engine,layers,ocr
from backend.app import app
from backend.words import inspect_words

PHRASE='Ashok one two three four five six seven eight nine ten'

def document(name='Kartik',neighbor=True):
    with fitz.open() as doc:
        p=doc.new_page();p.insert_text((60,90),name+(' contract continues here' if neighbor else ''),fontsize=16)
        p.insert_text((60,130),'Keep this following line unchanged.',fontsize=16)
        return doc.tobytes()

def test_large_replacement_spaces_wraps_without_compression_or_overlap(tmp_path):
    original=document();word=inspect_words(original,0)[0]
    phrase=PHRASE+'\n'+('A longer readable message with spaces. '*8)
    changed=engine.apply(original,'replace-readable',{'id':word['id'],'original':'Kartik','text':phrase})
    objects=layers.inspect_layers(changed,0);assert len(objects)==1
    layer=objects[0];assert layer['text']==phrase and layer['size']==16
    assert fitz.Rect(layer['rect']).width>300 and fitz.Rect(layer['rect']).height>50
    for other in inspect_words(original,0)[1:]:assert not fitz.Rect(layer['rect']).intersects(fitz.Rect(other['bbox']))
    with fitz.open(stream=changed,filetype='pdf') as doc:
        assert 'Kartik' not in doc[0].get_text()
        assert 'contract continues here' in doc[0].get_text()
        spans=[s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']]
        assert all(s['size']==pytest.approx(16,abs=.01) for s in spans)
    path=tmp_path/'readable.pdf';path.write_bytes(changed)
    extracted=subprocess.check_output(['pdftotext',str(path),'-'],text=True)
    assert 'Kartik' not in extracted and 'Ashok one two three' in extracted
    # Persisted layer metadata and vector rendering survive unrelated PDF tools.
    changed=engine.apply(changed,'compress',{});assert layers.inspect_layers(changed,0)[0]['id']==layer['id']

def test_phrase_in_available_space_edits_actual_original_operands():
    original=document(neighbor=False);word=inspect_words(original,0)[0]
    changed=engine.apply(original,'replace-readable',{'id':word['id'],'original':'Kartik','text':'Ashok one two three'})
    assert layers.inspect_layers(changed,0)==[]
    with fitz.open(stream=changed,filetype='pdf') as doc:assert 'Ashok one two three' in doc[0].get_text() and 'Kartik' not in doc[0].get_text()
    with pikepdf.open(io.BytesIO(changed)) as pdf:assert b'Kartik' not in pdf.pages[0].Contents.read_bytes()

def test_layer_punctuation_is_preserved_instead_of_question_marks():
    text='café — résumé “hello”'
    data=engine.apply(document(),'text',{'text':text,'x':60,'y':220})
    with fitz.open(stream=data,filetype='pdf') as doc:assert text in doc[0].get_text()

def test_added_text_is_editable_movable_resizable_and_removable(tmp_path):
    source=document();data=engine.apply(source,'text',{'text':'Added text with spaces\nA second line','x':60,'y':230,'size':18})
    item=layers.inspect_layers(data,0)[0];identity=item['id'];oldheight=fitz.Rect(item['rect']).height
    data=engine.apply(data,'layer-update',{'id':identity,'rect':[150,300,300,300+oldheight],'text':'This paragraph should wrap naturally at the same readable font size.','color':'#cc0000'})
    item=layers.inspect_layers(data,0)[0];assert item['id']==identity and item['size']==18 and item['color']=='#cc0000'
    assert fitz.Rect(item['rect']).height>oldheight
    with fitz.open(stream=data,filetype='pdf') as doc:
        assert 'Added text with spaces' not in doc[0].get_text()
        spans=[s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['color']==0xcc0000]
        assert spans and all(s['size']==pytest.approx(18,abs=.01) for s in spans)
    data=engine.apply(data,'layer-delete',{'id':identity});assert layers.inspect_layers(data,0)==[]
    with fitz.open(stream=data,filetype='pdf') as doc:assert 'This paragraph' not in doc[0].get_text() and 'Kartik' in doc[0].get_text()

def test_image_layer_moves_resizes_and_removes_image_bytes():
    image=Image.new('RGBA',(120,80),(255,0,0,200));buf=io.BytesIO();image.save(buf,'PNG')
    data=engine.apply(document(),'image',{'rect':[70,220,250,340]},buf.getvalue());item=layers.inspect_layers(data,0)[0]
    data=engine.apply(data,'layer-update',{'id':item['id'],'rect':[240,410,480,570]})
    with fitz.open(stream=data,filetype='pdf') as doc:
        assert len(doc[0].get_images())>0
        rect=doc[0].get_image_info()[0]['bbox'];assert rect==pytest.approx([240,410,480,570],abs=.1)
    data=engine.apply(data,'layer-delete',{'id':item['id']})
    with fitz.open(stream=data,filetype='pdf') as doc:assert doc[0].get_images()==[] and doc[0].get_image_info()==[]
    with pikepdf.open(io.BytesIO(data)) as pdf:assert not any(isinstance(o,pikepdf.Stream) and o.get('/Subtype')==pikepdf.Name('/Image') for o in pdf.objects)

def test_expanding_a_text_layer_avoids_following_content():
    source=document();data=engine.apply(source,'text',{'text':'Short text','x':60,'y':170,'size':16,'width':300})
    data=engine.apply(data,'text',{'text':'Do not cover this lower box','x':60,'y':220,'size':16,'width':300})
    first,second=layers.inspect_layers(data,0)
    changed=engine.apply(data,'layer-update',{'id':first['id'],'text':'An expanded paragraph with many words and spaces. '*8})
    first_after=next(m for m in layers.inspect_layers(changed,0) if m['id']==first['id'])
    assert not fitz.Rect(first_after['rect']).intersects(fitz.Rect(second['rect']))
    assert first_after['size']==16

def test_managed_layer_crop_coordinates_and_redaction_metadata():
    data=engine.apply(document(),'text',{'text':'Layer secret value','x':80,'y':230,'size':16})
    item=layers.inspect_layers(data,0)[0]
    cropped=engine.apply(data,'crop',{'rect':[20,30,550,800]})
    moved=layers.inspect_layers(cropped,0)[0]
    assert moved['rect'][0]==pytest.approx(item['rect'][0]-20,abs=.01)
    assert moved['rect'][1]==pytest.approx(item['rect'][1]-30,abs=.01)
    rect=item['rect'];redacted=engine.apply(data,'redact',{'rect':rect})
    assert layers.inspect_layers(redacted,0)==[]
    with fitz.open(stream=redacted,filetype='pdf') as doc:assert 'Layer secret' not in doc[0].get_text()
    with pikepdf.open(io.BytesIO(redacted)) as pdf:
        assert all('Layer secret' not in str(o.get('/FolioLayer','')) for o in pdf.objects if isinstance(o,(pikepdf.Dictionary,pikepdf.Stream)))

def test_brush_stroke_is_transparent_persisted_and_removable():
    source=document();args={'points':[[55,85],[100,82],[180,88],[220,85]],'width':20,'opacity':.35,'color':'#ffff00'}
    data=engine.apply(source,'brush',args);item=layers.inspect_layers(data,0)[0]
    assert item['type']=='brush' and len(item['points'])==4 and item['opacity']==.35
    with fitz.open(stream=data,filetype='pdf') as doc:
        stroke=next(d for d in doc[0].get_drawings() if d['color']==(1,1,0))
        assert stroke['stroke_opacity']==pytest.approx(.35,abs=.01) and stroke['width']==20
    moved=[v+100 for v in item['rect']];data=engine.apply(data,'layer-update',{'id':item['id'],'rect':moved})
    assert layers.inspect_layers(data,0)[0]['points'][0]==[155,185]
    data=engine.apply(data,'layer-delete',{'id':item['id']})
    with fitz.open(stream=data,filetype='pdf') as doc:assert not doc[0].get_drawings() and 'Kartik' in doc[0].get_text()

def scanned():
    with fitz.open() as doc:
        page=doc.new_page();page.insert_text((60,100),'ASHOK INVOICE',fontsize=30);page.insert_text((60,160),'Invoice total 12345',fontsize=22);pix=page.get_pixmap(dpi=180)
    with fitz.open() as doc:
        doc.new_page().insert_image((0,0,595,842),stream=pix.tobytes('png'));return doc.tobytes()

@pytest.mark.parametrize('mode',['searchable','editable'])
def test_real_ocr_async_job_can_be_downloaded_and_reopened(mode,tmp_path):
    with TestClient(app) as client:
        uploaded=client.post('/api/documents',files={'file':('scan.pdf',scanned())}).json();headers={'X-Session':uploaded['token']}
        res=client.post('/api/document/ocr',headers=headers,json={'args':{'languages':'eng','mode':mode}});assert res.status_code==200,res.text
        deadline=time.monotonic()+45
        while True:
            status=client.get('/api/document/ocr',headers=headers).json()
            if status['state']!='running':break
            assert time.monotonic()<deadline;time.sleep(.05)
        assert status['state']=='complete',status
        assert status['summary']['words']>=4 and status['completed']==1
        output=client.post('/api/document/export',headers=headers,json={'kind':'pdf'}).content;path=tmp_path/f'{mode}.pdf';path.write_bytes(output)
        assert 'ASHOK' in subprocess.check_output(['pdftotext',str(path),'-'],text=True)
        with fitz.open(stream=output,filetype='pdf') as doc:
            assert 'ASHOK' in doc[0].get_text()
            if mode=='editable':assert not doc[0].get_images()
        if mode=='editable':
            word=next(w for w in client.get('/api/document/page/0/text?words_only=true',headers=headers).json()['words'] if w['text']=='ASHOK')
            assert word['editable']
            res=client.post('/api/document/operation',headers=headers,json={'operation':'replace-readable','args':{'id':word['id'],'original':'ASHOK','text':'KARTIK'}});assert res.status_code==200,res.text

def test_ocr_failure_cancellation_and_conflicting_edits_preserve_original(monkeypatch):
    import importlib
    module=importlib.import_module('backend.app')
    def slow(data,languages,mode,indices,progress,cancel):
        progress(0,1,'Test OCR started')
        while not cancel.wait(.01):pass
        raise ocr.Cancelled()
    monkeypatch.setattr(module.ocr,'process',slow)
    with TestClient(app) as client:
        uploaded=client.post('/api/documents',files={'file':('scan.pdf',scanned())}).json();h={'X-Session':uploaded['token']};before=client.get('/api/document/pdf',headers=h).content
        assert client.post('/api/document/ocr',headers=h,json={'args':{'languages':'missing'}}).status_code==422
        assert client.post('/api/document/ocr',headers=h,json={'args':{'languages':'eng'}}).status_code==200
        assert client.post('/api/document/operation',headers=h,json={'operation':'compress'}).status_code==409
        assert client.delete('/api/document/ocr',headers=h).status_code==200
        for _ in range(100):
            state=client.get('/api/document/ocr',headers=h).json()['state']
            if state!='running':break
            time.sleep(.01)
        assert state=='cancelled' and client.get('/api/document/pdf',headers=h).content==before
