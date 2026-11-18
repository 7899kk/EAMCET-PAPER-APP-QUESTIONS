"""Movable vector text, image and highlighter objects saved as PDF Form XObjects.

The metadata belongs to the object, so it survives saving/reopening. Deletion
removes the drawing instruction and its resource, rather than hiding the object.
"""
import io,json,math,re,uuid,hashlib
from functools import lru_cache
from pathlib import Path
import pikepdf
import pymupdf as fitz
from PIL import Image

FONTS={'helv','hebo','heit','hebi','tiro','tibo','tiit','tibi','cour','cobo','coit','cobi'}
FONT_FILES={'helv':'LiberationSans-Regular.ttf','hebo':'LiberationSans-Bold.ttf','tiro':'LiberationSerif-Regular.ttf','tibo':'LiberationSerif-Bold.ttf','cour':'LiberationMono-Regular.ttf','cobo':'LiberationMono-Bold.ttf','heit':'LiberationSans-Italic.ttf','hebi':'LiberationSans-BoldItalic.ttf','tiit':'LiberationSerif-Italic.ttf','tibi':'LiberationSerif-BoldItalic.ttf','coit':'LiberationMono-Italic.ttf','cobi':'LiberationMono-BoldItalic.ttf'}

@lru_cache(maxsize=12)
def font_buffer(name):return (Path(__file__).with_name('fonts')/FONT_FILES[name]).read_bytes()

def insert_unicode_font(page):
    xref=page.insert_font(fontname='FolioText',fontbuffer=font_buffer('helv'))
    normalize_space_map(page.parent,xref)
    return xref

def normalize_space_map(doc,xref):
    kind,value=doc.xref_get_key(xref,'ToUnicode')
    if kind=='xref':
        stream=int(value.split()[0]);raw=doc.xref_stream(stream)
        normalized=re.sub(rb'(?im)^(<[0-9a-f]+>[ \t]+)<00a0>[ \t]*$',rb'\g<1><0020>',raw)
        if normalized!=raw:doc.update_stream(stream,normalized)

def draw_text(page,rect,text,font,size,color=(0,0,0),font_bytes=None,lineheight=1.2):
    # Embed licensed Unicode-capable fonts. Base-14's simple encoding
    # silently substituted question marks for curly quotes and em dashes.
    xref=page.insert_font(fontname='FolioText',fontbuffer=font_bytes or font_buffer(font))
    normalize_space_map(page.parent,xref)
    return page.insert_textbox(rect,text,fontname='FolioText',fontsize=size,color=color,lineheight=lineheight)

def rgb(color):
    if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):raise ValueError('Invalid colour.')
    return tuple(int(color[i:i+2],16)/255 for i in (1,3,5))

def checked_rect(page,values):
    if not isinstance(values,(list,tuple)) or len(values)!=4 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):raise ValueError('Invalid layer rectangle.')
    rect=fitz.Rect(values)
    if rect.is_empty or not page.rect.contains(rect) or min(rect.width,rect.height)<3:raise ValueError('Keep the layer inside the page, at least 3 points wide and high.')
    if page.rotation:raise ValueError('Rotate this page to 0° before editing layers.')
    return rect

def text_style(args,font_bytes=None):
    text=str(args.get('text',''))
    if not text.strip() or len(text)>6000:raise ValueError('Enter text, up to 6000 characters. Spaces and new lines are supported.')
    if any(ord(c)<32 and c not in '\n\t' for c in text):raise ValueError('Unsupported control character.')
    try:text.encode('cp1252')
    except UnicodeError:raise ValueError('Text boxes currently support Western Latin characters. Other scripts need a compatible shaping/font engine.')
    font=args.get('font','helv');size=float(args.get('size',16))
    if font not in FONTS and not(font=='source' and font_bytes):raise ValueError('Choose an available font.')
    if not math.isfinite(size) or not 4<=size<=144:raise ValueError('Font size must be 4–144 pt.')
    if font_bytes:
        face=fitz.Font(fontbuffer=font_bytes)
        missing=next((c for c in text if not c.isspace() and not face.has_glyph(ord(c))),None)
        if missing:raise ValueError(f'The original embedded font lacks {missing!r}. Remove that character or choose another font under Layers.')
    return text.replace('\t','    '),font,size,rgb(args.get('color','#263449'))

