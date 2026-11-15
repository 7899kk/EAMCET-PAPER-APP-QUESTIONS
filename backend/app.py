import asyncio,io,json,os,secrets,time,threading
from collections import OrderedDict
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
from . import layers,ocr,blocks,images
from .auth import COOKIE_NAME,COOKIE_TTL,valid_basic,valid_cookie,sign_cookie

LIMIT=25*1024*1024
MAX_MEMORY=200*1024*1024
TTL=3600
ocr_slots=threading.BoundedSemaphore(1)
ocr_tasks=set()
@dataclass
class Session:
    versions:list
    cursor:int=0
    touched:float=field(default_factory=time.time)
    name:str='document.pdf'
    lock:threading.Lock=field(default_factory=threading.Lock)
    word_cache:OrderedDict=field(default_factory=OrderedDict)
    analysis_bytes:int=0
    generation:int=0
    job:dict|None=None
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
    finally:
        task.cancel()
        for s in list(sessions.values()):
            if s.job:s.job['cancel'].set()
        if ocr_tasks:await asyncio.gather(*list(ocr_tasks),return_exceptions=True)
        sessions.clear()

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
        if now-sessions[key].touched>TTL:
            if sessions[key].job:sessions[key].job['cancel'].set()
            del sessions[key]

def get_session(token):
    with storage_lock:
        cleanup(); session=sessions.get(token)
        if session is None: raise HTTPException(404,'Session expired. Upload your PDF again.')
        session.touched=time.time(); return session

def total_memory(): return sum(sum(len(v) for v in s.versions)+s.analysis_bytes for s in sessions.values())

def clear_analysis(s):
    s.word_cache.clear();s.analysis_bytes=0

def page_blocks(s,page):
    key=('blocks',page)
    if key in s.word_cache:return s.word_cache[key][0]
    result=blocks.inspect_blocks(s.data,page,page_words(s,page));cost=len(json.dumps(result).encode())*4
    with storage_lock:
        while s.word_cache and (len(s.word_cache)>=4 or s.analysis_bytes+cost>4*1024*1024):
            _,(_,removed)=s.word_cache.popitem(last=False);s.analysis_bytes-=removed
        if cost<=4*1024*1024 and total_memory()+cost<=MAX_MEMORY:s.word_cache[key]=(result,cost);s.analysis_bytes+=cost
    return result

def page_words(s,page):
    """Caller holds s.lock. Cache only current-revision words within memory limits."""
    if page in s.word_cache:
        s.word_cache.move_to_end(page)
        return s.word_cache[page][0]
    with fitz.open(stream=s.data,filetype='pdf') as doc:
        if not 0<=page<len(doc):raise ValueError('Invalid page.')
    words=inspect_words(s.data,page)
    cost=len(json.dumps(words).encode())*4
    if cost<=4*1024*1024:
        with storage_lock:
            while s.word_cache and (len(s.word_cache)>=4 or s.analysis_bytes+cost>4*1024*1024 or total_memory()+cost>MAX_MEMORY):
                _,(_,removed)=s.word_cache.popitem(last=False);s.analysis_bytes-=removed
            if total_memory()+cost<=MAX_MEMORY:
                s.word_cache[page]=(words,cost);s.analysis_bytes+=cost
    return words

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
        other=total_memory()-sum(map(len,s.versions))-s.analysis_bytes
        if other+sum(map(len,versions))>MAX_MEMORY: raise ValueError('Undo history exceeds server memory. Download and reopen your current PDF.')
        clear_analysis(s);s.versions=versions; s.cursor=len(versions)-1;s.generation+=1

def ensure_idle(s):
    if s.job and s.job['state']=='running':raise HTTPException(409,'OCR is running. Wait for it to finish or cancel it before editing.')

