import io
import subprocess
from pathlib import Path
import pikepdf
import pymupdf as fitz
import pytest
from backend import engine
from backend.words import inspect_words,replace_word


def make_pdf(text='Keep this word and this word unchanged'):
    doc=fitz.open();page=doc.new_page();page.insert_text((40,80),text,fontsize=16)
    return doc.tobytes()


def stream_pdf(stream):
    with pikepdf.open(io.BytesIO(make_pdf())) as pdf:
        pdf.pages[0].Contents=pdf.make_stream(stream)
        out=io.BytesIO();pdf.save(out);return out.getvalue()


def edit(data,word,text,**options):
    return replace_word(data,0,word['id'],word['text'],text,**options)


def word_boxes(data):
    with fitz.open(stream=data,filetype='pdf') as doc:return doc[0].get_text('words')


def test_edit_one_repeated_word_preserves_every_other_word():
    original=make_pdf();words=inspect_words(original,0);assert all(w['editable'] for w in words)
    chosen=[w for w in words if w['text']=='word'][1]
    changed=edit(original,chosen,'term')
    before,after=word_boxes(original),word_boxes(changed)
    assert [w[4] for w in after]==['Keep','this','word','and','this','term','unchanged']
    for i in [0,1,2,3,4,6]:assert after[i][:4]==pytest.approx(before[i][:4],abs=.02)
    with fitz.open(stream=changed,filetype='pdf') as doc:assert not doc[0].get_drawings()


def test_repeated_identical_lines_are_editable_by_position():
    doc=fitz.open();p=doc.new_page()
    for y in [80,140]:p.insert_text((40,y),'Same word here',fontsize=16)
    original=doc.tobytes();words=inspect_words(original,0)
    candidates=[w for w in words if w['text']=='word'];assert len(candidates)==2 and all(w['editable'] for w in candidates)
    changed=edit(original,candidates[1],'term')
    with fitz.open(stream=changed,filetype='pdf') as doc:assert doc[0].get_text().splitlines()==['Same word here','Same term here']


def test_fragmented_word_across_several_text_operators():
    original=stream_pdf(b'BT /helv 16 Tf 1 0 0 1 40 762 Tm (Keep ) Tj (con) Tj (tr) Tj (act) Tj ( tail) Tj ET')
    words=inspect_words(original,0);chosen=next(w for w in words if w['text']=='contract')
    assert chosen['editable'] and len(chosen['parts'])==3
    changed=edit(original,chosen,'agreement')
    assert [w[4] for w in word_boxes(changed)]==['Keep','agreement','tail']
    assert word_boxes(changed)[-1][:4]==pytest.approx(word_boxes(original)[-1][:4],abs=.02)


def test_tj_kerning_outside_selected_word_is_preserved():
    original=stream_pdf(b'BT /helv 16 Tf 1 0 0 1 40 762 Tm [(alpha) -15 ( ) -20 (be) 12 (ta) 10 ( ) 25 (gamma)] TJ ET')
    chosen=next(w for w in inspect_words(original,0) if w['text']=='beta');assert chosen['editable']
    changed=edit(original,chosen,'delta')
    assert [w[4] for w in word_boxes(changed)]==['alpha','delta','gamma']
    for i in [0,2]:assert word_boxes(changed)[i][:4]==pytest.approx(word_boxes(original)[i][:4],abs=.02)


def test_longer_replacement_fits_original_space_without_moving_neighbor():
    original=make_pdf('A cat sleeps')
    chosen=next(w for w in inspect_words(original,0) if w['text']=='cat')
    changed=edit(original,chosen,'elephant')
    after=word_boxes(changed);before=word_boxes(original)
    assert after[1][2]<=before[1][2]+.02
    assert after[-1][:4]==pytest.approx(before[-1][:4],abs=.02)
    assert inspect_words(changed,0)[1]['editable']
    changed=edit(changed,inspect_words(changed,0)[1],'tiger')
    assert word_boxes(changed)[-1][:4]==pytest.approx(before[-1][:4],abs=.02)


def test_style_change_applies_to_selected_word_only():
    original=make_pdf('Keep this word unchanged')
    chosen=inspect_words(original,0)[2]
    changed=edit(original,chosen,'term',size=20,color='#cc1133')
    words=inspect_words(changed,0)
    assert words[2]['color']=='#cc1133' and words[2]['size']==pytest.approx(20,abs=.01)
    assert all(w['color']=='#000000' and w['size']==pytest.approx(16,abs=.01) for i,w in enumerate(words) if i!=2)


def test_character_and_word_spacing_and_scaled_text():
    original=stream_pdf(b'2 0 0 2 0 0 cm BT /helv 8 Tf 0.4 Tc 1 Tw 1 0 0 1 20 380 Tm (Keep word here) Tj ET')
    chosen=next(w for w in inspect_words(original,0) if w['text']=='word');assert chosen['editable']
    changed=edit(original,chosen,'term')
    assert [w[4] for w in word_boxes(changed)]==['Keep','term','here']
    assert word_boxes(changed)[-1][:4]==pytest.approx(word_boxes(original)[-1][:4],abs=.03)


