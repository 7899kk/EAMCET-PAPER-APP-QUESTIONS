import io,os,time
from pathlib import Path
import pytest,pymupdf as fitz,pikepdf
from PIL import Image
from fastapi.testclient import TestClient
from backend import blocks,layers,images,engine
from backend.app import app

def fixture():
    with fitz.open() as doc:
        page=doc.new_page();xref=page.insert_font(fontname='body',fontbuffer=layers.font_buffer('helv'));layers.normalize_space_map(doc,xref)
        page.insert_text((60,90),'So with this we can make this video.',fontname='body',fontsize=16,color=(.2,.3,.4))
        page.insert_text((60,230),'Keep the following panel unchanged.',fontname='body',fontsize=16)
        image=Image.new('RGB',(80,60),'red');b=io.BytesIO();image.save(b,'PNG')
        page.insert_image((60,330,180,420),stream=b.getvalue());page.insert_image((300,330,420,420),stream=b.getvalue())
        return doc.tobytes()

def test_same_frame_reflow_keeps_source_font_and_removes_original():
    source=fixture();block=next(b for b in blocks.inspect_blocks(source,0) if 'this video' in b['text'])
    changed,updated=blocks.replace_block(source,0,{'id':block['id'],'original':block['text'],'text':block['text'].replace('this video','this type of video')})
    assert updated['rect']==pytest.approx(block['rect'],abs=.01)
    assert block['size']*.65<=updated['size']<=block['size'] and updated['font']==block['font']
    assert blocks.font_for_block(changed,0,updated)==blocks.font_for_block(source,0,block)
    with fitz.open(stream=changed,filetype='pdf') as doc:
        text=' '.join(doc[0].get_text().split());assert 'make this type of video.' in text and 'make this video.' not in text
        assert 'Keep the following panel unchanged.' in text and len(doc[0].get_image_info())==2
    # Subsequent edits reuse the same object and can restore the original size.
    again,latest=blocks.replace_block(changed,0,{'id':updated['id'],'original':updated['text'],'text':'A short line.'})
    assert latest['layer_id']==updated['layer_id'] and latest['size']==block['size']

def test_overflow_and_stale_original_do_not_commit():
    data=fixture();block=blocks.inspect_blocks(data,0)[0]
    with pytest.raises(ValueError,match='more text'):blocks.replace_block(data,0,{'id':block['id'],'original':block['text'],'text':'Many additional words '*200})
    with pytest.raises(ValueError,match='changed'):blocks.replace_block(data,0,{'id':block['id'],'original':'incorrect','text':'hello'})
    with fitz.open(stream=data,filetype='pdf') as doc:assert 'this video' in doc[0].get_text()

def test_preview_mask_removes_only_text_with_no_cover_rectangle():
    data=fixture();block=blocks.inspect_blocks(data,0)[0];masked=blocks.remove_block(data,0,block)
    with fitz.open(stream=masked,filetype='pdf') as doc:
        assert 'this video' not in doc[0].get_text() and 'following panel' in doc[0].get_text()
        assert not doc[0].get_drawings() and len(doc[0].get_image_info())==2

def test_original_image_occurrence_delete_and_move_keep_other_instance():
    source=fixture();items=images.inspect_images(source,0);assert len(items)==2
    deleted=engine.apply(source,'layer-delete',{'id':items[0]['id']})
    with fitz.open(stream=deleted,filetype='pdf') as doc:assert len(doc[0].get_image_info())==1 and doc[0].get_image_info()[0]['bbox'][0]==300
    moved=engine.apply(source,'layer-update',{'id':items[0]['id'],'rect':[100,450,260,570]})
    with fitz.open(stream=moved,filetype='pdf') as doc:
        boxes=[i['bbox'] for i in doc[0].get_image_info()];assert len(boxes)==2 and any(fitz.Rect(b).x0==100 and fitz.Rect(b).y0==450 for b in boxes)
    assert len(layers.inspect_layers(moved,0))==1

def test_inline_api_font_mask_autosave_export_and_undo():
    with TestClient(app) as client:
        uploaded=client.post('/api/documents',files={'file':('sample.pdf',fixture())}).json();h={'X-Session':uploaded['token']}
        block=client.get('/api/document/page/0/blocks',headers=h).json()['blocks'][0]
        assert client.get('/api/document/page/0/font',headers=h,params={'block':block['id']}).content
        mask=client.get('/api/document/page/0/pdf',headers=h,params={'exclude_block':block['id']});assert mask.status_code==200
        res=client.post('/api/document/inline-edit',headers=h,json={'operation':'replace-block','args':{'page':0,'id':block['id'],'original':block['text'],'text':block['text'].replace('this video','this type of video')}});assert res.status_code==200,res.text
        saved=res.json()['inline_block'];assert saved['kind']=='layer'
        output=client.post('/api/document/export',headers=h,json={'kind':'pdf'}).content
        with fitz.open(stream=output,filetype='pdf') as doc:assert 'type of video' in doc[0].get_text()
        assert client.post('/api/document/history/undo',headers=h).status_code==200
        assert client.get('/api/document/page/0/blocks',headers=h).json()['blocks'][0]['text']==block['text']

@pytest.mark.skipif(not os.environ.get('FOLIO_SAMPLE_PDF'),reason='Optional private local PDF; never committed or uploaded to another service')
def test_user_document_same_frame_font_and_images():
    source=Path(os.environ['FOLIO_SAMPLE_PDF']).read_bytes();page=int(os.environ.get('FOLIO_SAMPLE_PAGE','1'))
    block=next(b for b in blocks.inspect_blocks(source,page) if 'the whole video' in b['text'])
    result,updated=blocks.replace_block(source,page,{'id':block['id'],'original':block['text'],'text':block['text'].replace('the whole video','this type of video')})
    assert updated['rect']==pytest.approx(block['rect'],abs=.01) and updated['font']==block['font']
    with fitz.open(stream=source,filetype='pdf') as before,fitz.open(stream=result,filetype='pdf') as after:
        assert len(before)==len(after)
        for old,new in zip(before,after):assert len(old.get_image_info())==len(new.get_image_info())
        assert 'the whole video' not in after[page].get_text()
