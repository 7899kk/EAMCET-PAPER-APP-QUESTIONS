import React, {useEffect, useRef, useState} from 'react';
import {Square, Circle, Minus, ArrowUpRight, MousePointer2, Trash2, Check} from 'lucide-react';

const types=[['select',MousePointer2,'Select shapes'],['rectangle',Square,'Rectangle'],['ellipse',Circle,'Ellipse'],['line',Minus,'Line'],['arrow',ArrowUpRight,'Arrow']];
export function useShapeEditor({api,session,page,version,current,operation,tool,busy,setError,zoom,surface}) {
 const [shapes,setShapes]=useState([]),[kind,setKind]=useState('rectangle'),[selectedId,setSelectedId]=useState(null),[color,setColor]=useState('#226a52'),[fill,setFill]=useState(''),[width,setWidth]=useState(2),[preview,setPreview]=useState(null);
 const gesture=useRef(null),created=useRef(false);
 const selected=shapes.find(s=>s.id===selectedId);
 useEffect(()=>{setSelectedId(null);setShapes([]);setPreview(null);gesture.current=null},[session,page]);
 useEffect(()=>{
  if(!session)return;let active=true;
  api(`/document/page/${page}/shapes`).then(r=>r.json()).then(data=>{if(!active)return;setShapes(data.shapes);if(created.current){created.current=false;const last=data.shapes.at(-1);if(last){setSelectedId(last.id);setKind('select')}}}).catch(e=>{if(active)setError(e.message)});
  return()=>{active=false};
 },[session,page,version,api]);
 useEffect(()=>{if(selected){setColor(selected.color);setFill(selected.fill||'');setWidth(selected.width)}},[selected]);
 useEffect(()=>{gesture.current=null;setPreview(null)},[tool]);
 const point=e=>{const r=surface.current.getBoundingClientRect();return {x:Math.max(0,Math.min(current.width,(e.clientX-r.left)/zoom)),y:Math.max(0,Math.min(current.height,(e.clientY-r.top)/zoom))}};
 const choose=k=>{setKind(k);setSelectedId(null);setPreview(null)};
 const select=s=>{setSelectedId(s.id);setKind('select')};
 const start=(e,shape=null,resize=false)=>{
  if(busy||tool!=='shapes')return;
  if(current.rotation){setError('Rotate the page back to 0° before editing shapes.');return}
  if(!shape&&kind==='select'){setSelectedId(null);return}
  e.preventDefault();e.stopPropagation();e.currentTarget.setPointerCapture(e.pointerId);
  if(shape){setSelectedId(shape.id);setKind('select')}
  gesture.current={start:point(e),shape,resize};
 };
 const move=e=>{
  const g=gesture.current;if(!g)return;
  const p=point(e);
  if(!g.shape){const r=[Math.min(g.start.x,p.x),Math.min(g.start.y,p.y),Math.max(g.start.x,p.x),Math.max(g.start.y,p.y)];setPreview({type:kind,rect:r,points:[[g.start.x,g.start.y],[p.x,p.y]]});return}
  const s=g.shape,[x0,y0,x1,y1]=s.rect;
  let rect,dx=p.x-g.start.x,dy=p.y-g.start.y;
  if(g.resize)rect=[x0,y0,Math.min(current.width,Math.max(x0+3,x1+dx)),Math.min(current.height,Math.max(y0+3,y1+dy))];
  else{dx=Math.max(-x0,Math.min(current.width-x1,dx));dy=Math.max(-y0,Math.min(current.height-y1,dy));rect=[x0+dx,y0+dy,x1+dx,y1+dy]}
  const points=s.points?.map(([x,y],i)=>g.resize?[rect[0]+(x1===x0?i:(x-x0)/(x1-x0))*(rect[2]-rect[0]),rect[1]+(y1===y0?i:(y-y0)/(y1-y0))*(rect[3]-rect[1])]:[x+dx,y+dy]);
  setPreview({...s,rect,points});
 };
 const end=async()=>{
  const g=gesture.current;if(!g)return;gesture.current=null;
  if(!preview)return;
  const [x0,y0,x1,y1]=preview.rect;
  if(Math.max(x1-x0,y1-y0)<3||(['rectangle','ellipse'].includes(preview.type)&&Math.min(x1-x0,y1-y0)<3)){setPreview(null);return}
  if(!g.shape)created.current=true;
  const saved=await operation(g.shape?'shape-update':'shape-add',{...preview,color:g.shape?g.shape.color:color,fill:g.shape?g.shape.fill:fill||null,width:g.shape?g.shape.width:width},g.shape?'Shape updated in your PDF':'Shape added. Drag it to move; use its corner to resize.');
  if(!saved)created.current=false;
  setPreview(null);
 };
 const style=()=>selected&&operation('shape-update',{...selected,color,fill:fill||null,width},'Shape style saved in your PDF');
 const remove=async()=>{if(selected){await operation('shape-delete',{id:selected.id},'Shape removed from your PDF');setSelectedId(null)}};
 const cancel=()=>{gesture.current=null;setPreview(null)};
 return {shapes,selected,kind,choose,select,color,setColor,fill,setFill,width,setWidth,preview,start,move,end,cancel,style,remove,busy,zoom,current};
}