def text_height(text,width,size,font,font_bytes=None,lineheight=1.2):
    # Use MuPDF's actual layout result, not a character-count approximation.
    with fitz.open() as doc:
        page=doc.new_page(width=max(width,10),height=16000)
        remaining=draw_text(page,(0,0,width,16000),text,font,size,font_bytes=font_bytes,lineheight=lineheight)
        if remaining<0:raise ValueError('This text needs more room.')
        return max(size*1.5,16000-remaining+2)

def frame_lines(text,width,size,face):
    lines=[]
    for paragraph in text.split('\n'):
        line=''
        for token in re.findall(r'\S+|[^\S\n]+',paragraph):
            if face.text_length(line+token,fontsize=size)<=width+.01:line+=token;continue
            if line.strip():lines.append(line.rstrip());line=''
            token=token.lstrip()
            for char in token:
                if face.text_length(line+char,fontsize=size)>width+.01:
                    if not line:raise ValueError('This area is too narrow for the selected font.')
                    lines.append(line);line=''
                line+=char
        lines.append(line.rstrip())
    return lines

def flow_obstacles(page):
    items=[fitz.Rect(w[:4]) for w in page.get_text('words')]
    items.extend(fitz.Rect(i['bbox']) for i in page.get_image_info())
    items.extend(fitz.Rect(d['rect']) for d in page.get_drawings())
    items.extend(fitz.Rect(a.rect) for a in page.annots() or [])
    return items

def flow_rect(page,values,expand_width=False,obstacles=None):
    """Available column area; never shift unrelated page objects."""
    original=fitz.Rect(values);bounds=page.rect
    right=max(original.x1,bounds.x1-max(12,min(52,original.x0))) if expand_width else original.x1
    bottom=max(original.y1,bounds.y1-12)
    obstacles=flow_obstacles(page) if obstacles is None else obstacles
    for r in obstacles:
        # Ignore the paragraph's own glyphs, and respect containing panels.
        if original.contains(r):continue
        if r.contains(original):
            right=min(right,max(original.x1,r.x1-3));bottom=min(bottom,max(original.y1,r.y1-3));continue
        if expand_width and r.x0>=original.x1-.1 and r.y0<original.y1 and r.y1>original.y0:
            right=min(right,max(original.x1,r.x0-3))
    for r in obstacles:
        if original.contains(r) or r.contains(original):continue
        if r.x1>original.x0+.1 and r.x0<right-.1 and r.y0>=original.y1-.1:
            bottom=min(bottom,max(original.y1,r.y0-3))
    return [original.x0,original.y0,right,bottom]

def _objects(pdf,page_index):
    page=pdf.pages[page_index]
    used={str(i.operands[0]) for i in pikepdf.parse_content_stream(page) if str(i.operator)=='Do'}
    for name,obj in page.Resources.get('/XObject',{}).items():
        if str(name) not in used or '/FolioLayer' not in obj:continue
        try:
            raw=str(obj.FolioLayer)
            if len(raw)>150000:continue
            meta=json.loads(raw)
            if meta.get('schema')==1 and meta.get('type') in ('text','image','brush'):yield str(name),obj,meta
        except (ValueError,TypeError,RecursionError):continue

