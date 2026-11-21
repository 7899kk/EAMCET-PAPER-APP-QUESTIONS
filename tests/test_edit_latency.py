"""Managed text saves must not reparse unrelated native text on each keystroke."""
import pytest,pymupdf as fitz
from backend import blocks,ocr
from backend.app import app
from fastapi.testclient import TestClient
from tests.test_extended_editing import scan

@pytest.mark.parametrize('mode',['layout','editable'])
def test_ocr_reconstructs_a_whole_editable_line(mode):
    data,_=ocr.process(scan(),mode=mode)
    block=next(b for b in blocks.inspect_blocks(data,0) if 'Ashok feels happy today.' in b['text'])
    assert block['editable']
    for text in ['Kartik feels enthusiastic today.','Kartik can edit the reconstructed text again.']:
        data,block=blocks.replace_block(data,0,{'id':block['id'],'original':block['text'],'text':text})
        with fitz.open(stream=data,filetype='pdf') as doc:assert text in ' '.join(doc[0].get_text().split())

def test_followup_inline_saves_do_not_decode_unrelated_pdf_operands(monkeypatch):
    with fitz.open() as d:
        d.new_page().insert_text((45,90),'Original text to edit.',fontsize=18);data=d.tobytes()
    with TestClient(app) as c:
        uploaded=c.post('/api/documents',files={'file':('sample.pdf',data)}).json();h={'X-Session':uploaded['token']}
        block=c.get('/api/document/page/0/blocks',headers=h).json()['blocks'][0]
        def save(text):
            r=c.post('/api/document/inline-edit',headers=h,json={'operation':'replace-block','args':{'page':0,'id':block['id'],'original':block['text'],'text':text}});assert r.status_code==200,r.text
            return r.json()['inline_block']
        block=save('First edit.')
        def unexpected(*a,**k):raise AssertionError('Decoded all native operands during a managed-layer save')
        monkeypatch.setattr(blocks,'inspect_words',unexpected)
        monkeypatch.setattr('backend.app.inspect_words',unexpected)
        block=save('Second edit with more words and spaces.')
        assert block['size']==18
        result=c.post('/api/document/export',headers=h,json={'kind':'pdf'}).content
        with fitz.open(stream=result,filetype='pdf') as d:assert block['text'] in ' '.join(d[0].get_text().split())
