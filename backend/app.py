import asyncio,io,json,os,secrets,time,threading
from dataclasses import dataclass,field
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,Form,Header,HTTPException,Request
from fastapi.responses import Response,FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
import pymupdf as fitz
import pikepdf,subprocess
from PIL import UnidentifiedImageError
from pydantic import BaseModel,Field
from contextlib import asynccontextmanager
from . import engine,content
from .words import inspect_words
from .shapes import inspect_shapes
from .sample import sample_pdf
from .auth import COOKIE_NAME,COOKIE_TTL,valid_basic,valid_cookie,sign_cookie

LIMIT=25*1024*1024
MAX_MEMORY=200*1024*1024
TTL=3600
@dataclass
class Session:
    versions:list
    cursor:int=0
    touched:float=field(default_factory=time.time)
    name:str='document.pdf'
    lock:threading.Lock=field(default_factory=threading.Lock)
    @property
    def data(self): return self.versions[self.cursor]

sessions={}; storage_lock=threading.Lock()
@asynccontextmanager
async def lifespan(app):
    async def loop():
        while True:
            await asyncio.sleep(60)
            with storage_lock: cleanup()
    task=asyncio.create_task(loop())
    try: yield
    finally: task.cancel(); sessions.clear()

class OperationBody(BaseModel):
    operation:str
    args:dict=Field(default_factory=dict)
class ExportBody(BaseModel):
    kind:str='pdf'
    args:dict=Field(default_factory=dict)

app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,title='Folio PDF API',version='1.0.0',description='Local PDF processing. Session IDs are bearer secrets. Documents expire after one idle hour.')

def cleanup():
    now=time.time()
    for key in list(sessions):
        if now-sessions[key].touched>TTL: del sessions[key]

def get_session(token):
    with storage_lock:
        cleanup(); session=sessions.get(token)
        if session is None: raise HTTPException(404,'Session expired. Upload your PDF again.')
        session.touched=time.time(); return session

def total_memory(): return sum(sum(len(v) for v in s.versions) for s in sessions.values())

def register(data,name):
    with storage_lock:
        cleanup()
        if total_memory()+len(data)>MAX_MEMORY: raise HTTPException(503,'Memory limit reached. Close another document and retry.')
        token=secrets.token_urlsafe(32); sessions[token]=Session([data],name=Path(name or 'document.pdf').name)
    return token

def commit(s,data):
    if len(data)>50*1024*1024: raise ValueError('Processed PDF exceeds the 50 MB result limit.')
    with storage_lock:
        versions=s.versions[:s.cursor+1]+[data]
        versions=versions[-12:]
        other=total_memory()-sum(map(len,s.versions))
        if other+sum(map(len,versions))>MAX_MEMORY: raise ValueError('Undo history exceeds server memory. Download and reopen your current PDF.')
        s.versions=versions; s.cursor=len(versions)-1

def describe(s):
    with fitz.open(stream=s.data,filetype='pdf') as doc:
        return {'name':s.name,'pages':[{'width':p.rect.width,'height':p.rect.height,'rotation':p.rotation} for p in doc],'bytes':len(s.data),'metadata':doc.metadata,'undo':s.cursor>0,'redo':s.cursor<len(s.versions)-1}

@app.middleware('http')
async def guards(request,call_next):
    password=os.environ.get('FOLIO_PREVIEW_PASSWORD','')
    auth_header=request.headers.get('authorization','')
    authenticated_basic=bool(password and valid_basic(auth_header,password))
    if password and request.url.path != '/api/health':
        authenticated=authenticated_basic if auth_header else valid_cookie(request.cookies.get(COOKIE_NAME,''),password)
        if not authenticated:
            return Response(json.dumps({'detail':'Your editor sign-in expired. Reload this page and sign in again.'}),
                media_type='application/json',status_code=401,
                headers={'WWW-Authenticate':'Basic realm="Folio PDF preview", charset="UTF-8"','Cache-Control':'no-store'})
    if request.method in ('POST','DELETE'):
        origin=request.headers.get('origin')
        expected_origin=(os.environ.get('FOLIO_PUBLIC_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL') or str(request.base_url)).rstrip('/')
        if origin and origin!=expected_origin:
            return Response('Cross-origin writes are not allowed.',status_code=403)
    length=request.headers.get('content-length')
    if length and int(length)>LIMIT+1024*1024: return Response('Upload exceeds 25 MB.',status_code=413)
    response=await call_next(request)
    if authenticated_basic:
        public_url=os.environ.get('FOLIO_PUBLIC_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL') or str(request.base_url)
        response.set_cookie(COOKIE_NAME,sign_cookie(password),max_age=COOKIE_TTL,
            httponly=True,secure=public_url.startswith('https://'),samesite='strict',path='/')
    response.headers['X-Content-Type-Options']='nosniff'; response.headers['Referrer-Policy']='no-referrer'
    if request.url.path.startswith('/api') or request.url.path=='/': response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; worker-src 'self' blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
    return response

@app.exception_handler(KeyError)
@app.exception_handler(UnidentifiedImageError)
@app.exception_handler(pikepdf.PdfError)
@app.exception_handler(fitz.FileDataError)
@app.exception_handler(subprocess.TimeoutExpired)
@app.exception_handler(subprocess.CalledProcessError)
@app.exception_handler(ValueError)
async def invalid(request,exc):
    return Response(json.dumps({'detail':str(exc)}),status_code=422,media_type='application/json')

async def read_file(file):
    data=await file.read(LIMIT+1); await file.close()
    if len(data)>LIMIT: raise HTTPException(413,'File exceeds 25 MB.')
    return data