def inspect_layers(data,page_index):
    with pikepdf.open(io.BytesIO(data)) as pdf,fitz.open(stream=data,filetype='pdf') as doc:
        if not 0<=page_index<len(doc):raise ValueError('Invalid page.')
        page=doc[page_index];result=[]
        for _,obj,meta in _objects(pdf,page_index):
            original=fitz.Rect(meta['rect'])
            rect=fitz.Rect(list(map(float,obj.BBox)))*fitz.Matrix(*map(float,obj.get('/Matrix',[1,0,0,1,0,0])))*page.transformation_matrix*page.rotation_matrix
            meta={**meta,'rect':list(rect),'editable':not bool(page.rotation)}
            if meta['type']=='brush' and not page.rotation and list(rect)!=list(original):
                meta['points']=[[rect.x0+(x-original.x0)*rect.width/original.width,rect.y0+(y-original.y0)*rect.height/original.height] for x,y in meta['points']]
            result.append(meta)
        return result

def _save(pdf):
    out=io.BytesIO();pdf.save(out);return out.getvalue()

def remove(data,page_index,identity):
    with pikepdf.open(io.BytesIO(data)) as pdf:
        if not 0<=page_index<len(pdf.pages):raise ValueError('Invalid page.')
        found=next((item for item in _objects(pdf,page_index) if item[2]['id']==identity),None)
        if not found:raise ValueError('This layer no longer exists. Select it again.')
        name,_,_=found;page=pdf.pages[page_index]
        instructions=[i for i in pikepdf.parse_content_stream(page) if not(str(i.operator)=='Do' and str(i.operands[0])==name)]
        page.Contents=pdf.make_stream(pikepdf.unparse_content_stream(instructions))
        page.Resources=pikepdf.Dictionary(page.Resources)
        objects=pikepdf.Dictionary(page.Resources.XObject);del objects[name];page.Resources.XObject=objects
        return _save(pdf)

