import React,{useEffect,useRef,useState} from 'react';
import {Layers,Trash2,Check,Move} from 'lucide-react';

export const TEXT_FONTS=[['helv','Sans'],['hebo','Sans Bold'],['heit','Sans Italic'],['hebi','Sans Bold Italic'],['tiro','Serif'],['tibo','Serif Bold'],['tiit','Serif Italic'],['tibi','Serif Bold Italic'],['cour','Monospace'],['cobo','Monospace Bold'],['coit','Monospace Italic'],['cobi','Monospace Bold Italic']];

export function useObjectEditor({api,session,page,version,current,zoom,surface,operation,tool,busy,focus,setError,onSelect}) {
 const [objects,setObjects]=useState([]),[selectedId,setSelectedId]=useState(null),[draft,setDraft]=useState(null),[preview,setPreview]=useState(null);
 const gesture=useRef(null),previewRef=useRef(null),write=useRef(null);const [saving,setSaving]=useState(false);const selected=objects.find(o=>o.id===selectedId);
 useEffect(()=>{setObjects([]);setSelectedId(null);setDraft(null);setPreview(null);gesture.current=null},[session,page]);
 useEffect(()=>{
  if(!session)return;let active=true;
  api(`/document/page/${page}/layers`).then(r=>r.json()).then(data=>{if(active){setObjects(data.layers);if(focus)setSelectedId(focus)}}).catch(e=>{if(active)setError(e.message)});
  return()=>{active=false};
 },[api,session,page,version,focus]);
 useEffect(()=>{setDraft(selected?{...selected}:null)},[selected]);
 useEffect(()=>{gesture.current=null;setPreview(null);if(!['select','layers','text'].includes(tool))setSelectedId(null)},[tool]);
 const select=o=>{setSelectedId(o.id);onSelect(o)};
 const point=e=>{const r=surface.current.getBoundingClientRect();return {x:Math.max(0,Math.min(current.width,(e.clientX-r.left)/zoom)),y:Math.max(0,Math.min(current.height,(e.clientY-r.top)/zoom))}};
 const start=(e,object=null,resize=false)=>{
  if(object)e.stopPropagation();
  if(busy||write.current)return;
  if(!object){setSelectedId(null);return}
  if(!object.editable){setError('Rotate this page to 0° before editing this layer.');return}
  e.preventDefault();e.stopPropagation();e.currentTarget.setPointerCapture(e.pointerId);select(object);previewRef.current=null;gesture.current={start:point(e),object,resize};
 };
 const move=e=>{
  const g=gesture.current;if(!g)return false;
  const p=point(e),[x0,y0,x1,y1]=g.object.rect;let dx=p.x-g.start.x,dy=p.y-g.start.y,rect;
  if(g.resize){
   let w=Math.max(24,x1-x0+dx),h=Math.max(16,y1-y0+dy);
   if(g.object.type==='image')h=w*(y1-y0)/(x1-x0);
   const scale=Math.min(1,(current.width-x0)/w,(current.height-y0)/h);rect=[x0,y0,x0+w*scale,y0+h*scale];
  }else{dx=Math.max(-x0,Math.min(current.width-x1,dx));dy=Math.max(-y0,Math.min(current.height-y1,dy));rect=[x0+dx,y0+dy,x1+dx,y1+dy]}
  previewRef.current={...g.object,rect};setPreview(previewRef.current);return true;
 };
 const end=()=>{
  const g=gesture.current;if(!g)return false;gesture.current=null;
  const next=previewRef.current;previewRef.current=null;
  if(next){
   setSaving(true);
   write.current=(async()=>{try{const ok=await operation('layer-update',{...(g.object.id===selectedId?draft:{}),id:g.object.id,rect:next.rect},g.resize?'Layer resized; text reflows at its font size.':'Layer moved');if(ok)setObjects(list=>list.map(o=>o.id===g.object.id?{...o,...(ok.active_layer||{}),rect:ok.active_layer?.rect||next.rect}:o));return !!ok}finally{setPreview(null);setSaving(false);write.current=null}})();
  }
  return true;
 };
 const changed=()=>selected&&draft&&['text','font','size','color','width','opacity'].some(k=>draft[k]!==selected[k]);
 const save=async()=>{
  if(write.current)return await write.current;
  if(!changed())return true;
  const id=selected.id,values={...draft};setSaving(true);
  write.current=(async()=>{try{const ok=await operation('layer-update',{id,...values},'Layer changes saved in your PDF');if(ok)setObjects(list=>list.map(o=>o.id===id?{...o,...values,...(ok.active_layer||{})}:o));return !!ok}finally{setSaving(false);write.current=null}})();
  return await write.current;
 };
 const remove=async()=>{if(selected&&await operation('layer-delete',{id:selected.id},'Layer deleted from the PDF'))setSelectedId(null)};
 const cancel=()=>{gesture.current=null;setPreview(null)};
 return {saving,flush:async()=>write.current?await write.current:true,objects,selected,draft,setDraft,select,start,move,end,save,remove,cancel,preview,zoom,busy:busy||saving,changed,clear:()=>setSelectedId(null)};
}

