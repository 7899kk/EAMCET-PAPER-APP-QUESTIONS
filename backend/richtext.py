"""Style inheritance and fixed-size wrapping for mixed-font PDF paragraphs."""
from difflib import SequenceMatcher
import re


def merge(runs):
    result=[]
    for run in runs:
        if not run['text']:continue
        style={k:v for k,v in run.items() if k!='text'}
        if result and {k:v for k,v in result[-1].items() if k!='text'}==style:result[-1]['text']+=run['text']
        else:result.append({**style,'text':run['text']})
    return result


def retarget(runs,text):
    """Unchanged characters keep their style; replacements inherit locally."""
    original=''.join(r['text'] for r in runs)
    if original==text:return [dict(r) for r in runs]
    styles=[i for i,r in enumerate(runs) for _ in r['text']]
    output=[]
    for tag,a,b,c,d in SequenceMatcher(None,original,text).get_opcodes():
        if tag=='equal':
            output.extend({**runs[styles[a+i]],'text':char} for i,char in enumerate(text[c:d]))
        elif tag in ('replace','insert'):
            at=a if tag=='replace' or a<len(original) and text[c:c+1].isdigit() and original[a:a+1].isdigit() else max(0,a-1)
            style=runs[styles[min(at,len(styles)-1)]]
            output.append({**style,'text':text[c:d]})
    return merge(output)


def layout(runs,width,size,faces):
    """Return lines of styled fragments, with shared baselines and real widths."""
    text=''.join(r['text'] for r in runs)
    styles=[i for i,r in enumerate(runs) for _ in r['text']]
    lines=[];line=[];used=0
    def fragments(start,end):
        result=[]
        for i in range(start,end):
            key=runs[styles[i]]['font_key'];color=runs[styles[i]]['color']
            if result and result[-1]['font_key']==key and result[-1]['color']==color:result[-1]['text']+=text[i]
            else:result.append({'font_key':key,'color':color,'text':text[i]})
        for r in result:r['width']=faces[r['font_key']].text_length(r['text'],fontsize=size)
        return result
    def finish():
        nonlocal line,used
        lines.append(line);line=[];used=0
    for token in re.finditer(r'\n|[^\S\n]+|\S+',text):
        value=token.group()
        if value=='\n':finish();continue
        pieces=fragments(token.start(),token.end());length=sum(p['width'] for p in pieces)
        if used+length<=width+.01:
            line.extend(pieces);used+=length;continue
        if line:finish()
        if value.isspace():continue
        if length<=width+.01:line.extend(pieces);used=length;continue
        for i in range(token.start(),token.end()):
            piece=fragments(i,i+1)[0]
            if used+piece['width']>width+.01:
                if not line:raise ValueError('This area is too narrow for the selected font.')
                finish()
            line.append(piece);used+=piece['width']
    finish()
    return lines
