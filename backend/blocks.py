"""Original paragraph detection and fixed-size, font-preserving PDF editing."""
import hashlib,io,re,unicodedata
import pikepdf
import pymupdf as fitz
from fontTools.ttLib import TTFont
from .words import inspect_words,source_runs,_replace_range
from . import layers,richtext
from .content import BASE_FONTS

def _style(span):return (span['font'],round(span['size'],3),span['color'])

def browser_font(raw):
    # Repack sfnt tables with proper four-byte alignment. Some valid PDF subset
    # fonts are rejected by browser OTS despite rendering correctly in MuPDF.
    try:
        font=TTFont(io.BytesIO(raw),recalcBBoxes=False,recalcTimestamp=False)
        out=io.BytesIO();font.save(out);font.close();return out.getvalue()
    except Exception:return raw

def compatible_font(name):
    name=name.lower();bold=any(w in name for w in ('bold','black','heavy','semibold','demi'));italic=any(w in name for w in ('italic','oblique'))
    family='cour' if any(w in name for w in ('courier','mono','consol')) else 'tiro' if any(w in name for w in ('times','serif','georgia','cambria')) else 'helv'
    return {('helv',False,False):'helv',('helv',True,False):'hebo',('helv',False,True):'heit',('helv',True,True):'hebi',('tiro',False,False):'tiro',('tiro',True,False):'tibo',('tiro',False,True):'tiit',('tiro',True,True):'tibi',('cour',False,False):'cour',('cour',True,False):'cobo',('cour',False,True):'coit',('cour',True,True):'cobi'}[(family,bold,italic)]

def font_choice(doc,page,name,resource):
    records=page.get_fonts(full=True)
    record=next((f for f in records if resource and '/'+f[4]==resource),None)
    normalized=lambda s:re.sub('[^a-z0-9]','',re.sub(r'^[A-Z]{6}\+','',s).lower())
    if record is None:
        # A prefix such as Arial must not select Arial-Bold simply because it
        # appears first in the resource dictionary (or the reverse).
        record=next((f for f in records if normalized(f[3])==normalized(name)),None)
    if record is None:
        candidates=[f for f in records if normalized(f[3]).startswith(normalized(name)) or normalized(name).startswith(normalized(f[3]))]
        record=next((f for f in candidates if compatible_font(f[3])==compatible_font(name)),None)
    raw=doc.extract_font(record[0])[-1] if record else b''
    fallback=BASE_FONTS.get(name,compatible_font(name))
    notice=None
    if raw[:4] in (b'\x00\x01\x00\x00',b'OTTO',b'true',b'wOFF',b'wOF2'):
        return record[0],None,None,hashlib.sha256(browser_font(raw)).hexdigest()[:20]
    notice=f'{name} cannot be reused for browser editing. A compatible font is used at the same point size.'
    return record[0] if record else None,fallback,notice,hashlib.sha256(layers.font_buffer(fallback)).hexdigest()[:20]