@app.get('/api/health')
def health(): return {'status':'ok','word_editing':True,'editor_release':'word-shapes-2','editable_shapes':True,'engine':'pikepdf + PyMuPDF','ocr_languages':engine.ocr_languages(),'max_upload_mb':25,'max_pages':300}

@app.get('/api/sample.pdf')
def sample():
    return Response(sample_pdf(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="folio-sample.pdf"'})

@app.post('/api/documents')
async def upload(file:UploadFile=File(...),password:str=Form('')):
    data=await read_file(file); clean=await run_in_threadpool(engine.validate,data,password)
    token=register(clean,file.filename)
    return {'token':token,**describe(get_session(token))}

@app.post('/api/images-to-pdf')
async def images_to_pdf(files:list[UploadFile]=File(...)):
    if not 1<=len(files)<=30: raise ValueError('Choose 1–30 images.')
    images=[await read_file(f) for f in files]
    if sum(map(len,images))>LIMIT: raise ValueError('Combined images exceed 25 MB.')
    def convert():
        doc=fitz.open()
        for data in images:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                if im.width*im.height>25_000_000: raise ValueError('Image exceeds 25 megapixels.')
                buf=io.BytesIO(); im.convert('RGB').save(buf,format='PNG'); w,h=im.size
            page=doc.new_page(width=595,height=842); page.insert_image(page.rect,stream=buf.getvalue(),keep_proportion=True)
        data=doc.tobytes(garbage=4,deflate=True); doc.close(); return data
    data=await run_in_threadpool(convert); token=register(data,'images.pdf'); return {'token':token,**describe(get_session(token))}

@app.get('/api/document')
def info(x_session:str=Header(...)): return describe(get_session(x_session))

@app.get('/api/document/pdf')
def pdf(x_session:str=Header(...)): return Response(get_session(x_session).data,media_type='application/pdf')

@app.get('/api/document/page/{page}/text')
def text(page:int,x_session:str=Header(...)):
    s=get_session(x_session)
    if not 0<=page<len(describe(s)['pages']): raise ValueError('Invalid page.')
    return {'spans':content.inspect(s.data,page),'words':inspect_words(s.data,page)}

@app.get('/api/document/page/{page}/shapes')
def shapes(page:int,x_session:str=Header(...)):
    return {'shapes':inspect_shapes(get_session(x_session).data,page)}

@app.get('/api/document/page/{page}/thumbnail')
def thumbnail(page:int,x_session:str=Header(...)):
    with fitz.open(stream=get_session(x_session).data,filetype='pdf') as doc:
        if not 0<=page<len(doc): raise ValueError('Invalid page.')
        p=doc[page]; return Response(p.get_pixmap(matrix=fitz.Matrix(120/p.rect.width,120/p.rect.width)).tobytes('png'),media_type='image/png')

@app.post('/api/document/operation')
async def operation(body:OperationBody,x_session:str=Header(...)):
    body=body.model_dump(); s=get_session(x_session)
    def work():
        with s.lock:
            data=engine.apply(s.data,body['operation'],body.get('args',{})); commit(s,data); return describe(s)
    return await run_in_threadpool(work)

@app.post('/api/document/file-operation')
async def file_operation(operation:str=Form(...),args:str=Form('{}'),file:UploadFile=File(...),x_session:str=Header(...)):
    extra=await read_file(file); s=get_session(x_session); params=json.loads(args)
    def work():
        with s.lock:
            commit(s,engine.apply(s.data,operation,params,extra)); return describe(s)
    return await run_in_threadpool(work)

@app.post('/api/document/history/{direction}')
def history(direction:str,x_session:str=Header(...)):
    s=get_session(x_session)
    with s.lock:
        target=s.cursor+(-1 if direction=='undo' else 1 if direction=='redo' else 0)
        if direction not in ('undo','redo') or not 0<=target<len(s.versions): raise ValueError('No history in that direction.')
        s.cursor=target; return describe(s)

@app.post('/api/document/export')
async def export(body:ExportBody,x_session:str=Header(...)):
    body=body.model_dump(); s=get_session(x_session)
    data,mime,ext=await run_in_threadpool(engine.export,s.data,body.get('kind','pdf'),body.get('args',{}))
    return Response(data,media_type=mime,headers={'Content-Disposition':f'attachment; filename="folio-export.{ext}"'})

@app.get('/api/document/search')
def search(q:str,x_session:str=Header(...)):
    if not 1<=len(q)<=500: raise ValueError('Search must contain 1–500 characters.')
    with fitz.open(stream=get_session(x_session).data,filetype='pdf') as doc:
        return {'results':[{'page':i,'rects':[list(r) for r in p.search_for(q)]} for i,p in enumerate(doc) if p.search_for(q)]}

@app.delete('/api/document')
def close(x_session:str=Header(...)):
    with storage_lock: sessions.pop(x_session,None)
    return {'closed':True}

@app.get('/source.zip',include_in_schema=False)
def source_download():
    source=Path(__file__).resolve().parent.parent/'source.zip'
    if not source.is_file(): raise HTTPException(404,'Source archive is generated by the Docker build.')
    return FileResponse(source,media_type='application/zip',filename='folio-source.zip')

DIST=Path(__file__).resolve().parent.parent/'frontend'/'dist'
if DIST.exists():
    app.mount('/pdfjs',StaticFiles(directory=DIST/'pdfjs'),name='pdfjs')
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
    @app.get('/')
    def index(): return FileResponse(DIST/'index.html')
