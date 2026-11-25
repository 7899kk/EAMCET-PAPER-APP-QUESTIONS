"""Numbers in mixed-style lines must retain their own face, size and colour."""
from pathlib import Path
import io
import pytest
import pymupdf as fitz
from fastapi.testclient import TestClient
from backend import blocks,layers,engine
from backend.app import app


def numeric_pdf(font='hebo',font_bytes=None):
    with fitz.open() as doc:
        p=doc.new_page()
        regular=layers.font_buffer('helv')
        for name,raw in [('body',regular),('amount',font_bytes or layers.font_buffer(font))]:
            xref=p.insert_font(fontname=name,fontbuffer=raw);layers.normalize_space_map(doc,xref)
        p.insert_text((50,100),'Invoice total: ',fontname='body',fontsize=18)
        x=50+fitz.Font(fontbuffer=regular).text_length('Invoice total: ',fontsize=18)
        p.insert_text((x,100),'12345',fontname='amount',fontsize=18,color=(.8,.1,.2))
        p.insert_text((50,180),'24680',fontname='amount',fontsize=22)
        p.insert_text((50,260),'Unchanged body and image area.',fontname='body',fontsize=14)
        return doc.tobytes()


@pytest.mark.parametrize('font',list(layers.FONTS))
def test_numeric_edits_preserve_exact_embedded_font_and_neighbours(font):
    source=numeric_pdf(font)
    detected=blocks.inspect_blocks(source,0)
    number=next(b for b in detected if '12345' in b['text'])
    style=number['style_runs'][-1]
    assert number['size']==18 and style['color']=='#cc1a33'
    face=blocks.font_for_block(source,0,number,number['style_runs'][-1]['font_key'])
    result,updated=blocks.replace_block(source,0,{'id':number['id'],'original':number['text'],'text':number['text'].replace('12345','98765.00')})
    assert updated['size']==18 and updated['style_runs'][-1]['color']==style['color']
    assert blocks.font_for_block(result,0,updated,updated['style_runs'][-1]['font_key'])==face
    with fitz.open(stream=source,filetype='pdf') as before,fitz.open(stream=result,filetype='pdf') as after:
        assert '12345' not in after[0].get_text() and '98765.00' in after[0].get_text()
        old=before[0].get_pixmap(clip=(45,70,145,115)).samples
        new=after[0].get_pixmap(clip=(45,70,145,115)).samples
        assert old==new,'Editing the amount changed neighbouring regular text'
        span=next(s for b in after[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if '98765' in s['text'])
        assert span['font']==style['font'] and span['size']==number['size'] and span['color']==int(style['color'][1:],16)
    reopened=next(b for b in blocks.inspect_blocks(result,0) if '98765.00' in b['text'])
    again,last=blocks.replace_block(result,0,{'id':reopened['id'],'original':reopened['text'],'text':reopened['text'].replace('98765.00','10000.50')})
    assert last['layer_id']==updated['layer_id'] and blocks.font_for_block(again,0,last,last['style_runs'][-1]['font_key'])==face


@pytest.mark.parametrize('name',['OpenSans-ExtraBold','OpenSans-SemiboldItalic'])
def test_embedded_heavy_weights_are_reused_without_substitution(name):
    path=Path('/usr/share/fonts/truetype/open-sans')/(name+'.ttf')
    if not path.exists():pytest.skip('Optional distro test font')
    source=numeric_pdf(font_bytes=path.read_bytes());number=next(b for b in blocks.inspect_blocks(source,0) if '12345' in b['text'])
    original_font=blocks.font_for_block(source,0,number,number['style_runs'][-1]['font_key'])
    result,updated=blocks.replace_block(source,0,{'id':number['id'],'original':number['text'],'text':number['text'].replace('12345','67890')})
    assert blocks.font_for_block(result,0,updated,updated['style_runs'][-1]['font_key'])==original_font
    assert updated['font']==number['font'] and updated['size']==18 and not updated.get('font_notice')


def test_font_lookup_uses_exact_name_before_prefix():
    class Page:
        def get_fonts(self,full=True):return [(1,'ttf','TrueType','LiberationSans-Bold','Bold',''),(2,'ttf','TrueType','LiberationSans','Regular','')]
    class Doc:
        def extract_font(self,xref):return ('','', '',layers.font_buffer('hebo' if xref==1 else 'helv'))
    assert blocks.font_choice(Doc(),Page(),'LiberationSans',None)[0]==2
    assert blocks.font_choice(Doc(),Page(),'LiberationSans-Bold',None)[0]==1


def test_same_named_subset_fonts_resolve_the_actual_resource_for_each_style():
    from fontTools import subset
    def partial(text):
        font=subset.load_font(io.BytesIO(layers.font_buffer('helv')),subset.Options())
        tool=subset.Subsetter();tool.populate(text=text);tool.subset(font)
        output=io.BytesIO();font.save(output);font.close();return output.getvalue()
    with fitz.open() as doc:
        page=doc.new_page()
        for name,raw in [('label',partial('Invoice total: ')),('digits',partial('0123456789 '))]:
            xref=page.insert_font(fontname=name,fontbuffer=raw);layers.normalize_space_map(doc,xref)
        page.insert_text((50,100),'Invoice total: ',fontname='label',fontsize=18)
        page.insert_text((160,100),'12345',fontname='digits',fontsize=18,color=(.8,.1,.2))
        source=doc.tobytes()
    b=blocks.inspect_blocks(source,0)[0];assert len(b['style_runs'])==2
    label,amount=b['style_runs'];assert label['font']==amount['font'] and label['font_key']!=amount['font_key']
    raw=blocks.font_for_block(source,0,b,amount['font_key'])
    assert fitz.Font(fontbuffer=raw).has_glyph(ord('9')) and not fitz.Font(fontbuffer=raw).has_glyph(ord('I'))
    result,updated=blocks.replace_block(source,0,{'id':b['id'],'original':b['text'],'text':b['text'].replace('12345','98765')})
    assert blocks.font_for_block(result,0,updated,amount['font_key'])==raw


def test_native_first_save_applies_formatting_and_invalid_style_is_atomic():
    with TestClient(app) as client:
        token=client.post('/api/documents',files={'file':('numbers.pdf',numeric_pdf())}).json()['token'];h={'X-Session':token}
        number=next(b for b in client.get('/api/document/page/0/blocks',headers=h).json()['blocks'] if '12345' in b['text'])
        args={'page':0,'id':number['id'],'original':number['text'],'text':number['text'].replace('12345','67890'),'box_style':{'font':'cobi','size':22,'color':'#336699'}}
        bad=client.post('/api/document/inline-edit',headers=h,json={'operation':'replace-block','args':{**args,'box_style':{'font':'not-a-font'}}})
        assert bad.status_code==422
        source=client.post('/api/document/export',headers=h,json={'kind':'pdf'}).content
        with fitz.open(stream=source,filetype='pdf') as doc:assert '12345' in doc[0].get_text() and '67890' not in doc[0].get_text()
        res=client.post('/api/document/inline-edit',headers=h,json={'operation':'replace-block','args':args})
        assert res.status_code==200,res.text
        saved=res.json()['inline_block'];assert saved['font_code']=='cobi' and saved['size']==22 and saved['color']=='#336699'
        output=client.post('/api/document/export',headers=h,json={'kind':'pdf'}).content
        with fitz.open(stream=output,filetype='pdf') as doc:
            span=next(s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if '67890' in s['text'])
            assert span['font']=='LiberationMono-BoldItalic' and span['size']==22 and span['color']==0x336699


def test_rich_numbers_wrap_following_regular_words_and_survive_other_tools():
    with fitz.open(stream=numeric_pdf(),filetype='pdf') as doc:
        p=doc[0];x=50+fitz.Font(fontbuffer=layers.font_buffer('helv')).text_length('Invoice total: ',fontsize=18)+fitz.Font(fontbuffer=layers.font_buffer('hebo')).text_length('12345',fontsize=18)
        p.insert_text((x,100),' including taxes and fees',fontname='body',fontsize=18)
        source=doc.tobytes()
    b=next(b for b in blocks.inspect_blocks(source,0) if '12345' in b['text'])
    text=b['text'].replace('12345','98765 43210 98765 43210 98765')
    result,updated=blocks.replace_block(source,0,{'id':b['id'],'original':b['text'],'text':text})
    assert updated['size']==18 and updated['rect'][3]>b['rect'][3]
    original_number=b['style_runs'][1];original_font=blocks.font_for_block(source,0,b,original_number['font_key'])
    for operation,args in [('compress',{}),('metadata',{'metadata':{'title':'Styled numbers'}}),('clear-metadata',{}),('rotate',{'angle':90}),('rotate',{'angle':-90})]:
        result=engine.apply(result,operation,args)
    reopened=next(b for b in blocks.inspect_blocks(result,0) if '98765' in b['text'])
    assert blocks.font_for_block(result,0,reopened,original_number['font_key'])==original_font
    with fitz.open(stream=result,filetype='pdf') as doc:
        assert text in ' '.join(doc[0].get_text().split())
        suffix=next(s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if 'fees' in s['text'])
        assert suffix['font']=='LiberationSans' and suffix['size']==18 and suffix['color']==0
        number=next(s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if '98765' in s['text'])
        assert number['font']=='LiberationSans-Bold' and number['color']==0xcc1a33


def test_rich_duplicate_resize_and_delete_keep_all_source_fonts():
    source=numeric_pdf();b=next(b for b in blocks.inspect_blocks(source,0) if '12345' in b['text'])
    first,managed=blocks.replace_block(source,0,{'id':b['id'],'original':b['text'],'text':b['text'].replace('12345','98765')})
    rect=managed['rect'];target=[rect[0],rect[1]+35,rect[2],rect[3]+35]
    copied,clone=blocks.replace_block(first,0,{'id':managed['id'],'original':managed['text'],'text':managed['text'],'rect':target},duplicate=True)
    assert clone['layer_id']!=managed['layer_id']
    for style in managed['style_runs']:
        assert blocks.font_for_block(first,0,managed,style['font_key'])==blocks.font_for_block(copied,0,clone,style['font_key'])
    moved=layers.update(copied,0,{'id':clone['layer_id'],'rect':[80,350,500,420],'size':20})
    copy=blocks.managed_block(moved,0,clone['layer_id'])
    assert copy['size']==20 and copy['style_runs']==clone['style_runs']
    removed=layers.remove(moved,0,clone['layer_id'])
    remaining=layers.inspect_layers(removed,0)
    assert len(remaining)==1 and remaining[0]['id']==managed['layer_id']