export function ShapeControls({model:m}) {
 return <div className="shape-controls" aria-label="Shape controls">
  <div className="shape-types" role="group" aria-label="Choose shape type">{types.map(([id,Icon,label])=><button key={id} type="button" className={m.kind===id?'active':''} aria-pressed={m.kind===id} onClick={()=>m.choose(id)} disabled={m.busy}><Icon size={16}/>{label}</button>)}</div>
  <div className="shape-style"><label>Border<input type="color" aria-label="Shape border colour" value={m.color} onChange={e=>m.setColor(e.target.value)}/></label><label>Width<input type="number" aria-label="Shape border width" min="0.5" max="12" step="0.5" value={m.width} onChange={e=>m.setWidth(+e.target.value)}/></label><label><input type="checkbox" aria-label="Fill shape" checked={!!m.fill} onChange={e=>m.setFill(e.target.checked?'#e5f1ea':'')}/>Fill</label>{m.fill&&<input type="color" aria-label="Shape fill colour" value={m.fill} onChange={e=>m.setFill(e.target.value)}/>} {m.selected&&<><button className="button primary" onClick={m.style} disabled={m.busy}><Check size={14}/>Apply style</button><button className="button shape-delete" onClick={m.remove} disabled={m.busy}><Trash2 size={14}/>Delete shape</button></>}</div>
  <p>{m.selected?'Shape selected. Drag to move it. Drag the corner handle to resize.':m.kind==='select'?`${m.shapes.length} selectable shapes. Click one on the page.`:`Drag on the page to draw a ${m.kind}.`}</p>
 </div>;
}

export function ShapeLayer({model:m}) {
 const z=m.zoom;
 return <>
  {m.shapes.map((s,i)=>{const r=m.preview?.id===s.id?m.preview.rect:s.rect,selected=m.selected?.id===s.id;return <div key={s.id} className={'shape-object '+(selected?'shape-selected':'')} style={{left:r[0]*z,top:r[1]*z,width:Math.max((r[2]-r[0])*z,4),height:Math.max((r[3]-r[1])*z,4),pointerEvents:m.kind==='select'||selected?'auto':'none'}}><button className="shape-hit" aria-label={`Select ${s.type} ${i+1}`} onPointerDown={e=>m.start(e,s)} onClick={()=>m.select(s)} disabled={!s.editable} title={s.reason||'Select and drag this shape'}/>{selected&&<button className="shape-resize" aria-label="Resize selected shape" title="Drag to resize" onPointerDown={e=>m.start(e,s,true)}/>}</div>})}
  {m.preview&&<svg className="shape-preview" width={m.current.width*z} height={m.current.height*z} aria-hidden="true"><ShapeDrawing shape={m.preview} zoom={z} color={m.preview.color||m.color} fill={m.preview.fill||m.fill} width={m.preview.width||m.width}/></svg>}
 </>;
}
function ShapeDrawing({shape:s,zoom:z,color,fill,width}) {
 const [x0,y0,x1,y1]=s.rect.map(v=>v*z),style={stroke:color,fill:fill||'none',strokeWidth:width*z};
 if(s.type==='rectangle')return <rect x={x0} y={y0} width={x1-x0} height={y1-y0} {...style}/>;
 if(s.type==='ellipse')return <ellipse cx={(x0+x1)/2} cy={(y0+y1)/2} rx={(x1-x0)/2} ry={(y1-y0)/2} {...style}/>;
 const points=s.points||[[x0/z,y0/z],[x1/z,y1/z]];
 return <line x1={points[0][0]*z} y1={points[0][1]*z} x2={points[1][0]*z} y2={points[1][1]*z} {...style}/>;
}
