"""Occurrence-specific editing of directly embedded PDF raster images."""
import io
import pikepdf
import pymupdf as fitz
from .layers import checked_rect
from . import layers

def _records(pdf,page_index,transform):
    page=pdf.pages[page_index];instructions=list(pikepdf.parse_content_stream(page));resources=page.Resources.get('/XObject',{});matrix=fitz.Matrix(1,0,0,1,0,0);stack=[];records=[]
    for index,ins in enumerate(instructions):
        args,op=ins.operands,str(ins.operator)
        if op=='q':stack.append(fitz.Matrix(matrix))
        elif op=='Q' and stack:matrix=stack.pop()
        elif op=='cm':matrix=fitz.Matrix(*map(float,args))*matrix
        elif op=='Do':
            name=str(args[0]);obj=resources.get(name)
            if obj is None or obj.get('/Subtype')!=pikepdf.Name('/Image'):continue
            rect=fitz.Rect(0,0,1,1)*matrix*transform
            editable=abs(matrix.b)<.001 and abs(matrix.c)<.001 and abs(matrix.a)>.001 and abs(matrix.d)>.001
            records.append({'id':f'image:{index}:{name}','index':index,'resource':name,'matrix':matrix,'rect':list(rect),'editable':editable,'xref':obj.objgen[0]})
    return instructions,records

def inspect_images(data,page_index):
    with pikepdf.open(io.BytesIO(data)) as pdf,fitz.open(stream=data,filetype='pdf') as doc:
        if not 0<=page_index<len(doc):raise ValueError('Invalid page.')
        page=doc[page_index];_,records=_records(pdf,page_index,page.transformation_matrix*page.rotation_matrix)
        return [{'id':r['id'],'type':'image','source':'native','rect':r['rect'],'editable':r['editable'] and not page.rotation} for r in records]

def change(data,page_index,args,delete=False):
    with pikepdf.open(io.BytesIO(data)) as pdf,fitz.open(stream=data,filetype='pdf') as doc:
        if not 0<=page_index<len(doc):raise ValueError('Invalid page.')
        page=doc[page_index];instructions,records=_records(pdf,page_index,page.transformation_matrix)
        item=next((r for r in records if r['id']==args.get('id')),None)
        if not item or not item['editable'] or page.rotation:raise ValueError('This image changed or has an unsupported transformation.')
        if not delete:
            rect=checked_rect(page,args['rect']);info=doc.extract_image(item['xref']);image=info['image']
            if info['width']*info['height']>25_000_000:raise ValueError('Image exceeds 25 megapixels.')
            if info.get('smask'):
                pix=fitz.Pixmap(doc,item['xref']);mask=fitz.Pixmap(doc,info['smask']);image=fitz.Pixmap(pix,mask).tobytes('png')
            removed=change(data,page_index,args,delete=True)
            return layers.add(removed,page_index,{'type':'image','rect':list(rect),'note':'Original image converted to a movable rectangular layer. Original clipping effects are not retained.'},image)
        index=item['index'];resource=item['resource']
        if delete:
            del instructions[index]
            if not any(str(i.operator)=='Do' and str(i.operands[0])==resource for i in instructions):
                pageobj=pdf.pages[page_index];pageobj.Resources=pikepdf.Dictionary(pageobj.Resources);objects=pikepdf.Dictionary(pageobj.Resources.XObject);del objects[resource];pageobj.Resources.XObject=objects
        else:
            rect=checked_rect(page,args['rect'])*~page.transformation_matrix
            old=item['matrix'];sx=1 if old.a>0 else -1;sy=1 if old.d>0 else -1
            target=fitz.Matrix(rect.width*sx,0,0,rect.height*sy,rect.x0 if sx>0 else rect.x1,rect.y0 if sy>0 else rect.y1)
            delta=target*~old
            make=lambda a,o:pikepdf.ContentStreamInstruction(a,pikepdf.Operator(o))
            instructions[index:index+1]=[make([],'q'),make(list(delta),'cm'),instructions[index],make([],'Q')]
        pdf.pages[page_index].Contents=pdf.make_stream(pikepdf.unparse_content_stream(instructions));out=io.BytesIO();pdf.save(out);return out.getvalue()
