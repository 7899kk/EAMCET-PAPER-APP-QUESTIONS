import io
from pathlib import Path
import pytest,pymupdf as fitz
from PIL import Image
from backend import blocks,layers,ocr

def nested():
    with fitz.open() as doc,fitz.open() as part:
        p=part.new_page(width=400,height=80);p.insert_text((10,30),'Nested text can be edited.',fontsize=16)
        for _ in range(2):
            page=doc.new_page();page.show_pdf_page(fitz.Rect(45,100,445,180),part,0)
        return doc.tobytes()

def test_true_nested_edit_removes_source_and_keeps_other_page():
    data=nested();b=blocks.inspect_blocks(data,0)[0];assert b['editable'] and b['removal']=='glyphs'
    result,updated=blocks.replace_block(data,0,{'id':b['id'],'original':b['text'],'text':'Nested text has truly changed.'})
    assert updated['size']==16
    with fitz.open(stream=result,filetype='pdf') as doc:
        assert 'Nested text has truly changed.' in doc[0].get_text()
        assert 'Nested text can be edited.' not in doc[0].get_text()
        assert 'Nested text can be edited.' in doc[1].get_text()
        assert not doc[0].get_drawings()

def test_subset_font_supports_new_letters_at_same_size():
    with fitz.open() as doc:
        p=doc.new_page();p.insert_font(fontname='body',fontbuffer=layers.font_buffer('helv'))
        p.insert_text((45,90),'ASHOK',fontname='body',fontsize=20);doc.subset_fonts();data=doc.tobytes()
    b=blocks.inspect_blocks(data,0)[0];assert b['editable']
    result,u=blocks.replace_block(data,0,{'id':b['id'],'original':b['text'],'text':'Ashok one two three and new letters'})
    assert u['size']==20 and u['font_notice']
    with fitz.open(stream=result,filetype='pdf') as doc:assert 'Ashok one two three' in doc[0].get_text()

@pytest.mark.parametrize('font',['heit','hebi','tiit','tibi','coit','cobi'])
def test_italic_standard_fonts_are_editable(font):
    with fitz.open() as doc:
        doc.new_page().insert_text((45,90),'Italic words stay editable.',fontname=font,fontsize=16);data=doc.tobytes()
    b=blocks.inspect_blocks(data,0)[0];assert b['editable']
    result,u=blocks.replace_block(data,0,{'id':b['id'],'original':b['text'],'text':'Italic words are now changed.'})
    assert u['size']==16
    with fitz.open(stream=result,filetype='pdf') as doc:assert 'are now changed' in doc[0].get_text()

def scan():
    with fitz.open() as d:
        p=d.new_page();p.insert_text((45,90),'SCANNED INVOICE',fontsize=30);p.insert_text((45,150),'Ashok feels happy today.',fontsize=22)
        p.draw_rect((45,320,185,418),color=(.1,.3,.7),fill=(.1,.3,.7));pix=p.get_pixmap(dpi=180)
    with fitz.open() as d:
        p=d.new_page();p.insert_image(p.rect,stream=pix.tobytes('png'));return d.tobytes()

def test_scan_reconstruction_keeps_artwork_and_produces_truly_editable_text():
    source=scan();data,summary=ocr.process(source,mode='layout')
    targets=blocks.inspect_blocks(data,0);b=next(b for b in targets if 'Ashok' in b['text']);assert b['editable']
    changed,u=blocks.replace_block(data,0,{'id':b['id'],'original':b['text'],'text':b['text'].replace('Ashok','Kartik')})
    assert u['size']==b['size']
    with fitz.open(stream=source,filetype='pdf') as before,fitz.open(stream=changed,filetype='pdf') as after:
        assert 'Kartik' in after[0].get_text() and 'Ashok' not in after[0].get_text()
        # The old raster is replaced, with the separate artwork region unchanged.
        a=before[0].get_pixmap(dpi=72,clip=fitz.Rect(60,335,170,400));b=after[0].get_pixmap(dpi=72,clip=fitz.Rect(60,335,170,400))
        assert a.samples==b.samples and len(after[0].get_images())==1

def test_searchable_ocr_pixels_are_not_mislabelled_as_native_editing():
    data,_=ocr.process(scan(),mode='searchable');targets=blocks.inspect_blocks(data,0)
    assert targets and not any(b['editable'] for b in targets)

def test_nested_edit_does_not_apply_unrelated_existing_redaction_marks():
    data=nested()
    with fitz.open(stream=data,filetype='pdf') as doc:
        doc[0].add_redact_annot((10,10,30,30));data=doc.tobytes()
    b=blocks.inspect_blocks(data,0)[0]
    with pytest.raises(ValueError,match='unapplied redaction'):
        blocks.replace_block(data,0,{'id':b['id'],'original':b['text'],'text':'Changed text'})
