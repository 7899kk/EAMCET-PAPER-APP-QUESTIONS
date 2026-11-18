import io
import pymupdf as fitz
from fastapi.testclient import TestClient
from backend.app import app

def test_prepared_patch_removes_only_preview_text_and_keeps_real_pdf_unchanged():
    with fitz.open() as doc:
        p=doc.new_page();p.draw_rect((30,30,500,150),fill=(.1,.3,.5),color=(.1,.3,.5));p.insert_text((45,90),'Editable text on a blue background',fontsize=16,color=(1,1,1));source=doc.tobytes()
    with TestClient(app) as c:
        r=c.post('/api/documents',files={'file':('blue.pdf',source)});h={'X-Session':r.json()['token']}
        before=c.get('/api/document/pdf',headers=h).content;b=c.get('/api/document/page/0/blocks',headers=h).json()['blocks'][0]
        patch=c.get('/api/document/page/0/edit-patch',params={'block':b['id']},headers=h)
        assert patch.status_code==200 and patch.content.startswith(b'\x89PNG') and patch.headers['x-patch-rect']
        pix=fitz.Pixmap(patch.content);pixels=pix.samples
        # Reconstructed preview background is blue, not a white cover rectangle.
        assert max(pixels[0::pix.n])<40 and min(pixels[2::pix.n])>110
        assert c.get('/api/document/pdf',headers=h).content==before
        with fitz.open(stream=before,filetype='pdf') as d:assert 'Editable text' in d[0].get_text()
        assert c.get('/api/document/page/0/edit-patch',params={'block':'missing'},headers=h).status_code==422
