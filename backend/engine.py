import io,zipfile,subprocess,tempfile,os,re,json
import pymupdf as fitz
import pikepdf
from PIL import Image
from .content import replace,inspect
from .words import replace_word
from . import shapes
from . import layers,images,metadata
from .readable import replace_readable

MAX_PAGES=300

def validate(data,password=''):
    if not data.startswith(b'%PDF-'): raise ValueError('Upload a valid PDF file.')
    with fitz.open(stream=data,filetype='pdf') as doc:
        if doc.needs_pass and not doc.authenticate(password): raise ValueError('This PDF needs the correct password. Enter it in the upload dialog.')
        if not 1<=len(doc)<=MAX_PAGES: raise ValueError(f'PDF must contain 1–{MAX_PAGES} pages.')
        for p in doc:
            if p.rect.width>2000 or p.rect.height>2000 or p.rect.width<10 or p.rect.height<10:
                raise ValueError('Page dimensions must be between 10 and 2000 PDF points.')
        # No active content is preserved on upload.
        if doc.is_encrypted or password:
            data=doc.tobytes(garbage=4,deflate=True,encryption=fitz.PDF_ENCRYPT_NONE)
    with pikepdf.open(io.BytesIO(data)) as pdf:
        for key in ('/OpenAction','/AA','/AcroForm','/Collection'):
            if key in pdf.Root: del pdf.Root[key]
        names=pdf.Root.get('/Names',{})
        for key in ('/JavaScript','/EmbeddedFiles'):
            if key in names: del names[key]
        for obj in pdf.objects:
            if isinstance(obj,(pikepdf.Dictionary,pikepdf.Stream)):
                for key in ('/A','/AA','/OpenAction','/JS'):
                    if key in obj: del obj[key]
        excluded={'/Widget','/RichMedia','/Movie','/Sound','/Screen','/FileAttachment','/3D'}
        for page in pdf.pages:
            if '/Annots' in page.obj:
                page.obj.Annots=pikepdf.Array([a for a in page.obj.Annots if str(a.get('/Subtype','')) not in excluded])
        out=io.BytesIO(); pdf.save(out); return out.getvalue()

def rgb(value):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',value): raise ValueError('Invalid colour.')
    return tuple(int(value[i:i+2],16)/255 for i in (1,3,5))

def rect_for(page,coords):
    rect=fitz.Rect(coords)
    if rect.is_empty or rect.is_infinite or not page.rect.contains(rect): raise ValueError('The rectangle must fit inside the page.')
    return rect

