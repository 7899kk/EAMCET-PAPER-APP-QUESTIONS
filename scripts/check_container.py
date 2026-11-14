"""Test a built image on loopback, without printing the temporary password."""
import io,os,secrets,subprocess,time,zipfile
from pathlib import Path
import httpx
import pymupdf as fitz

DOCKER=['docker','--host=unix:///var/run/docker.sock']
environment=os.environ.copy()
for key in ['DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH']: environment.pop(key,None)
environment['FOLIO_PREVIEW_PASSWORD']=secrets.token_urlsafe(32)
name='folio-check-'+secrets.token_hex(4)
started=False
try:
 subprocess.run(DOCKER+['run','--rm','-d','--name',name,'-e','FOLIO_PREVIEW_PASSWORD','-p','127.0.0.1:10001:10000','folio-pdf:hosting-check'],env=environment,check=True,capture_output=True);started=True
 base='http://127.0.0.1:10001'
 for _ in range(40):
  try:
   if httpx.get(base+'/api/health',timeout=1).status_code==200:break
  except httpx.TransportError:pass
  time.sleep(.25)
 else:raise RuntimeError('Container did not become ready.')
 assert httpx.get(base+'/').status_code==401
 with httpx.Client(base_url=base,auth=('folio',environment['FOLIO_PREVIEW_PASSWORD']),timeout=30) as client:
  assert client.get('/').status_code==200
  assert 'eng' in client.get('/api/health').json()['ocr_languages']
  response=client.get('/source.zip');response.raise_for_status()
  with zipfile.ZipFile(io.BytesIO(response.content)) as archive:assert 'pdf-studio/backend/app.py' in archive.namelist()
  assert subprocess.check_output(DOCKER+['exec',name,'id','-u'],env=environment,text=True).strip()=='10001'
  root=Path(__file__).resolve().parent.parent
  uploaded=client.post('/api/documents',files={'file':('test.pdf',(root/'tests/artifacts/selectable.pdf').read_bytes(),'application/pdf')});uploaded.raise_for_status();headers={'X-Session':uploaded.json()['token']}
  span=client.get('/api/document/page/0/text',headers=headers).json()['spans'][0];assert span['editable']
  for op,args in [('replace',{'id':span['id'],'text':'Hosted engine verified'}),('text',{'text':'Saved in Docker','x':72,'y':150}),('pages',{'indices':[0,2]}),('rotate',{'page':1})]:
   response=client.post('/api/document/operation',headers=headers,json={'operation':op,'args':args});response.raise_for_status()
  output=client.post('/api/document/export',headers=headers,json={'kind':'pdf'});output.raise_for_status()
  destination=root/'tests/artifacts/container-downloaded.pdf';destination.write_bytes(output.content)
  with fitz.open(stream=output.content,filetype='pdf') as doc:
   assert len(doc)==2 and doc[1].rotation==90
   assert 'Hosted engine verified' in doc[0].get_text() and 'Saved in Docker' in doc[0].get_text()
   assert 'Original contract' not in doc[0].get_text()
  independent=subprocess.check_output(['pdftotext',str(destination),'-'],text=True)
  assert 'Hosted engine verified' in independent and 'Original contract' not in independent
 print('Container check passed: non-root execution, authenticated UI/API, Tesseract, source download, real PDF upload/edit/page operations/download, independent reopen.')
finally:
 if started:subprocess.run(DOCKER+['rm','-f',name],env=environment,capture_output=True)
