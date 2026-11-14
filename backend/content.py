"""Conservative, actual Tj/TJ content operand editing. Never draws cover rectangles."""
import io,re,collections
import pikepdf
import pymupdf as fitz
from fontTools import agl
from fontTools.encodings.StandardEncoding import StandardEncoding

BASE_FONTS={'Helvetica':'helv','Helvetica-Bold':'hebo','Helvetica-Oblique':'heit','Helvetica-BoldOblique':'hebi','Times-Roman':'tiro','Times-Bold':'tibo','Times-Italic':'tiit','Times-BoldItalic':'tibi','Courier':'cour','Courier-Bold':'cobo','Courier-Oblique':'coit','Courier-BoldOblique':'cobi'}

def cmap(font):
    mapping={}; lengths=set()
    if '/ToUnicode' in font:
        source=font.ToUnicode.read_bytes().decode('latin1')
        for block in re.findall(r'beginbfchar(.*?)endbfchar',source,re.S):
            for a,b in re.findall(r'<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>',block):
                try: mapping[bytes.fromhex(a)]=bytes.fromhex(b).decode('utf-16-be')
                except (ValueError,UnicodeError): pass
        for block in re.findall(r'beginbfrange(.*?)endbfrange',source,re.S):
            for a,b,target in re.findall(r'<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*(\[[^\]]*\]|<[0-9a-fA-F]+>)',block,re.S):
                start,end=int(a,16),int(b,16)
                if end-start>65535: continue
                values=re.findall(r'<([0-9a-fA-F]+)>',target)
                for offset,code in enumerate(range(start,end+1)):
                    try:
                        v=values[offset] if target.startswith('[') else f'{int(values[0],16)+offset:0{len(values[0])}x}'
                        mapping[code.to_bytes(len(a)//2,'big')]=bytes.fromhex(v).decode('utf-16-be')
                    except (IndexError,ValueError,UnicodeError): pass
        lengths={len(k) for k in mapping}
        # Variable length codes and vertical writing require a more capable editor.
        if len(lengths)!=1 or str(font.get('/Encoding','')).endswith('-V'): return None
    elif str(font.get('/Subtype')) in ('/Type1','/TrueType'):
        enc=font.get('/Encoding','/StandardEncoding'); differences=[]
        if isinstance(enc,pikepdf.Dictionary): differences=list(enc.get('/Differences',[])); enc=enc.get('/BaseEncoding','/StandardEncoding')
        enc=str(enc)
        for i in range(256):
            try:
                if enc=='/WinAnsiEncoding': char=bytes([i]).decode('cp1252')
                elif enc=='/MacRomanEncoding': char=bytes([i]).decode('mac_roman')
                elif enc=='/StandardEncoding': char=agl.toUnicode(StandardEncoding[i])
                else: return None
                if char: mapping[bytes([i])]=char
            except UnicodeError: pass
        idx=0
        for v in differences:
            if isinstance(v,int): idx=v
            else:
                char=agl.toUnicode(str(v).lstrip('/'))
                if char and idx<256: mapping[bytes([idx])]=char
                idx+=1
    else: return None
    return mapping

def font_width(font,raw,mapping):
    if str(font.get('/Subtype'))=='/Type0':
        if str(font.get('/Encoding'))!='/Identity-H': raise ValueError('Only Identity-H CID fonts are supported.')
        desc=font.DescendantFonts[0]; widths=list(desc.get('/W',[])); default=float(desc.get('/DW',1000)); table={}; i=0
        while i<len(widths):
            start=int(widths[i]); item=widths[i+1]; i+=2
            if isinstance(item,pikepdf.Array):
                for j,w in enumerate(item): table[start+j]=float(w)
            else:
                end=int(item); w=float(widths[i]); i+=1
                if end-start>65535: raise ValueError('Invalid font width range.')
                table.update({j:w for j in range(start,end+1)})
        if len(raw)%2: raise ValueError('Invalid CID text.')
        return sum(table.get(int.from_bytes(raw[j:j+2],'big'),default) for j in range(0,len(raw),2))
    widths=font.get('/Widths'); first=int(font.get('/FirstChar',0))
    if widths is not None:
        return sum(float(widths[b-first]) if 0<=b-first<len(widths) else float(font.get('/FontDescriptor',{}).get('/MissingWidth',0)) for b in raw)
    name=str(font.get('/BaseFont','')).lstrip('/')
    if name not in BASE_FONTS: raise ValueError('Font metrics unavailable.')
    f=fitz.Font(BASE_FONTS[name]); return sum(f.glyph_advance(ord(mapping[bytes([b])] ))*1000 for b in raw)

def runs(pdf,page_index):
    page=pdf.pages[page_index]; instructions=list(pikepdf.parse_content_stream(page)); fonts=page.Resources.get('/Font',{})
    state={'font':None,'size':12.,'spacing':0.,'wordspacing':0.,'render':0,'fill_op':'g','fill_args':[0]}; stack=[]; result=[]
    for idx,ins in enumerate(instructions):
        args,op=ins.operands,str(ins.operator)
        if op=='q': stack.append(state.copy())
        elif op=='Q' and stack: state=stack.pop()
        elif op in ('g','rg','k'): state['fill_op']=op; state['fill_args']=list(args)
        elif op in ('cs','sc','scn'): state['fill_op']=None
        elif op=='Tf': state['font']=str(args[0]); state['size']=float(args[1])
        elif op=='Tc': state['spacing']=float(args[0])
        elif op=='Tw': state['wordspacing']=float(args[0])
        elif op=='Tr': state['render']=int(args[0])
        elif op in ('Tj','TJ'):
            font=fonts.get(state['font']) if state['font'] else None
            if font is None or state['spacing'] or state['wordspacing'] or state['render']!=0: continue
            mapping=cmap(font)
            if not mapping: continue
            parts=[args[0]] if op=='Tj' else list(args[0]); data=b''.join(bytes(x) for x in parts if isinstance(x,pikepdf.String))
            length=len(next(iter(mapping)))
            try:
                decoded=''.join(mapping[data[j:j+length]] for j in range(0,len(data),length))
                width=font_width(font,data,mapping)
            except (KeyError,ValueError,TypeError): continue
            if not decoded.strip(): continue
            result.append(dict(id=idx,text=decoded,fontobj=font,mapping=mapping,width=width,adjust=sum(float(x) for x in parts if not isinstance(x,pikepdf.String)),**state))
    return instructions,result

def inspect(data,page_index):
    with pikepdf.open(io.BytesIO(data)) as pdf, fitz.open(stream=data,filetype='pdf') as doc:
        _,items=runs(pdf,page_index); page=doc[page_index]; spans=[]
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    spans.append({**span,'direction':line['dir']})
        run_counts=collections.Counter(r['text'] for r in items); span_counts=collections.Counter(s['text'] for s in spans)
        lookup={r['text']:r for r in items}; output=[]
        for s in spans:
            r=lookup.get(s['text']); editable=bool(r and run_counts[s['text']]==1 and span_counts[s['text']]==1 and tuple(s['direction'])==(1.,0.) and page.rotation==0 and abs(s['size']-r['size'])<.02)
            output.append({'text':s['text'],'bbox':s['bbox'],'size':s['size'],'font':s['font'],'color':f"#{s['color']:06x}",'editable':editable,'id':r['id'] if editable else None,'reason':None if editable else 'Unsupported font, transformed/fragmented text, or repeated ambiguous text. Use another PDF source; new text is a separate tool.'})
        return output

def replace(data,page_index,run_id,text,size=None,color=None):
    if not text or '\n' in text or len(text)>4000: raise ValueError('Use 1–4000 characters on one line.')
    eligible={s['id'] for s in inspect(data,page_index) if s['editable']}
    if run_id not in eligible: raise ValueError('This text run cannot be safely edited.')
    with pikepdf.open(io.BytesIO(data)) as pdf:
        instructions,items=runs(pdf,page_index); run=next(r for r in items if r['id']==run_id)
        reverse={v:k for k,v in run['mapping'].items() if len(v)==1}
        try: raw=b''.join(reverse[c] for c in text)
        except KeyError as e: raise ValueError(f'The embedded font does not contain {e.args[0]!r}. Choose text using its available glyphs.')
        newsize=float(size or run['size'])
        if not 4<=newsize<=144: raise ValueError('Font size must be 4–144 pt.')
        newwidth=font_width(run['fontobj'],raw,run['mapping'])
        # Preserve the following text position, including original TJ kerning advance.
        adjustment=newwidth-(run['width']-run['adjust'])*run['size']/newsize
        op=lambda args,name:pikepdf.ContentStreamInstruction(args,pikepdf.Operator(name))
        replacement=[op([pikepdf.Name(run['font']),newsize],'Tf')]
        if color:
            if not run['fill_op']: raise ValueError('This colour space cannot be safely restored.')
            if not re.fullmatch(r'#[0-9a-fA-F]{6}',color): raise ValueError('Invalid colour.')
            replacement.append(op([int(color[j:j+2],16)/255 for j in (1,3,5)],'rg'))
        replacement += [op([pikepdf.Array([pikepdf.String(raw),adjustment])],'TJ'),op([pikepdf.Name(run['font']),run['size']],'Tf')]
        if color: replacement.append(op(run['fill_args'],run['fill_op']))
        instructions[run_id:run_id+1]=replacement
        pdf.pages[page_index].Contents=pdf.make_stream(pikepdf.unparse_content_stream(instructions))
        out=io.BytesIO(); pdf.save(out); return out.getvalue()