def changed_info(s,before,operation,args):
    result=describe(s)
    if operation in ('replace-readable','text','stamp','image','brush','layer-update'):
        page=int(args.get('page',0));old={m['id'] for m in layers.inspect_layers(before,page)}
        active=next((m for m in reversed(layers.inspect_layers(s.data,page)) if m['id'] not in old or operation=='layer-update' and m['id']==args.get('id')),None)
        if active:
            result['active_layer']=active
            if operation!='layer-update' and active.get('note'):result['notice']=active['note']
    return result

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
def health(): return {'status':'ok','word_editing':True,'editor_release':'inline-paragraphs-5','inline_editing':True,'native_images':True,'editable_layers':True,'brush_highlights':True,'async_ocr':True,'editable_shapes':True,'page_previews':True,'engine':'pikepdf + PyMuPDF','ocr_languages':engine.ocr_languages(),'max_upload_mb':25,'max_pages':300}

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

@app.get('/api/document/page/{page}/pdf')
def page_pdf(page:int,x_session:str=Header(...),exclude_block:str=''):
    s=get_session(x_session);data=s.data
    if exclude_block:
        with s.lock:
            data=s.data;block=blocks.find_block(data,page,exclude_block,page_blocks(s,page));data=blocks.remove_block(data,page,block,page_words(s,page))
    with fitz.open(stream=data,filetype='pdf') as doc,fitz.open() as preview:
        if not 0<=page<len(doc):raise ValueError('Invalid page.')
        preview.insert_pdf(doc,from_page=page,to_page=page,links=False,widgets=False)
        return Response(preview.tobytes(garbage=3,deflate=True),media_type='application/pdf')

@app.get('/api/document/page/{page}/text')
def text(page:int,x_session:str=Header(...),words_only:bool=False):
    s=get_session(x_session)
    with s.lock:
        words=page_words(s,page)
        if words_only:return {'words':words}
        return {'spans':content.inspect(s.data,page),'words':words}

@app.get('/api/document/page/{page}/shapes')
def shapes(page:int,x_session:str=Header(...)):
    return {'shapes':inspect_shapes(get_session(x_session).data,page)}

@app.get('/api/document/page/{page}/layers')
def layer_list(page:int,x_session:str=Header(...)):
    s=get_session(x_session)
    return {'layers':layers.inspect_layers(s.data,page)+images.inspect_images(s.data,page)}

@app.get('/api/document/page/{page}/blocks')
def text_blocks(page:int,x_session:str=Header(...)):
    s=get_session(x_session)
    with s.lock:return {'blocks':page_blocks(s,page)}

@app.get('/api/document/page/{page}/font')
def block_font(page:int,block:str,x_session:str=Header(...)):
    s=get_session(x_session)
    with s.lock:
        if block=='new':
            face=fitz.Font(fontbuffer=layers.font_buffer('helv'))
            return Response(layers.font_buffer('helv'),media_type='application/octet-stream',headers={'X-Font-Ascender':str(face.ascender),'X-Font-Descender':str(face.descender)})
        selected=blocks.find_block(s.data,page,block,page_blocks(s,page));data=blocks.font_for_block(s.data,page,selected)
        return Response(data,media_type='application/octet-stream')

@app.post('/api/document/inline-edit')
async def inline_edit(body:OperationBody,x_session:str=Header(...)):
    s=get_session(x_session);args=body.args;page=int(args.get('page',0))
    def work():
        with s.lock:
            ensure_idle(s)
            if args.get('id')=='new':
                face=fitz.Font(fontbuffer=layers.font_buffer('helv'))
                result=layers.add(s.data,page,{'type':'text','text':args['text'],'rect':args['rect'],'size':args.get('size',16),'max_size':args.get('size',16),'color':args.get('color','#263449'),'font':'helv','font_label':'Sans','ascender':face.ascender,'descender':face.descender,'fixed_frame':True})
                block=next(b for b in reversed(blocks.inspect_blocks(result,page)) if b['kind']=='layer')
            else:result,block=blocks.replace_block(s.data,page,args,page_blocks(s,page),page_words(s,page))
            commit(s,result)
            return {**describe(s),'inline_block':block}
    return await run_in_threadpool(work)