export function ObjectControls({model:m}) {
 const d=m.draft;
 return <div className="object-controls" aria-label="PDF layer controls"><div className="object-selector"><Layers size={16}/><label>Layers<select aria-label="Select PDF layer" value={m.selected?.id||''} onChange={e=>{const object=m.objects.find(o=>o.id===e.target.value);if(object)m.select(object)}}><option value="">Choose a layer…</option>{m.objects.map((o,i)=><option key={o.id} value={o.id}>{i+1}. {o.type==='text'?o.text.slice(0,45):o.type==='brush'?'Brush highlight':'Image'}</option>)}</select></label>{m.selected&&<button className="button shape-delete" onClick={m.remove} disabled={m.busy}><Trash2 size={14}/>Delete layer</button>}<span className="object-hint"><Move size={14}/>{m.saving?'Saving box…':m.selected?'Drag to move. Drag the corner to resize.':'Select added text, an image or a brush highlight on the page.'}</span></div>
 {d&&<div className="object-properties">{d.type==='text'&&<><textarea aria-label="Layer text" value={d.text} maxLength={4000} onChange={e=>m.setDraft({...d,text:e.target.value})}/><label>Font<select aria-label="Layer font" value={d.font} onChange={e=>m.setDraft({...d,font:e.target.value})}>{m.selected?.font==='source'&&<option value="source">{d.font_label||"Original embedded font"}</option>}{TEXT_FONTS.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><label>Size<input aria-label="Layer font size" type="number" min="4" max="144" value={d.size} onChange={e=>m.setDraft({...d,size:+e.target.value})}/></label></>}{d.color&&<label>Colour<input aria-label="Layer colour" type="color" value={d.color} onChange={e=>m.setDraft({...d,color:e.target.value})}/></label>}{d.type==='brush'&&<><label>Brush width<input aria-label="Layer brush width" type="number" min="1" max="60" value={d.width} onChange={e=>m.setDraft({...d,width:+e.target.value})}/></label><label>Opacity<input aria-label="Layer opacity" type="number" min="0.05" max="0.8" step="0.05" value={d.opacity} onChange={e=>m.setDraft({...d,opacity:+e.target.value})}/></label></>}{d.type!=='image'&&<button className="button primary" onClick={m.save} disabled={m.busy}><Check size={14}/>Apply layer changes</button>}</div>}</div>;
}

export function ObjectLayer({model:m,textOnly=false,exclude}) {
 const active=useRef();
 useEffect(()=>{if(m.selected)active.current?.scrollIntoView({block:'nearest',inline:'nearest'})},[m.selected?.id]);
 return <>{m.objects.filter(o=>(!textOnly||o.type==='text')&&o.id!==exclude).map((o,i)=>{const r=m.preview?.id===o.id?m.preview.rect:o.rect,selected=m.selected?.id===o.id,z=m.zoom;return <div key={o.id} ref={selected?active:null} className={'object-box '+(textOnly?'added-text-box ':'')+(selected?'object-selected':'')} style={{left:r[0]*z,top:r[1]*z,width:(r[2]-r[0])*z,height:(r[3]-r[1])*z}}><button className="object-hit" disabled={m.busy} aria-label={`Select ${o.type} layer ${i+1}`} title={o.type==='text'?'Edit this text box':`Select ${o.type} layer`} onPointerDown={e=>m.start(e,o)} onClick={()=>m.select(o)}/>{selected&&<button className="object-resize" disabled={m.busy} aria-label="Resize selected layer" onPointerDown={e=>m.start(e,o,true)}/>}</div>})}</>;
}