def test_embedded_unicode_font_and_word_edit():
    doc=fitz.open();p=doc.new_page();p.insert_font(fontname='custom',fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    p.insert_text((40,80),'Embedded sample font',fontname='custom',fontsize=17)
    original=doc.tobytes();chosen=inspect_words(original,0)[1];assert chosen['editable']
    changed=edit(original,chosen,'simple')
    assert [w[4] for w in word_boxes(changed)]==['Embedded','simple','font']
    assert word_boxes(changed)[-1][:4]==pytest.approx(word_boxes(original)[-1][:4],abs=.03)


def test_word_input_and_stale_selection_are_validated():
    original=make_pdf();chosen=inspect_words(original,0)[2]
    with pytest.raises(ValueError,match='one word'):edit(original,chosen,'two words')
    with pytest.raises(ValueError,match='changed'):replace_word(original,0,chosen['id'],'incorrect','term')
    with pytest.raises(ValueError,match='font does not contain'):edit(original,chosen,'猫')


def test_delete_word_removes_its_operand_without_covering_it():
    original=make_pdf('Keep secret here');chosen=inspect_words(original,0)[1]
    changed=edit(original,chosen,'')
    assert [w[4] for w in word_boxes(changed)]==['Keep','here']
    with fitz.open(stream=changed,filetype='pdf') as doc:assert not doc[0].get_drawings()


def test_scanned_pages_and_rotated_or_mixed_style_text_are_not_fake_editable():
    doc=fitz.open();p=doc.new_page();p.insert_text((40,80),'Scanned text');pix=p.get_pixmap()
    scan=fitz.open();p=scan.new_page();p.insert_image(p.rect,stream=pix.tobytes('png'))
    assert inspect_words(scan.tobytes(),0)==[]
    d=fitz.open(stream=make_pdf(),filetype='pdf');d[0].set_rotation(90)
    assert not any(w['editable'] for w in inspect_words(d.tobytes(),0))


def test_word_edit_export_is_independently_reopened(tmp_path):
    data=make_pdf('The quick brown fox')
    word=inspect_words(data,0)[1]
    data=engine.apply(data,'replace-word',{'id':word['id'],'original':'quick','text':'swift'})
    out=tmp_path/'word-edited.pdf';out.write_bytes(engine.export(data,'pdf',{})[0])
    extracted=subprocess.check_output(['pdftotext',str(out),'-'],text=True)
    assert 'The swift brown fox' in extracted and 'quick' not in extracted

@pytest.mark.parametrize('ending',[b'(next word here) \'',b'1 0.2 (next word here) "'])
def test_quote_text_operators_keep_line_position_and_spacing(ending):
    original=stream_pdf(b'BT /helv 16 Tf 22 TL 1 0 0 1 40 762 Tm (First line) Tj '+ending+b' ET')
    chosen=next(w for w in inspect_words(original,0) if w['text']=='word');assert chosen['editable']
    changed=edit(original,chosen,'term')
    assert [w[4] for w in word_boxes(changed)]==['First','line','next','term','here']
    before,after=word_boxes(original),word_boxes(changed)
    for i in [0,1,2,4]:assert before[i][:4]==pytest.approx(after[i][:4],abs=.03)


def test_mixed_style_inside_word_is_readonly():
    doc=fitz.open();p=doc.new_page();p.insert_font(fontname='hebo')
    with pikepdf.open(io.BytesIO(make_pdf())) as pdf:
        with pikepdf.open(io.BytesIO(doc.tobytes())) as font_pdf:
            pdf.pages[0].Resources.Font['/hebo']=pdf.copy_foreign(font_pdf.pages[0].Resources.Font['/hebo'])
        pdf.pages[0].Contents=pdf.make_stream(b'BT /helv 16 Tf 1 0 0 1 40 762 Tm (mi) Tj /hebo 16 Tf (xed) Tj ET')
        out=io.BytesIO();pdf.save(out)
    words=inspect_words(out.getvalue(),0)
    assert words[0]['text']=='mixed' and not words[0]['editable']


def test_word_edit_survives_other_pdf_tools_and_stream_cleanup():
    original=make_pdf('Original contract remains')
    chosen=inspect_words(original,0)[0]
    changed=edit(original,chosen,'Revised',size=18,color='#cc1133')
    changed=engine.apply(changed,'text',{'text':'Added note','x':40,'y':150})
    changed=engine.apply(changed,'compress',{})
    assert [w[4] for w in word_boxes(changed)]==['Revised','contract','remains','Added','note']
    words=inspect_words(changed,0)
    assert all(w['editable'] for w in words)
    changed=edit(changed,next(w for w in words if w['text']=='contract'),'agreement')
    changed=engine.apply(changed,'metadata',{'metadata':{'title':'Actual word edits'}})
    assert [w[4] for w in word_boxes(changed)][:3]==['Revised','agreement','remains']
    with pikepdf.open(io.BytesIO(changed)) as pdf:
        inside=False
        for ins in pikepdf.parse_content_stream(pdf.pages[0]):
            op=str(ins.operator)
            if op=='BT':inside=True
            elif op=='ET':inside=False
            elif op in ('Tj','TJ'):assert inside,'Text must remain inside a text object after cleanup.'


def test_legacy_run_replacement_survives_cleanup_without_losing_following_text():
    from backend.content import inspect,replace
    original=stream_pdf(b'BT /helv 16 Tf 1 0 0 1 40 762 Tm (Original) Tj 0 1 0 rg (Following) Tj ET')
    run=next(s for s in inspect(original,0) if s['text']=='Original')
    changed=replace(original,0,run['id'],'Revised',18,'#223355')
    changed=engine.apply(changed,'compress',{})
    with fitz.open(stream=changed,filetype='pdf') as doc:
        text=doc[0].get_text()
        assert 'Revised' in text and 'Following' in text and 'Original' not in text
