"""Readable phrase replacement without compression, whiteouts or hidden old text."""
import io
import pikepdf
import pymupdf as fitz
from .words import inspect_words,source_runs,replace_word
from .content import font_width
from . import layers

FONT_NAMES={'Helvetica':'helv','Helvetica-Bold':'hebo','LiberationSans':'helv','LiberationSans-Bold':'hebo','Times-Roman':'tiro','Times-Bold':'tibo','Courier':'cour','Courier-Bold':'cobo'}

def replace_readable(data,page_index,args,word_targets=None):
    text=str(args.get('text',''))
    if len(text)>4000 or any(ord(c)<32 and c not in '\n\t' for c in text):raise ValueError('Enter up to 4000 characters. Spaces and new lines are supported.')
    words=inspect_words(data,page_index) if word_targets is None else word_targets
    word=next((w for w in words if w['id']==args.get('id') and w['editable']),None)
    if word is None or word['text']!=args.get('original'):raise ValueError('This text changed. Select it again.')
    if not text.strip():return replace_word(data,page_index,word['id'],word['text'],'',word_targets=words)
    size=float(args.get('size') or word['size']);color=args.get('color') or word['color']
    if not 4<=size<=144:raise ValueError('Font size must be 4–144 pt.')
    box=fitz.Rect(word['bbox'])
    with fitz.open(stream=data,filetype='pdf') as doc,pikepdf.open(io.BytesIO(data)) as pdf:
        page=doc[page_index];_,runs=source_runs(pdf,page_index,page.transformation_matrix)
        run=next(r for r in runs if r['id']==word['parts'][0]['id'])
        first=next(g for g in run['glyphs'] if g['start']==word['parts'][0]['start'])
        # Natural-width edits may expand into genuine whitespace, never a neighbor.
        right=page.rect.width-20
        for other in words:
            r=fitz.Rect(other['bbox'])
            if other is not word and r.x0>=box.x1-.1 and min(r.y1,box.y1)>max(r.y0,box.y0):right=min(right,r.x0-1)
        try:
            reverse={char:code for code,char in run['mapping'].items() if len(char)==1}
            raw=b''.join(reverse[c] for c in text)
            width=(font_width(run['fontobj'],raw,run['mapping'])*size/run['yscale']/1000+len(text)*run['spacing'])*run['hscale']/100*run['xscale']
            aspect=run['hscale']*run['xscale']/(100*run['yscale'])
            fits='\n' not in text and '\t' not in text and .85<=aspect<=1.15 and width<=right-first['origin'][0]+.05 and size<=word['size']+.1
        except (KeyError,ValueError):fits=False
        if fits:return replace_word(data,page_index,word['id'],word['text'],text,args.get('size'),color,False,words)
        obstacles=[fitz.Rect(w['bbox']) for w in words if w is not word]
        obstacles.extend(fitz.Rect(item['bbox']) for item in page.get_image_info())
        obstacles.extend(fitz.Rect(item['rect']) for item in layers.inspect_layers(data,page_index))
        obstacles.extend(a.rect for a in page.annots() or [])
        obstacles.extend(r['rect'] for r in page.get_drawings() if r['rect'].get_area()<page.rect.get_area()*.8)
        font=FONT_NAMES.get(word['font'],'helv')
        chosen=None;heights={}
        y_positions=sorted({round(box.y0,2)}|{round(r.y1+6,2) for r in obstacles if r.y1>=box.y0})
        for y in y_positions:
            for x in dict.fromkeys([box.x0,24.]):
                width=min(400.,page.rect.width-x-24)
                if width<50:continue
                if width not in heights:heights[width]=layers.text_height(text,width,size,font)
                height=heights[width]
                candidate=fitz.Rect(x,y,x+width,y+height)
                if page.rect.contains(candidate) and not any(candidate.intersects(r+(-2,-2,2,2)) for r in obstacles):chosen=candidate;break
            if chosen:break
        if chosen is None:raise ValueError('This replacement needs more free space than the page has. Reduce the font size or add a text box on another page. The original text is unchanged.')
    # Remove the actual encoded original characters before adding the vector box.
    removed=replace_word(data,page_index,word['id'],word['text'],'',word_targets=words)
    moved=abs(chosen.x0-box.x0)>.5 or abs(chosen.y0-box.y0)>.5
    note='Long replacement saved as a readable, wrapped text layer.'
    if moved:note+=' It was placed in free space to avoid covering other content. Drag it to reposition.'
    if word['font'] not in FONT_NAMES:note+=' The text box uses a compatible sans font because its original font cannot be reused for this layout.'
    return layers.add(removed,page_index,{'type':'text','text':text,'font':font,'size':size,'color':color,'rect':list(chosen),'note':note})