def apply(data,op,args,extra=None,word_targets=None):
    if op=='metadata':return metadata.edit(data,args.get('metadata',{}),args.get('custom'))
    if op=='clear-metadata':return metadata.clear(data)
    page_index=int(args.get('page',0))
    if op=='replace-readable':return replace_readable(data,page_index,args,word_targets)
    if op in ('text','stamp'):return layers.add(data,page_index,{**args,'type':'text'})
    if op=='image':return layers.add(data,page_index,{**args,'type':'image'},extra)
    if op=='brush':return layers.add(data,page_index,{**args,'type':'brush'})
    if op=='layer-update':return images.change(data,page_index,args) if str(args.get('id','')).startswith('image:') else layers.update(data,page_index,args)
    if op=='layer-delete':return images.change(data,page_index,args,True) if str(args.get('id','')).startswith('image:') else layers.remove(data,page_index,str(args['id']))
    if op=='redact':
        # Remove intersected managed objects completely, including their private
        # editing metadata. Otherwise redacted text could survive in /FolioLayer.
        area=fitz.Rect(args['rect'])
        for item in layers.inspect_layers(data,page_index):
            if area.intersects(fitz.Rect(item['rect'])):data=layers.remove(data,page_index,item['id'])
    if op=='replace-word':
        return replace_word(data,page_index,str(args['id']),args['original'],args['text'],args.get('size'),args.get('color'),args.get('fit',True),word_targets)
    if op=='find-replace':
        find=str(args.get('find','')); replacement=str(args.get('replacement',''))
        if not find or len(find)>500: raise ValueError('Enter search text (up to 500 characters).')
        with fitz.open(stream=data,filetype='pdf') as d: count=len(d)
        changed=0
        for i in range(count):
            matches=[s for s in inspect(data,i) if s['editable'] and find in s['text']]
            for s in sorted(matches,key=lambda s:s['id'],reverse=True):
                data=replace(data,i,s['id'],s['text'].replace(find,replacement)); changed+=1
        if not changed: raise ValueError('No supported editable text matches. Repeated or fragmented text may be read-only.')
        return data
    if op=='replace': return replace(data,page_index,int(args['id']),args['text'],args.get('size'),args.get('color'))
    with fitz.open(stream=data,filetype='pdf') as doc:
        if not 0<=page_index<len(doc): raise ValueError('Invalid page.')
        page=doc[page_index]; color=rgb(args.get('color','#263449')); size=float(args.get('size',16))
        if not 4<=size<=144: raise ValueError('Font size must be 4–144 pt.')
        if op in ('shape-add','shape-update','shape-delete'):
            shapes.apply(page,op,args,rgb)
        elif op=='pages':
            indices=args['indices']
            if not isinstance(indices,list) or not 1<=len(indices)<=MAX_PAGES or any(type(i)!=int or not 0<=i<len(doc) for i in indices): raise ValueError('Invalid page order; keep at least one page.')
            doc.select(indices)
        elif op=='rotate': page.set_rotation((page.rotation+int(args.get('angle',90)))%360)
        elif op in ('merge','insert'):
            clean=validate(extra,args.get('password',''))
            with fitz.open(stream=clean,filetype='pdf') as other:
                if len(doc)+len(other)>MAX_PAGES: raise ValueError('Combined PDF exceeds 300 pages.')
                doc.insert_pdf(other,start_at=int(args.get('at',len(doc))))
        elif op in ('rectangle','highlight','redact','crop','line'):
            rect=rect_for(page,args['rect'])
            if page.rotation and op!='crop': raise ValueError('Rotate this page back to 0° before drawing on it.')
            if op=='rectangle': page.draw_rect(rect,color=color,width=2)
            elif op=='line': page.draw_line(rect.tl,rect.br,color=color,width=2)
            elif op=='highlight':
                annot=page.add_highlight_annot(rect); annot.set_colors(stroke=color); annot.update()
            elif op=='redact':
                page.add_redact_annot(rect,fill=(0,0,0)); page.apply_redactions(images=2,graphics=2,text=0)
                # Redaction output is fully rewritten below with garbage collection.
            else:
                if page.rotation: raise ValueError('Rotate to 0° before cropping.')
                page.set_cropbox(rect)
        elif op=='comment':
            if page.rotation: raise ValueError('Rotate to 0° before placing a comment.')
            annot=page.add_text_annot((float(args.get('x',72)),float(args.get('y',90))),str(args['text'])[:4000]); annot.update()
        elif op in ('numbers','watermark'):
            for i,p in enumerate(doc):
                if op=='numbers': p.insert_text((p.rect.width/2-8,p.rect.height-25),str(i+1),fontsize=11,color=color)
                else: p.insert_text((40,p.rect.height/2),str(args.get('text','DRAFT'))[:100],fontsize=min(size,60),color=color,fill_opacity=.25)
        elif op=='compress': pass
        elif op=='ocr':
            langs=str(args.get('languages','eng'))
            if not langs or not all(v in ocr_languages() for v in langs.split('+')):raise ValueError('The requested Tesseract language is not installed.')
            from .ocr import process
            return process(data,langs,args.get('mode','searchable'),args.get('indices'))[0]
        else: raise ValueError('Unsupported operation.')
        return doc.tobytes(garbage=4,deflate=True,clean=True,encryption=fitz.PDF_ENCRYPT_NONE)

def ocr_languages():
    try:
        p=subprocess.run(['tesseract','--list-langs'],capture_output=True,text=True,timeout=5)
        return [v for v in p.stdout.splitlines()[1:] if v and v!='osd']
    except (FileNotFoundError,subprocess.TimeoutExpired): return []

def zip_files(files):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files: z.writestr(name,data)
    return out.getvalue()

def export(data,kind,args):
    with fitz.open(stream=data,filetype='pdf') as doc:
        indices=args.get('indices',list(range(len(doc))))
        if not indices or len(indices)>MAX_PAGES or any(type(i)!=int or not 0<=i<len(doc) for i in indices): raise ValueError('Invalid selected pages.')
        if kind=='pdf': return data,'application/pdf','pdf'
        if kind=='text': return '\n\n'.join(doc[i].get_text() for i in indices).encode(),'text/plain; charset=utf-8','txt'
        if kind=='images':
            if len(indices)>50: raise ValueError('Export at most 50 images at a time.')
            return zip_files([(f'page-{i+1}.png',doc[i].get_pixmap(dpi=144).tobytes('png')) for i in indices]),'application/zip','zip'
        if kind=='extract-images':
            files=[]; seen=set()
            for i in indices:
                for img in doc[i].get_images():
                    if img[0] not in seen:
                        seen.add(img[0]); obj=doc.extract_image(img[0]); files.append((f'image-{img[0]}.{obj["ext"]}',obj['image']))
            if not files: raise ValueError('No embedded raster images were found.')
            return zip_files(files),'application/zip','zip'
        if kind=='split':
            files=[]
            for i in indices:
                with fitz.open() as part:
                    part.insert_pdf(doc,from_page=i,to_page=i); files.append((f'page-{i+1}.pdf',part.tobytes(garbage=4,deflate=True)))
            return zip_files(files),'application/zip','zip'
        if kind=='extract':
            with fitz.open() as out:
                for i in indices: out.insert_pdf(doc,from_page=i,to_page=i)
                return out.tobytes(garbage=4,deflate=True),'application/pdf','pdf'
        if kind=='protect':
            password=str(args.get('password',''))
            if len(password)<6: raise ValueError('Use a password of at least 6 characters.')
            return doc.tobytes(garbage=4,deflate=True,encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw=password,user_pw=password),'application/pdf','pdf'
        raise ValueError('Conversion is unsupported. Word/Excel export is not implemented.')