@app.post('/api/document/ocr')
async def start_ocr(body:ExportBody,x_session:str=Header(...)):
    s=get_session(x_session);args=body.args;langs=str(args.get('languages','eng'));mode=args.get('mode','searchable')
    available=engine.ocr_languages()
    if args.get('scope','all') not in ('all','current'):raise ValueError('Choose all pages or current page for OCR.')
    if not langs or not all(l in available for l in langs.split('+')):raise ValueError('The selected OCR language is not installed on this server.')
    if mode not in ('searchable','editable'):raise ValueError('Invalid OCR mode.')
    with s.lock:
        ensure_idle(s)
        if not ocr_slots.acquire(blocking=False):raise HTTPException(503,'Another OCR job is running. Please retry shortly.')
        data=s.data;generation=s.generation;cancel=threading.Event()
        job={'id':secrets.token_urlsafe(16),'state':'running','completed':0,'total':len(describe(s)['pages']) if args.get('scope','all')=='all' else 1,'message':'Starting local OCR…','cancel':cancel}
        s.job=job
    def run():
        try:
            def progress(completed,total,message):job.update(completed=completed,total=total,message=message)
            result,summary=ocr.process(data,langs,mode,None if args.get('scope','all')=='all' else [int(args.get('page',0))],progress,cancel)
            with s.lock:
                if cancel.is_set() or s.generation!=generation or sessions.get(x_session) is not s:raise ocr.Cancelled()
                commit(s,result)
            job.update(state='complete',summary=summary,message=f"OCR complete: {summary['words']} words across {summary['pages']} pages.")
        except ocr.Cancelled:job.update(state='cancelled',message='OCR cancelled. Your previous PDF is preserved.')
        except Exception as exc:job.update(state='failed',message=str(exc) if isinstance(exc,ValueError) else 'OCR failed. Your previous PDF is preserved.')
        finally:ocr_slots.release()
    async def worker():await run_in_threadpool(run)
    task=asyncio.create_task(worker());ocr_tasks.add(task);task.add_done_callback(ocr_tasks.discard)
    return {'id':job['id'],'state':job['state']}

@app.get('/api/document/ocr')
def ocr_status(x_session:str=Header(...)):
    s=get_session(x_session)
    if not s.job:raise HTTPException(404,'No OCR job is running.')
    result={k:v for k,v in s.job.items() if k!='cancel'}
    if result['state']=='complete':result['document']=describe(s)
    return result

@app.delete('/api/document/ocr')
def cancel_ocr(x_session:str=Header(...)):
    s=get_session(x_session)
    if s.job:s.job['cancel'].set()
    return {'cancel_requested':True}

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
            ensure_idle(s)
            args=body.get('args',{})
            targets=page_words(s,int(args.get('page',0))) if body['operation'] in ('replace-word','replace-readable') else None
            before=s.data;data=engine.apply(before,body['operation'],args,word_targets=targets); commit(s,data); return changed_info(s,before,body['operation'],args)
    return await run_in_threadpool(work)

@app.post('/api/document/file-operation')
async def file_operation(operation:str=Form(...),args:str=Form('{}'),file:UploadFile=File(...),x_session:str=Header(...)):
    extra=await read_file(file); s=get_session(x_session); params=json.loads(args)
    def work():
        with s.lock:
            ensure_idle(s);before=s.data;commit(s,engine.apply(before,operation,params,extra)); return changed_info(s,before,operation,params)
    return await run_in_threadpool(work)

@app.post('/api/document/history/{direction}')
def history(direction:str,x_session:str=Header(...)):
    s=get_session(x_session)
    with s.lock:
        ensure_idle(s)
        target=s.cursor+(-1 if direction=='undo' else 1 if direction=='redo' else 0)
        if direction not in ('undo','redo') or not 0<=target<len(s.versions): raise ValueError('No history in that direction.')
        with storage_lock:
            clear_analysis(s);s.cursor=target;s.generation+=1
        return describe(s)

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
    with storage_lock:
        s=sessions.pop(x_session,None)
        if s and s.job:s.job['cancel'].set()
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