def add(data,page_index,args,extra=None,font_bytes=None):
    kind=args.get('type','text');meta={'schema':1,'id':args.get('id') or uuid.uuid4().hex,'type':kind}
    with fitz.open(stream=data,filetype='pdf') as doc,fitz.open() as source:
        if not 0<=page_index<len(doc):raise ValueError('Invalid page.')
        page=doc[page_index]
        if page.rotation:raise ValueError('Rotate this page to 0° before placing content.')
        if kind=='text':
            text,font,size,color=text_style(args,font_bytes);lineheight=float(args.get('lineheight',1.2))
            if not 1<=lineheight<=2.5:raise ValueError('Invalid line spacing.')
            if 'rect' in args:rect=checked_rect(page,args['rect'])
            else:
                x=float(args.get('x',52));y=float(args.get('y',72));width=min(float(args.get('width',320)),page.rect.width-x-12)
                if width<20:raise ValueError('Click further from the right edge to leave room for text.')
                height=text_height(text,width,size,font)
                rect=checked_rect(page,[x,y,x+width,y+height])
            height=text_height(text,rect.width,size,font,font_bytes,lineheight)
            if args.get('fixed_frame'):
                # Keep the chosen font size. Grow down and wrap; never auto-shrink.
                size=float(args.get('max_size',size))
                if not math.isfinite(size) or not 4<=size<=144:raise ValueError('Font size must be 4–144 pt.')
                face=fitz.Font(fontbuffer=font_bytes or font_buffer(font));asc=float(args.get('ascender',face.ascender));desc=float(args.get('descender',face.descender))
                needed=(asc-desc)*size+max(0,len(frame_lines(text,rect.width,size,face))-1)*lineheight*size
                available=flow_rect(page,rect)
                minimum=float(args.get('min_height',rect.height))
                target=max(minimum,needed)
                if rect.y0+target>available[3]+.02:
                    raise ValueError('This paragraph needs more text space at its current font size. Widen or move its layer, or shorten the text; your draft is preserved. Font size was not reduced.')
                rect=checked_rect(page,[rect.x0,rect.y0,rect.x1,rect.y0+target])
            elif height>rect.height+.1:
                # Resizing a text layer reflows at its font size, never stretches glyphs.
                rect=checked_rect(page,[rect.x0,rect.y0,rect.x1,rect.y0+height])
            p=source.new_page(width=rect.width,height=rect.height)
            if args.get('fixed_frame'):
                xref=p.insert_font(fontname='FolioText',fontbuffer=font_bytes or font_buffer(font));normalize_space_map(p.parent,xref)
                for i,line in enumerate(frame_lines(text,rect.width,size,face)):
                    if line:p.insert_text((0,(asc+i*lineheight)*size),line,fontname='FolioText',fontsize=size,color=color)
            elif draw_text(p,p.rect,text,font,size,color,font_bytes,lineheight)<-.01:raise ValueError('The text needs a larger box; no changes were saved.')
            meta.update({'text':text,'font':font,'size':size,'color':args.get('color','#263449'),'font_key':hashlib.sha256(font_bytes or font_buffer(font)).hexdigest()[:20]})
            for key in ('fixed_frame','max_size','lineheight','font_label','ascender','descender','min_height','font_notice'):
                if key in args:meta[key]=args[key]
        elif kind=='image':
            rect=checked_rect(page,args['rect'])
            if not extra:raise ValueError('Choose an image.')
            with Image.open(io.BytesIO(extra)) as image:
                if image.width*image.height>25_000_000:raise ValueError('Image exceeds 25 megapixels.')
                buf=io.BytesIO();image.convert('RGBA' if 'A' in image.getbands() else 'RGB').save(buf,format='PNG')
            p=source.new_page(width=rect.width,height=rect.height);p.insert_image(p.rect,stream=buf.getvalue(),keep_proportion=True)
        elif kind=='brush':
            points=args.get('points',[]);width=float(args.get('width',16));opacity=float(args.get('opacity',.35));color=rgb(args.get('color','#ffda45'))
            if not .5<=width<=60 or not .05<=opacity<=.8:raise ValueError('Brush width must be 0.5–60 pt and opacity 5–80%.')
            if not 2<=len(points)<=2000 or any(len(p)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in p) for p in points):raise ValueError('Draw a brush stroke on the page.')
            if any(not page.rect.contains(fitz.Point(p)) for p in points):raise ValueError('Keep the stroke inside the page.')
            pad=width/2+1
            bounds=[max(0,min(p[0] for p in points)-pad),max(0,min(p[1] for p in points)-pad),min(page.rect.width,max(p[0] for p in points)+pad),min(page.rect.height,max(p[1] for p in points)+pad)]
            rect=checked_rect(page,args.get('rect',bounds));p=source.new_page(width=rect.width,height=rect.height)
            p.draw_polyline([(x-rect.x0,y-rect.y0) for x,y in points],color=color,width=width,lineCap=1,lineJoin=1,stroke_opacity=opacity)
            meta.update({'points':points,'width':width,'opacity':opacity,'color':args.get('color','#ffda45')})
        else:raise ValueError('Unsupported layer type.')
        meta['rect']=list(rect)
        if args.get('note'):meta['note']=str(args['note'])[:500]
        page.show_pdf_page(rect,source,0,keep_proportion=False)
        content=doc.xref_stream(page.get_contents()[-1])
        name=re.findall(rb'/([^\s/]+)\s+Do',content)[-1].decode('ascii')
        result=doc.tobytes(garbage=4,deflate=True)
    with pikepdf.open(io.BytesIO(result)) as pdf:
        pdf.pages[page_index].Resources.XObject['/'+name].FolioLayer=pikepdf.String(json.dumps(meta,separators=(',',':')))
        if font_bytes:
            if len(font_bytes)>5*1024*1024:raise ValueError('Embedded font exceeds the supported size.')
            pdf.pages[page_index].Resources.XObject['/'+name].FolioFont=pdf.make_stream(font_bytes)
        return _save(pdf)

def font_for_layer(data,page_index,identity):
    with pikepdf.open(io.BytesIO(data)) as pdf:
        item=next((o for o in _objects(pdf,page_index) if o[2]['id']==identity),None)
        if not item:raise ValueError('This text layer no longer exists.')
        _,obj,meta=item
        return obj.FolioFont.read_bytes() if '/FolioFont' in obj else font_buffer(meta['font'])

