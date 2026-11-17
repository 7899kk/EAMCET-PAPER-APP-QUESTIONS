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

def test_fixed_size_flow_keeps_source_font_and_removes_original():
    source=fixture();block=next(b for b in blocks.inspect_blocks(source,0) if 'this video' in b['text'])
    changed,updated=blocks.replace_block(source,0,{'id':block['id'],'original':block['text'],'text':block['text'].replace('this video','this type of video')})
    assert updated['rect'][:2]==pytest.approx(block['rect'][:2],abs=.01)
    assert updated['rect'][2]>=block['rect'][2]
    assert updated['size']==block['size'] and updated['font']==block['font']
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


def reflow_fixture():
    with fitz.open() as doc:
        p=doc.new_page(width=420,height=500)
        xref=p.insert_font(fontname='body',fontbuffer=layers.font_buffer('helv'));layers.normalize_space_map(doc,xref)
        p.insert_text((45,55),'Link-',fontname='body',fontsize=18)
        p.insert_text((45,90),"I'm feeling happy Today",fontname='body',fontsize=18)
        p.insert_text((45,210),'Keep this separate paragraph.',fontname='body',fontsize=18)
        return doc.tobytes()

def test_longer_word_pushes_following_words_without_shrinking():
    source=reflow_fixture();target=next(b for b in blocks.inspect_blocks(source,0) if 'feeling' in b['text'])
    result,updated=blocks.replace_block(source,0,{'id':target['id'],'original':target['text'],'text':"I'm Enthusiam happy Today"})
    assert updated['size']==18
    with fitz.open(stream=source,filetype='pdf') as before,fitz.open(stream=result,filetype='pdf') as after:
        old=next(w for w in before[0].get_text('words') if w[4]=='happy')
        new=next(w for w in after[0].get_text('words') if w[4]=='happy')
        assert new[0]>old[0] and new[1]==pytest.approx(old[1],abs=.02)
        assert 'feeling' not in after[0].get_text()
        assert 'Keep this separate paragraph.' in after[0].get_text()
        spans=[s for b in after[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if 'Enthusiam' in s['text']]
        assert spans and spans[0]['size']==18

def test_wrapping_grows_down_and_survives_reopen_at_exact_font_size():
    source=reflow_fixture();target=next(b for b in blocks.inspect_blocks(source,0) if 'feeling' in b['text'])
    text="I'm feeling really enthusiastic and happy Today and ready to make this type of video."
    result,updated=blocks.replace_block(source,0,{'id':target['id'],'original':target['text'],'text':text})
    assert updated['size']==18 and updated['rect'][3]>target['rect'][3] and updated['rect'][3]<190
    with fitz.open(stream=result,filetype='pdf') as doc:
        words=[w for w in doc[0].get_text('words') if w[1]<180 and w[4]!='Link-']
        assert len({round(w[1],1) for w in words})>=2
        assert all(w[2]<=375.02 for w in words)
        rendered=' '.join(doc[0].get_text().split());assert text in rendered
        original_next=next(b for b in doc[0].get_text('blocks') if 'Keep this' in b[4]);assert original_next[1]==pytest.approx(193.71,abs=.05)
    # Exported/reopened metadata continues to use the same size and box identity.
    reopened=next(b for b in blocks.inspect_blocks(result,0) if 'enthusiastic' in b['text'])
    shorter,short=blocks.replace_block(result,0,{'id':reopened['id'],'original':reopened['text'],'text':"I'm Enthusiam happy Today"})
    assert short['size']==18 and short['layer_id']==updated['layer_id'] and short['rect'][3]<updated['rect'][3]

def test_full_area_refuses_collision_without_shrinking_or_moving_other_text():
    source=reflow_fixture();target=next(b for b in blocks.inspect_blocks(source,0) if 'feeling' in b['text'])
    with pytest.raises(ValueError,match='Font size was not reduced'):
        blocks.replace_block(source,0,{'id':target['id'],'original':target['text'],'text':'Longer text with spaces '*100})
    with fitz.open(stream=source,filetype='pdf') as doc:assert "I'm feeling happy Today" in doc[0].get_text()
