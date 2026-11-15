import importlib
import pymupdf as fitz
from fastapi.testclient import TestClient
from backend.app import app,sessions,total_memory
from tests.test_engine import fixture

app_module=importlib.import_module('backend.app')
words_module=importlib.import_module('backend.words')

def upload(client,data=None):
    res=client.post('/api/documents',files={'file':('fast.pdf',data or fixture(),'application/pdf')})
    assert res.status_code==200,res.text
    token=res.json()['token']
    return token,{'X-Session':token}

def test_words_only_cache_reused_for_edit_and_invalidated_for_history(monkeypatch):
    original=app_module.inspect_words;calls=[]
    def counted(data,page):
        calls.append(page);return original(data,page)
    monkeypatch.setattr(app_module,'inspect_words',counted)
    with TestClient(app) as client:
        token,headers=upload(client)
        def words():
            res=client.get('/api/document/page/0/text?words_only=true',headers=headers)
            assert res.status_code==200,res.text
            assert 'spans' not in res.json()
            return res.json()['words']
        before=words();assert words()==before and calls==[0]
        cached=sessions[token];assert cached.analysis_bytes>0
        assert total_memory()==sum(map(len,cached.versions))+cached.analysis_bytes
        # Neither legacy detection nor a second word scan is needed to save.
        def unexpected(*args):raise AssertionError('Unnecessary repeated text scan')
        monkeypatch.setattr(words_module,'inspect_words',unexpected)
        monkeypatch.setattr(app_module.content,'inspect',unexpected)
        word=next(w for w in before if w['text']=='Original')
        res=client.post('/api/document/operation',headers=headers,json={'operation':'replace-word','args':{'id':word['id'],'original':'Original','text':'Revised'}})
        assert res.status_code==200,res.text
        assert not cached.word_cache and cached.analysis_bytes==0
        assert words()[0]['text']=='Revised' and calls==[0,0]
        assert client.post('/api/document/history/undo',headers=headers).status_code==200
        assert words()[0]['text']=='Original' and calls==[0,0,0]
        assert client.post('/api/document/history/redo',headers=headers).status_code==200
        assert words()[0]['text']=='Revised' and calls==[0,0,0,0]

def test_word_cache_is_bounded_and_private():
    with fitz.open() as doc:
        for i in range(8):doc.new_page().insert_text((40,80),f'Private page {i}')
        source=doc.tobytes()
    with TestClient(app) as client:
        token,headers=upload(client,source)
        for i in range(8):
            assert client.get(f'/api/document/page/{i}/text?words_only=true',headers=headers).status_code==200
        s=sessions[token];assert len(s.word_cache)==4 and list(s.word_cache)==[4,5,6,7]
        assert 0<s.analysis_bytes<=4*1024*1024
        _,other=upload(client)
        words=client.get('/api/document/page/0/text?words_only=true',headers=other).json()['words']
        assert words[0]['text']=='Original'
        assert client.delete('/api/document',headers=headers).status_code==200
        assert token not in sessions

def test_single_page_preview_preserves_content_shapes_and_rotation():
    with TestClient(app) as client:
        _,headers=upload(client)
        for operation,args in [('shape-add',{'page':1,'type':'ellipse','rect':[50,180,150,250]}),('rotate',{'page':1})]:
            res=client.post('/api/document/operation',headers=headers,json={'operation':operation,'args':args});assert res.status_code==200
        original=client.get('/api/document/pdf',headers=headers).content
        res=client.get('/api/document/page/1/pdf',headers=headers);assert res.status_code==200
        with fitz.open(stream=res.content,filetype='pdf') as preview:
            assert len(preview)==1 and preview[0].rotation==90
            page=preview[0]
            assert 'Delete this page' in page.get_text()
            assert next(page.annots()).type[0]==fitz.PDF_ANNOT_CIRCLE
            assert page.get_pixmap().width>0
        assert client.get('/api/document/pdf',headers=headers).content==original
        exported=client.post('/api/document/export',headers=headers,json={'kind':'pdf'}).content
        with fitz.open(stream=exported,filetype='pdf') as doc:assert len(doc)==3
        assert client.get('/api/document/page/9/pdf',headers=headers).status_code==422