def update(data,page_index,args):
    old=next((m for m in inspect_layers(data,page_index) if m['id']==args.get('id')),None)
    if not old:raise ValueError('This layer no longer exists. Select it again.')
    merged={**old,**{k:v for k,v in args.items() if k in ('rect','text','font','size','color','width','opacity')}}
    if old['type']=='text' and merged['font']!=old['font'] and merged['font'] in FONTS:
        face=fitz.Font(fontbuffer=font_buffer(merged['font']))
        merged.update(font_label={'helv':'Sans','hebo':'Sans Bold','tiro':'Serif','tibo':'Serif Bold','cour':'Monospace','cobo':'Monospace Bold','heit':'Sans Italic','hebi':'Sans Bold Italic','tiit':'Serif Italic','tibi':'Serif Bold Italic','coit':'Monospace Italic','cobi':'Monospace Bold Italic'}[merged['font']],ascender=face.ascender,descender=face.descender)
    font_bytes=font_for_layer(data,page_index,old['id']) if old.get('font')=='source' and merged.get('font')=='source' else None
    if 'size' in args and old.get('fixed_frame'):merged['max_size']=args['size']
    if old.get('fixed_frame') and 'rect' in args and fitz.Rect(args['rect']).height!=fitz.Rect(old['rect']).height:merged['min_height']=fitz.Rect(args['rect']).height
    if old['type']=='text' and not old.get('fixed_frame') and any(merged[k]!=old[k] for k in ('text','font','size')) and merged['rect']==old['rect']:
        text,font,size,_=text_style(merged);original=fitz.Rect(old['rect'])
        height=max(original.height,text_height(text,original.width,size,font))
        with fitz.open(stream=data,filetype='pdf') as doc:
            page=doc[page_index]
            obstacles=[fitz.Rect(w[:4]) for w in page.get_text('words') if not original.contains(fitz.Rect(w[:4]))]
            obstacles.extend(fitz.Rect(i['bbox']) for i in page.get_image_info())
            obstacles.extend(fitz.Rect(m['rect']) for m in inspect_layers(data,page_index) if m['id']!=old['id'])
            positions=sorted({original.y0}|{r.y1+6 for r in obstacles if r.y1>=original.y0})
            target=None
            for y in positions:
                box=fitz.Rect(original.x0,y,original.x1,y+height)
                if page.rect.contains(box) and not any(box.intersects(r+(-2,-2,2,2)) for r in obstacles):target=box;break
            if target is None:raise ValueError('The expanded text box needs more free space. Move it, widen it or reduce the font size. Your previous text is preserved.')
            merged['rect']=list(target)
    if old['type']=='image':
        with fitz.open(stream=data,filetype='pdf') as doc:
            page=doc[page_index];rect=checked_rect(page,merged['rect']);target=rect*~page.transformation_matrix
        with pikepdf.open(io.BytesIO(data)) as pdf:
            _,obj,_=next(item for item in _objects(pdf,page_index) if item[2]['id']==old['id'])
            bbox=list(map(float,obj.BBox));sx=target.width/(bbox[2]-bbox[0]);sy=target.height/(bbox[3]-bbox[1])
            obj.Matrix=pikepdf.Array([sx,0,0,sy,target.x0-sx*bbox[0],target.y0-sy*bbox[1]])
            obj.FolioLayer=pikepdf.String(json.dumps(merged,separators=(',',':')))
            return _save(pdf)
    if old['type']=='brush' and merged['rect']!=old['rect']:
        a,b=fitz.Rect(old['rect']),fitz.Rect(merged['rect'])
        merged['points']=[[b.x0+(x-a.x0)*b.width/a.width,b.y0+(y-a.y0)*b.height/a.height] for x,y in old['points']]
        merged['width']=max(.5,min(60,old['width']*min(b.width/a.width,b.height/a.height)))
    elif old['type']=='brush' and merged['width']!=old['width']:
        merged.pop('rect',None)
    return add(remove(data,page_index,old['id']),page_index,merged,font_bytes=font_bytes)
