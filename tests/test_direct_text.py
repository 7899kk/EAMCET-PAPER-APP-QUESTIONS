import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.layers import inspect_layers

def test_direct_text_style_geometry_and_content_save_together():
 with TestClient(app) as c:
  h={'X-Session':c.post('/api/documents/blank').json()['token']}
  def edit(args):
   r=c.post('/api/document/inline-edit',headers=h,json={'operation':'replace-block','args':{'page':0,**args}});assert r.status_code==200,r.text
   return r.json()['inline_block']
  b=edit({'id':'new','text':'Direct text','rect':[50,80,370,110],'font':'helv','size':16})
  for size,font,text in [(24,'cobo','Direct text in bold mono'),(20,'tiit','Direct text in italic serif')]:
   b=edit({'id':b['id'],'original':b['text'],'text':text,'box_style':{'font':font,'size':size,'color':'#cc3333','rect':[80,120,350,180]}})
   assert b['size']==size and b['font_code']==font and b['rect'][0]==80
  data=c.post('/api/document/export',headers=h,json={'kind':'pdf'}).content
  obj=inspect_layers(data,0)[0];assert obj['font']=='tiit' and obj['text']=='Direct text in italic serif'
  with fitz.open(stream=data,filetype='pdf') as d:
   assert 'Direct text in italic serif' in d[0].get_text()
   assert 'Direct text in bold mono' not in d[0].get_text()

def test_stale_direct_style_cannot_overwrite_text():
 with TestClient(app) as c:
  h={'X-Session':c.post('/api/documents/blank').json()['token']}
  r=c.post('/api/document/inline-edit',headers=h,json={'operation':'replace-block','args':{'page':0,'id':'new','text':'Keep me','rect':[50,80,370,110]}});b=r.json()['inline_block']
  r=c.post('/api/document/inline-edit',headers=h,json={'operation':'replace-block','args':{'page':0,'id':b['id'],'original':'stale','text':'Lost','box_style':{'size':24}}})
  assert r.status_code==422
  with fitz.open(stream=c.get('/api/document/pdf',headers=h).content,filetype='pdf') as d:assert 'Keep me' in d[0].get_text()

def test_first_save_uses_latest_style_even_before_browser_font_finishes_loading():
 with TestClient(app) as c:
  h={'X-Session':c.post('/api/documents/blank').json()['token']}
  r=c.post('/api/document/inline-edit',headers=h,json={'operation':'replace-block','args':{'page':0,'id':'new','text':'Latest style wins','rect':[50,80,370,110],'font':'helv','size':16,'box_style':{'font':'cobo','size':24,'color':'#cc3333','rect':[80,120,400,180]}}})
  assert r.status_code==200,r.text
  data=c.get('/api/document/pdf',headers=h).content
  obj=inspect_layers(data,0)[0];assert obj['font']=='cobo' and obj['size']==24 and obj['rect'][0]==80
  with fitz.open(stream=data,filetype='pdf') as d:
   assert any(s['font']=='LiberationMono-Bold' and s['size']==24 for b in d[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'])
