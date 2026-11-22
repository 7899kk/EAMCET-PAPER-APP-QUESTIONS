import React,{useRef} from 'react';
import {Move,Copy,Trash2,Bold,Italic} from 'lucide-react';
import {TEXT_FONTS} from './ObjectEditor.jsx';
const variants=[['helv','hebo','heit','hebi'],['tiro','tibo','tiit','tibi'],['cour','cobo','coit','cobi']];
export function TextBoxChrome({model:m,zoom,width,height}){
 const gesture=useRef(null),a=m.active;
 if(!a||a.closing)return null;
 const rect=a.rect,boxWidth=(a.flow_rect||rect)[2]-rect[0],font=TEXT_FONTS.some(([v])=>v===(a.font_code||a.font))?(a.font_code||a.font):a.creation_font||'source';
 const family=variants.find(v=>v.includes(font))||variants[0],index=Math.max(0,family.indexOf(font));
 const begin=(e,resize=false)=>{e.preventDefault();e.stopPropagation();m.pause();e.currentTarget.setPointerCapture(e.pointerId);gesture.current={x:e.clientX,y:e.clientY,resize,rect:[rect[0],rect[1],rect[0]+boxWidth,rect[1]+Math.max(rect[3]-rect[1],(m.element.current?.offsetHeight||0)/zoom)]}};
 const move=e=>{const g=gesture.current;if(!g)return;e.preventDefault();e.stopPropagation();const [x,y,r,b]=g.rect,dx=(e.clientX-g.x)/zoom,dy=(e.clientY-g.y)/zoom;
  let next;if(g.resize)next=[x,y,Math.min(width-4,Math.max(x+32,r+dx)),Math.min(height-4,Math.max(y+16,b+dy))];else{const tx=Math.max(-x,Math.min(width-r,dx)),ty=Math.max(-y,Math.min(height-b,dy));next=[x+tx,y+ty,r+tx,b+ty]}
  m.format({rect:next},false);
 };
 const end=e=>{if(!gesture.current)return;e.stopPropagation();gesture.current=null;m.save()};
 const key=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();const step=e.shiftKey?10:1,dx=e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0,dy=e.key==='ArrowUp'?-step:e.key==='ArrowDown'?step:0;const tx=Math.max(-rect[0],Math.min(width-rect[2],dx)),ty=Math.max(-rect[1],Math.min(height-rect[3],dy));m.format({rect:[rect[0]+tx,rect[1]+ty,rect[2]+tx,rect[3]+ty]})};
 const toolbarWidth=Math.min(450,width*zoom-12),left=Math.max(6,Math.min(rect[0]*zoom,width*zoom-toolbarWidth-6));
 return <>
  <div className="text-format-toolbar" role="toolbar" aria-label="Selected text formatting" style={{left,top:Math.max(4,rect[1]*zoom-51),width:toolbarWidth}} onPointerDown={e=>e.stopPropagation()}>
   <select aria-label="Text box font" value={font} onChange={e=>m.format({font:e.target.value})}>{font==='source'&&<option value="source">Original font</option>}{TEXT_FONTS.map(([v,label])=><option key={v} value={v}>{label}</option>)}</select>
   <input aria-label="Text box font size" type="number" min="4" max="144" value={a.max_size||a.size} onChange={e=>{const n=Number(e.target.value);if(n>=4&&n<=144)m.format({size:n})}}/>
   <button aria-label="Bold text" aria-pressed={index%2===1} onPointerDown={e=>e.preventDefault()} onClick={()=>m.format({font:family[index^1]})}><Bold size={16}/></button>
   <button aria-label="Italic text" aria-pressed={index>=2} onPointerDown={e=>e.preventDefault()} onClick={()=>m.format({font:family[index^2]})}><Italic size={16}/></button>
   <input aria-label="Text box colour" type="color" value={a.color} onChange={e=>m.format({color:e.target.value})}/>
   <button className="text-box-handle" aria-label="Move text box" title="Drag to move; arrow keys move precisely" onPointerDown={e=>begin(e)} onPointerMove={move} onPointerUp={end} onPointerCancel={()=>{gesture.current=null}} onKeyDown={key}><Move size={17}/></button>
   <button aria-label="Duplicate text box" onPointerDown={e=>e.preventDefault()} onClick={m.duplicate}><Copy size={16}/></button>
   <button aria-label="Delete text box" onPointerDown={e=>e.preventDefault()} onClick={m.remove}><Trash2 size={16}/></button>
  </div>
  <button className="text-box-handle text-box-corner" aria-label="Resize text box" title="Drag to change the text frame; font size stays fixed" style={{left:(rect[0]+boxWidth)*zoom-7,top:rect[3]*zoom-7}} onPointerDown={e=>begin(e,true)} onPointerMove={move} onPointerUp={end} onPointerCancel={()=>{gesture.current=null}}/>
 </>;
}
