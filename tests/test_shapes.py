import io,subprocess
import pytest,pymupdf as fitz,pikepdf
from fastapi.testclient import TestClient
from backend import engine
from backend.app import app,sessions
from backend.sample import sample_pdf
from backend.shapes import inspect_shapes
from backend.words import inspect_words

@pytest.mark.parametrize('kind',['rectangle','ellipse','line','arrow'])
def test_shape_create_move_resize_style_and_delete(kind,tmp_path):
    original=sample_pdf()
    data=engine.apply(original,'shape-add',{'type':kind,'rect':[80,340,220,420],'fill':'#ffeecc','width':3})
    shape=inspect_shapes(data,0)[0]
    assert shape['type']==kind and shape['editable'] and shape['width']==3
    moved={**shape,'rect':[120,380,300,490],'color':'#ff0000','fill':'#00ff00','width':5}
    if shape['points']:moved['points']=[[120,380],[300,490]]
    data=engine.apply(data,'shape-update',moved)
    updated=inspect_shapes(data,0)[0]
    assert updated['id']==shape['id'] and updated['color']=='#ff0000' and updated['width']==5
    assert updated['rect']==pytest.approx(moved['rect'],abs=.01)
    # Independent reader verifies real persisted PDF annotation and appearance.
    with pikepdf.open(io.BytesIO(data)) as pdf:
        annot=pdf.pages[0].Annots[0]
        assert '/AP' in annot and list(annot.C)==[1,0,0]
        if kind=='arrow':assert str(annot.LE[1])=='/ClosedArrow'
    path=tmp_path/'shape.pdf';path.write_bytes(data)
    subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','600','-png',str(path),str(tmp_path/'visible')],check=True,capture_output=True)
    from PIL import Image
    with Image.open(tmp_path/'visible.png') as image:
        pixels=list(image.convert('RGB').getdata())
        assert any(r>180 and g<80 and b<80 for r,g,b in pixels)
    # Shape survives a genuine content rewrite followed by compression.
    word=next(w for w in inspect_words(data,0) if w['text']=='brown')
    data=engine.apply(data,'replace-word',{'id':word['id'],'original':'brown','text':'red'})
    data=engine.apply(data,'compress',{})
    assert inspect_shapes(data,0)[0]['id']==shape['id']
    data=engine.apply(data,'shape-delete',{'id':shape['id']})
    assert inspect_shapes(data,0)==[]
    with fitz.open(stream=data,filetype='pdf') as doc:
        assert 'quick red fox' in ' '.join(doc[0].get_text().split())

def test_horizontal_line_and_bad_shapes():
    source=sample_pdf()
    data=engine.apply(source,'shape-add',{'type':'line','rect':[70,350,250,350]})
    assert inspect_shapes(data,0)[0]['rect']==[70,350,250,350]
    for args in [{'type':'circle','rect':[30,30,70,70]}, {'type':'ellipse','rect':[-1,20,70,70]}, {'type':'rectangle','rect':[30,30,70,70],'width':99}, {'type':'rectangle','rect':[30,30,70,70],'fill':'invalid'}]:
        with pytest.raises(ValueError):engine.apply(source,'shape-add',args)
    with pytest.raises(ValueError):engine.apply(data,'shape-delete',{'id':'gone'})

def test_sample_and_shape_api_roundtrip():
    with TestClient(app) as c:
        res=c.get('/api/sample.pdf');assert res.status_code==200 and res.content.startswith(b'%PDF')
        uploaded=c.post('/api/documents',files={'file':('sample.pdf',res.content,'application/pdf')}).json();h={'X-Session':uploaded['token']}
        assert c.get('/api/document/page/0/text',headers=h).json()['words']
        r=c.post('/api/document/operation',headers=h,json={'operation':'shape-add','args':{'type':'ellipse','rect':[80,340,200,420]}})
        assert r.status_code==200,r.text
        shape=c.get('/api/document/page/0/shapes',headers=h).json()['shapes'][0]
        assert shape['type']=='ellipse'
        assert c.post('/api/document/history/undo',headers=h).status_code==200
        assert c.get('/api/document/page/0/shapes',headers=h).json()['shapes']==[]
        assert c.post('/api/document/history/redo',headers=h).status_code==200
        exported=c.post('/api/document/export',headers=h,json={'kind':'pdf'}).content
        assert inspect_shapes(exported,0)[0]['id']==shape['id']
    sessions.clear()
