import io,time
import pytest,pymupdf as fitz
from fastapi.testclient import TestClient
from backend.app import app
from backend import blocks,layers,ocr

def mixed():
    with fitz.open() as art:
        p=art.new_page(width=470,height=160);p.insert_text((25,65),'IMAGE WORDS 87453',fontsize=25);image=p.get_pixmap(dpi=180).tobytes('png')
    with fitz.open() as doc:
        p=doc.new_page();p.insert_text((50,90),'NATIVE HEADER 12345',fontsize=22);p.insert_image((50,180,520,340),stream=image);return doc.tobytes()

def test_blank_pdf_is_real_and_supports_image_insertion_and_export():
    with TestClient(app) as c:
        r=c.post('/api/documents/blank');assert r.status_code==200,r.text
        h={'X-Session':r.json()['token']}
        with fitz.open(stream=c.get('/api/document/pdf',headers=h).content,filetype='pdf') as d:assert len(d)==1 and not d[0].get_text() and d[0].rect.width==595
        with fitz.open(stream=mixed(),filetype='pdf') as d:image=d[0].get_pixmap().tobytes('png')
        r=c.post('/api/document/file-operation',headers=h,data={'operation':'image','args':'{"page":0,"rect":[50,50,500,700]}'},files={'file':('sample.png',image,'image/png')});assert r.status_code==200,r.text
        with fitz.open(stream=c.post('/api/document/export',headers=h,json={'kind':'pdf'}).content,filetype='pdf') as d:assert len(d[0].get_image_info())==1

@pytest.mark.parametrize('font',['helv','tiro','cour'])
def test_repeated_inline_boxes_keep_chosen_fonts_and_can_move_resize(font):
    with TestClient(app) as c:
        h={'X-Session':c.post('/api/documents/blank').json()['token']}
        ids=[]
        for i in range(2):
            y=60+i*120
            r=c.post('/api/document/inline-edit',headers=h,json={'operation':'replace-block','args':{'id':'new','page':0,'rect':[50,y,350,y+30],'text':f'Independent box {i+1}','font':font,'size':20}});assert r.status_code==200,r.text
            ids.append(r.json()['inline_block']['layer_id'])
        assert len(set(ids))==2
        r=c.post('/api/document/operation',headers=h,json={'operation':'layer-update','args':{'page':0,'id':ids[0],'rect':[80,70,410,120],'font':'hebo','size':24}});assert r.status_code==200,r.text
        out=c.post('/api/document/export',headers=h,json={'kind':'pdf'}).content
        objs=layers.inspect_layers(out,0);assert len(objs)==2 and next(o for o in objs if o['id']==ids[0])['size']==24
        assert next(o for o in objs if o['id']==ids[1])['font']==font
        with fitz.open(stream=out,filetype='pdf') as d:assert all(f'Independent box {i+1}' in d[0].get_text() for i in range(2))

@pytest.mark.parametrize('mode',['layout','searchable'])
def test_ocr_does_not_skip_image_words_when_page_has_native_text(mode):
    data,_=ocr.process(mixed(),mode=mode)
    with fitz.open(stream=data,filetype='pdf') as d:
        text=' '.join(d[0].get_text().split());assert 'NATIVE HEADER 12345' in text and 'IMAGE WORDS 87453' in text
    if mode=='layout':
        target=next(b for b in blocks.inspect_blocks(data,0) if 'IMAGE WORDS' in b['text']);assert target['editable']
        out,_=blocks.replace_block(data,0,{'id':target['id'],'original':target['text'],'text':'IMAGE TEXT IS EDITED'})
        with fitz.open(stream=out,filetype='pdf') as d:assert 'IMAGE TEXT IS EDITED' in d[0].get_text()