def inspect_blocks(data,page_index,words=None):
    words=inspect_words(data,page_index) if words is None else words
    owned=layers.inspect_layers(data,page_index)
    with fitz.open(stream=data,filetype='pdf') as doc:
        page=doc[page_index]
        visible=[fitz.Rect(t['bbox']) for t in page.get_texttrace() if t['type']!=3 and t.get('opacity',1)>0]
        groups=[]
        for block in page.get_text('rawdict',flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks']:
            previous=None
            for line in block.get('lines',[]):
                spans=[{**s,'text':''.join(c['c'] for c in s['chars'])} for s in line['spans'] if any(c['c'].strip() for c in s['chars'])]
                if not spans:continue
                uniform=max(s['size'] for s in spans)-min(s['size'] for s in spans)<.1 and tuple(line['dir'])==(1.,0.)
                pieces=[spans] if uniform else [[s] for s in spans]
                for piecespans in pieces:
                    box=fitz.Rect(piecespans[0]['bbox']);text=''.join(s['text'] for s in piecespans).replace('\u00a0',' ')
                    for span in piecespans:box|=fitz.Rect(span['bbox'])
                    main_span=max(piecespans,key=lambda s:len(s['text']));style=_style(main_span);can_join=uniform and previous and previous['style']==style and abs(box.x0-previous['rect'][0])<3 and 0<box.y0-previous['last_y']<style[1]*1.9
                    if can_join:
                        previous['text']+=' '+text;previous['style_spans'].append({**previous['style_spans'][-1],'text':' '});previous['style_spans'].extend(piecespans);previous['rect']=list(fitz.Rect(previous['rect'])|box);previous['origins'].append(piecespans[0]['origin'][1]);previous['last_y']=box.y0;previous['chars'].extend(c for s in piecespans for c in s['chars'])
                    else:
                        previous={'style':style,'style_spans':list(piecespans),'text':text,'rect':list(box),'last_y':box.y0,'origins':[piecespans[0]['origin'][1]],'ascender':main_span['ascender'],'descender':main_span['descender'],'chars':[c for s in piecespans for c in s['chars']],'horizontal':tuple(line['dir'])==(1.,0.),'mixed':len({_style(s) for s in piecespans})>1}
                        groups.append(previous)
                    if not uniform:previous=None
        unique=[]
        for group in groups:
            duplicate=next((g for g in unique if g['text']==group['text'] and all(abs(a-b)<3 for a,b in zip(g['rect'],group['rect']))),None)
            if duplicate:
                duplicate['chars'].extend(group['chars']);duplicate['rect']=list(fitz.Rect(duplicate['rect'])|fitz.Rect(group['rect']));duplicate['style']=group['style']
            else:unique.append(group)
        groups=unique
        output=[];font_cache={}
        for group in groups:
            box=fitz.Rect(group['rect'])
            if any((fitz.Rect(o['rect'])+(-.1,-.1,.1,.1)).contains(box) for o in owned if o['type']=='text'):continue
            contained=[w for w in words if box.contains(fitz.Rect(w['bbox'])) or box.intersects(fitz.Rect(w['bbox'])) and fitz.Rect(w['bbox']).get_area() and (box&fitz.Rect(w['bbox'])).get_area()/fitz.Rect(w['bbox']).get_area()>.98]
            # A decorative duplicate/shadow must not leave a second copy behind.
            overlap=any(other is not group and (box&fitz.Rect(other['rect'])).get_area()>.45*min(box.get_area(),fitz.Rect(other['rect']).get_area()) for other in groups)
            # Word analysis already resolved these resources. Parsing all PDF
            # operands a second time made every page's initial read slower.
            resources={w['font_resource'] for w in contained if w['editable'] and w.get('font_resource')}
            editable=bool(contained and all(w['editable'] for w in contained) and len(resources)==1 and not overlap and not page.rotation)
            resource=next(iter(resources)) if len(resources)==1 else None
            direct=editable
            editable=bool(group['horizontal'] and any(r.intersects(box) for r in visible) and not page.rotation and group['chars'] and not any(unicodedata.bidirectional(c) in ('R','AL','AN') for c in group['text']))
            key=(group['style'][0],resource)
            if key not in font_cache:font_cache[key]=font_choice(doc,page,group['style'][0],resource)
            font_xref,fallback,font_notice,font_key=font_cache[key]
            style_runs=[]
            if len({_style(s) for s in group['style_spans']})>1:
                for span in group['style_spans']:
                    span_box=fitz.Rect(span['bbox'])
                    span_resources={w['font_resource'] for w in contained if w['editable'] and w.get('font_resource') and w['font']==span['font'] and span_box.contains(fitz.Rect(w['bbox']))}
                    span_resource=next(iter(span_resources)) if len(span_resources)==1 else None
                    choice_key=(span['font'],span_resource)
                    if choice_key not in font_cache:font_cache[choice_key]=font_choice(doc,page,span['font'],span_resource)
                    sx,sf,sn,sk=font_cache[choice_key]
                    style_runs.append({'text':span['text'].replace('\u00a0',' '),'font':span['font'],'color':f"#{span['color']:06x}",'font_xref':sx,'fallback_font':sf,'font_key':sk})
                    if sn and not font_notice:font_notice=sn
                style_runs=richtext.merge(style_runs)
                # All runs share the source baseline, including fonts with
                # different ascender metrics at the same point size.
                group['ascender']=(group['origins'][0]-box.y0)/group['style'][1]
                group['descender']=(group['origins'][-1]-box.y1)/group['style'][1]
            identity='block:'+hashlib.sha256((';'.join(w['id'] for w in contained)+group['text']).encode()).hexdigest()[:24]
            origins=group['origins'];size=group['style'][1]
            leading=(origins[1]-origins[0])/size if len(origins)>1 else 1.2
            output.append({'id':identity,'kind':'native','text':group['text'],'rect':group['rect'],'font':group['style'][0],'size':size,'color':f"#{group['style'][2]:06x}",'lineheight':max(1.,min(2.,leading)),'ascender':group['ascender'],'descender':group['descender'],'editable':editable,'word_ids':[w['id'] for w in contained],'font_resource':resource,'font_xref':font_xref,'fallback_font':fallback,'font_notice':font_notice,'font_key':font_key,'auto_width':len(origins)==1,'removal':'operands' if direct else 'glyphs','erase_rects':[list(fitz.Rect(c['bbox'])) for c in group['chars'] if c['c'].strip()],'reason':None if editable else 'This styled/overlapping text or font cannot be safely rebuilt as one paragraph.'})
            if style_runs:output[-1]['style_runs']=style_runs
        for item in owned:
            if item['type']=='text':output.append({'id':'layer:'+item['id'],'kind':'layer','font_code':item['font'],'text':item['text'],'rect':item['rect'],'font':item.get('font_label',item['font']),'size':item['size'],'max_size':item.get('max_size',item['size']),'color':item['color'],'lineheight':item.get('lineheight',1.2),'ascender':item.get('ascender',1.05),'descender':item.get('descender',-.3),'editable':item['editable'],'word_ids':[],'layer_id':item['id'],'min_height':item.get('min_height',fitz.Rect(item['rect']).height),'font_notice':item.get('font_notice'),'font_key':item.get('font_key'),'auto_width':item.get('auto_width',item.get('fixed_frame',False)) and not item.get('manual_width',False)})
        obstacles=layers.flow_obstacles(page)
        for target in output:
            if target['kind']=='layer':
                item=next(o for o in owned if o['id']==target['layer_id'])
                if item.get('style_runs'):target['style_runs']=item['style_runs']
            if target['editable']:
                single_line=target.get('auto_width',False)
                target['flow_rect']=layers.flow_rect(page,target['rect'],single_line,obstacles)
        return output

def find_block(data,page_index,identity,blocks=None):
    if identity.startswith('layer:'):
        return managed_block(data,page_index,identity[6:])
    block=next((b for b in (inspect_blocks(data,page_index) if blocks is None else blocks) if b['id']==identity),None)
    if not block or not block['editable']:raise ValueError('This paragraph changed or cannot be edited safely. Click it again.')
    return block

def managed_block(data,page_index,identity):
    """Resolve our own text object without decoding every native text operand."""
    item=next((m for m in layers.inspect_layers(data,page_index) if m['id']==identity and m['type']=='text'),None)
    if not item or not item['editable']:raise ValueError('This paragraph changed or cannot be edited safely. Click it again.')
    block={'id':'layer:'+item['id'],'kind':'layer','font_code':item['font'],'text':item['text'],'rect':item['rect'],'font':item.get('font_label',item['font']),'size':item['size'],'max_size':item.get('max_size',item['size']),'color':item['color'],'lineheight':item.get('lineheight',1.2),'ascender':item.get('ascender',1.05),'descender':item.get('descender',-.3),'editable':True,'word_ids':[],'layer_id':item['id'],'min_height':item.get('min_height',fitz.Rect(item['rect']).height),'font_notice':item.get('font_notice'),'font_key':item.get('font_key'),'auto_width':item.get('auto_width',item.get('fixed_frame',False)) and not item.get('manual_width',False)}
    if item.get('style_runs'):block['style_runs']=item['style_runs']
    with fitz.open(stream=data,filetype='pdf') as doc:block['flow_rect']=layers.flow_rect(doc[page_index],block['rect'],block['auto_width'])
    return block

def font_for_block(data,page_index,block,run=None):
    if run:
        selected=next((r for r in block.get('style_runs',[]) if r['font_key']==run),None)
        if not selected:raise ValueError('This text style changed. Select it again.')
        if block['kind']=='layer':return layers.fonts_for_layer(data,page_index,block['layer_id'])[run]
        block={**block,**selected}
    if block['kind']=='layer':return layers.font_for_layer(data,page_index,block['layer_id'])
    if block.get('fallback_font'):return layers.font_buffer(block['fallback_font'])
    with fitz.open(stream=data,filetype='pdf') as doc:
        if not block.get('font_xref'):return layers.font_buffer(compatible_font(block['font']))
        return browser_font(doc.extract_font(block['font_xref'])[-1])

def remove_block(data,page_index,block,words=None):
    if block['kind']=='layer':return layers.remove(data,page_index,block['layer_id'])
    if block.get('removal')=='glyphs':
        with fitz.open(stream=data,filetype='pdf') as doc:
            page=doc[page_index]
            if any(a.type[0]==fitz.PDF_ANNOT_REDACT for a in page.annots() or []):raise ValueError('Resolve existing unapplied redaction annotations before rebuilding this text.')
            # Tiny glyph-centre regions remove actual source text (including
            # nested Form text), with no fill, image editing or vector removal.
            for bounds in block['erase_rects']:
                r=fitz.Rect(bounds);centre=(r.tl+r.br)/2
                page.add_redact_annot(fitz.Rect(centre.x-.05,centre.y-.05,centre.x+.05,centre.y+.05),fill=False,cross_out=False)
            page.apply_redactions(images=0,graphics=0,text=0)
            return doc.tobytes(garbage=4,deflate=True)
    words=inspect_words(data,page_index) if words is None else words
    selected=[w for w in words if w['id'] in block['word_ids']]
    if len(selected)!=len(block['word_ids']) or not all(w['editable'] for w in selected):raise ValueError('The paragraph changed. Click it again.')
    with pikepdf.open(io.BytesIO(data)) as pdf,fitz.open(stream=data,filetype='pdf') as doc:
        instructions,runs=source_runs(pdf,page_index,doc[page_index].transformation_matrix);by_id={r['id']:r for r in runs};ranges={}
        for word in selected:
            for part in word['parts']:ranges.setdefault(part['id'],[]).append((part['start'],part['end']))
        for index in sorted(ranges,reverse=True):
            run=by_id[index];intervals=sorted(ranges[index]);start=min(a for a,b in intervals);end=max(b for a,b in intervals)
            covered=set(n for a,b in intervals for n in range(a,b))
            if any(not run['text'][n].isspace() for n in range(start,end) if n not in covered):raise ValueError('This paragraph shares text instructions with another object.')
            instructions[index:index+1]=_replace_range(run,start,end,'',None,None,1,False)
        pdf.pages[page_index].Contents=pdf.make_stream(pikepdf.unparse_content_stream(instructions));out=io.BytesIO();pdf.save(out);return out.getvalue()

def replace_block(data,page_index,args,blocks=None,words=None,duplicate=False):
    block=find_block(data,page_index,args['id'],blocks)
    if block['text']!=args.get('original'):raise ValueError('This paragraph changed. Click it again.')
    text=str(args.get('text',''))
    if len(text)>6000:raise ValueError('Keep a paragraph under 6000 characters.')
    font_bytes=font_for_block(data,page_index,block)
    style_runs=richtext.retarget(block['style_runs'],text) if block.get('style_runs') else None
    style_fonts={}
    if style_runs:
        for run in style_runs:
            raw=font_for_block(data,page_index,block,run['font_key']);face=fitz.Font(fontbuffer=raw)
            if run['font_key'] in args.get('fallback_styles',[]) or any(not c.isspace() and not face.has_glyph(ord(c)) for c in run['text']):
                raw=layers.font_buffer(compatible_font(run['font']));block={**block,'font_notice':'A compatible font is used for characters missing from an original text style.'}
                run['font_key']=hashlib.sha256(raw).hexdigest()[:20]
            style_fonts[run['font_key']]=raw
    face=fitz.Font(fontbuffer=font_bytes)
    if not style_runs and (args.get('font_fallback') or any(not c.isspace() and not face.has_glyph(ord(c)) for c in text)):
        fallback=compatible_font(block['font']);font_bytes=layers.font_buffer(fallback)
        block={**block,'font_notice':f"A compatible full font replaces {block['font']} for browser/glyph support, at the same point size."}
    stripped=data if duplicate else remove_block(data,page_index,block,words)
    if not text.strip():return stripped,None
    identity=None if duplicate else block.get('layer_id')
    rect=args['rect'] if duplicate else [block['rect'][0],block['rect'][1],block.get('flow_rect',block['rect'])[2],block['rect'][3]]
    result=layers.add(stripped,page_index,{'type':'text','id':identity,'text':text,'font':'source','style_runs':style_runs,'font_label':block['font'],'font_notice':block.get('font_notice'),'size':block.get('max_size',block['size']),'max_size':block.get('max_size',block['size']),'color':block['color'],'rect':rect,'min_height':block.get('min_height',fitz.Rect(block['rect']).height),'lineheight':block['lineheight'],'ascender':block['ascender'],'descender':block['descender'],'fixed_frame':True,'auto_width':block.get('auto_width',True)},font_bytes=font_bytes,style_fonts=style_fonts)
    item=next(o for o in layers.inspect_layers(result,page_index) if o['id']==identity) if identity else layers.inspect_layers(result,page_index)[-1]
    return result,managed_block(result,page_index,item['id'])
