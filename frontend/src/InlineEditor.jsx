import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';

export function useInlineEditor({api,session,page,version,onCommit,setError,canvasMask}) {
 const [blocks,setBlocks]=useState([]),[ready,setReady]=useState(false),[active,setActive]=useState(null),[status,setStatus]=useState(''),[face,setFace]=useState(null),[masked,setMasked]=useState(false),[needsOcr,setNeedsOcr]=useState(false);
 const current=useRef(null),draft=useRef(''),saved=useRef(''),timer=useRef(),flight=useRef(null),element=useRef(),sequence=useRef(0),click=useRef(null),finishRef=useRef(),switching=useRef(false),navigation=useRef(0),selectionIntent=useRef(null);
 useEffect(()=>{navigation.current++;switching.current=false;selectionIntent.current=null;current.current=null;setActive(null);setNeedsOcr(false);setFace(null);setMasked(false);clearTimeout(timer.current);draft.current='';saved.current=''},[session]);
 useEffect(()=>{
  if(!session){setBlocks([]);setReady(false);current.current=null;setActive(null);return}
  let cancelled=false;const controller=new AbortController();setReady(false);
  api(`/document/page/${page}/blocks`,{signal:controller.signal}).then(r=>r.json()).then(data=>{if(!cancelled){setBlocks(data.blocks);setNeedsOcr(!!data.ocr_recommended);setReady(true)}}).catch(e=>{if(!cancelled)setError(e.message)});
  return()=>{cancelled=true;controller.abort()};
 },[api,session,page,version]);
 useEffect(()=>{if(current.current?.page!==page){current.current=null;setActive(null);clearTimeout(timer.current)}},[session,page]);
 const save=async(final=false)=>{
  clearTimeout(timer.current);
  if(flight.current){const ok=await flight.current;if(!ok)return false;if(draft.current!==saved.current)return save(final);return !current.current?.error}
  const a=current.current;if(!a||draft.current===saved.current)return true;
  const text=draft.current;if(!final&&!text.trim())return true;setStatus('Saving…');
  const job=(async()=>{try{
   const result=await(await api('/document/inline-edit',{method:'POST',body:JSON.stringify({operation:'replace-block',args:{page:a.page,id:a.id,original:saved.current,text,rect:a.rect,size:a.size,color:a.color,font_fallback:!!a.font_fallback}})})).json();
   if(current.current?.editSession!==a.editSession)return true;
   saved.current=result.inline_block?.text??text;
   if(current.current===a||current.current?.editSession===a.editSession){
    const next=result.inline_block?{...a,...result.inline_block,error:null}: {...a,id:'deleted',closing:true,error:null};current.current=next;setActive(next);
   }
   onCommit(result);setError('');setStatus(draft.current===text?'All changes saved':'Editing…');return true;
  }catch(e){if(current.current?.editSession!==a.editSession)return false;if(current.current){current.current.error=e.message;setActive({...current.current})}setStatus('Could not save this text');setError(e.message);return false}})();
  flight.current=job;const success=await job;flight.current=null;
  if(success&&draft.current!==saved.current)timer.current=setTimeout(()=>save(),350);
  return success;
 };
 const finish=async()=>{const before=current.current;if(!await save(true))return false;const a=current.current;if(a&&a.editSession===before?.editSession){const next={...a,closing:true};current.current=next;setActive(next)}return true};
 finishRef.current=finish;
 const activate=async(block,point=null)=>{
  if(point){const host=document.querySelector('.pdf-surface')?.getBoundingClientRect();if(host&&point.zoom)point={...point,pdfX:(point.x-host.x)/point.zoom,pdfY:(point.y-host.y)/point.zoom}}
  if(!block.editable){setError(block.reason||'This text structure needs OCR or reconstruction.');return}
  if(current.current?.id===block.id&&!current.current.closing){if(point?.clicks>1){selectionIntent.current={...point,word:true};if(!switching.current)placeSelection()}return}
  const ticket=++navigation.current;switching.current=true;
  if(point)selectionIntent.current={...point,word:point.clicks>1};
  if(!await save(true)){switching.current=false;return}
  if(ticket!==navigation.current)return;
  // Saving another paragraph changes source instruction IDs. Resolve against
  // the current PDF before loading its font and text-free preview.
  if(block.id!=='new'){
   try{const data=await(await api(`/document/page/${page}/blocks`)).json();
    block=data.blocks.find(b=>b.id===block.id)||data.blocks.find(b=>b.text===block.text&&b.rect.every((n,i)=>Math.abs(n-block.rect[i])<.3));
    if(!block)throw new Error('This text changed. Click its current position again.');setBlocks(data.blocks);
   }catch(e){switching.current=false;setError(e.message);return}
  }
  if(ticket!==navigation.current)return;
  setError('');
  const next={...block,size:block.max_size||block.size,page,editSession:++sequence.current,closing:false};current.current=next;draft.current=block.text;saved.current=block.text;click.current=point;setMasked(block.id==='new');setFace(null);setActive(next);setStatus('Preparing text…');
 };
 const blur=()=>{if(!switching.current)return finish()};
 const placeSelection=()=>{
  const el=element.current,intent=selectionIntent.current;if(!el||!intent)return;
  const at=p=>{const host=el.closest('.pdf-surface').getBoundingClientRect(),z=Number(el.dataset.zoom);return document.caretRangeFromPoint?.(p.pdfX===undefined?p.x:host.x+p.pdfX*z,p.pdfY===undefined?p.y:host.y+p.pdfY*z)};
  let range=at(intent);
  if(!range||!el.contains(range.startContainer)){range=document.createRange();range.selectNodeContents(el);range.collapse(false)}
  const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
  if(intent.end){const end=at(intent.end);if(end&&el.contains(end.startContainer))selection.setBaseAndExtent(range.startContainer,range.startOffset,end.startContainer,end.startOffset)}
  else if(intent.word){selection.modify('move','backward','word');selection.modify('extend','forward','word')}
  selectionIntent.current=null;
 };
 useEffect(()=>{
  const move=e=>{if(switching.current&&selectionIntent.current&&e.buttons===1&&Math.hypot(e.clientX-selectionIntent.current.x,e.clientY-selectionIntent.current.y)>4){const host=element.current?.closest('.pdf-surface')?.getBoundingClientRect(),z=Number(element.current?.dataset.zoom);selectionIntent.current.end={x:e.clientX,y:e.clientY,...(host&&z?{pdfX:(e.clientX-host.x)/z,pdfY:(e.clientY-host.y)/z}:{})}}};
  const down=e=>{if(e.detail>1&&selectionIntent.current)selectionIntent.current.word=true};
  const double=e=>{if(!e.target.closest('.paragraph-hit,.inline-text')||e.target.closest('[aria-readonly="true"]'))return;if(switching.current&&selectionIntent.current){selectionIntent.current={...selectionIntent.current,word:true};delete selectionIntent.current.end}else{const host=element.current?.closest('.pdf-surface')?.getBoundingClientRect(),z=Number(element.current?.dataset.zoom);selectionIntent.current={x:e.clientX,y:e.clientY,word:true,...(host&&z?{pdfX:(e.clientX-host.x)/z,pdfY:(e.clientY-host.y)/z}:{})}}if(!switching.current)setTimeout(()=>placeSelection(),0)};
  window.addEventListener('pointermove',move);window.addEventListener('pointerdown',down,true);window.addEventListener('dblclick',double,true);
  return()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerdown',down,true);window.removeEventListener('dblclick',double,true)};
 },[]);
 const createAt=(point,size=16,color='#263449')=>activate({id:'new',kind:'new',text:'',rect:[point.x,point.y,Math.min(point.x+320,point.width-12),Math.min(point.y+110,point.height-12)],font:'Sans',size,color,lineheight:1.2,ascender:1.05,descender:-.3,editable:true});
 useEffect(()=>{
  if(!active)return;let alive=true,loaded;
  const name='folio-inline-'+active.editSession+'-'+(active.font_key||'new')+(active.font_fallback?'-compatible':'');
  api(`/document/page/${active.page}/font?block=${encodeURIComponent(active.id)}${active.font_fallback?'&compatible=true':''}`).then(async r=>({bytes:await r.arrayBuffer(),asc:Number(r.headers.get('X-Font-Ascender'))||active.ascender,desc:Number(r.headers.get('X-Font-Descender'))||active.descender})).then(async ({bytes,asc,desc})=>{
   if(active.id==='new'&&current.current?.editSession===active.editSession){const next={...current.current,ascender:asc,descender:desc};current.current=next;setActive(next)}
   const font=new FontFace(name,bytes,{ascentOverride:`${asc*100}%`,descentOverride:`${Math.abs(desc)*100}%`,lineGapOverride:'0%'});
   await font.load();if(alive){document.fonts.add(font);loaded=font;setFace(name)}
  }).catch(e=>{if(!alive)return;if(!active.font_fallback&&current.current?.editSession===active.editSession){const next={...current.current,font_fallback:true,font_notice:'The browser could not load the original font. A compatible font is used at the same point size.'};current.current=next;setActive(next)}else setError(e.message)});
  return()=>{alive=false;if(loaded)document.fonts.delete(loaded)};
 },[active?.editSession,active?.font_key,active?.font_fallback]);
 useLayoutEffect(()=>{
  if(active&&!active.closing&&canvasMask===active.id)setMasked(true);
  if(active?.closing&&canvasMask===''){current.current=null;setActive(null);setMasked(false);setStatus('All changes saved')}
 },[canvasMask,active?.closing,active?.id]);
 useLayoutEffect(()=>{if(active&&element.current){element.current.textContent=draft.current}},[active?.editSession]);
 useEffect(()=>{
  if(!active||!face||!masked||active.closing||!element.current)return;
  const el=element.current;if(document.activeElement!==el||selectionIntent.current){el.focus({preventScroll:true});placeSelection()}switching.current=false;setStatus(draft.current===saved.current?'All changes saved':'Editing…');
 },[face,masked,active?.editSession]);
 useEffect(()=>()=>clearTimeout(timer.current),[]);
 const input=()=>{
  const el=element.current,a=current.current;draft.current=el?.innerText.replace(/\r/g,'').replace(/\t/g,'    ').replace(/\u00a0/g,' ')||'';
  if(a){a.error=null;el.style.fontSize=(a.max_size||a.size)*Number(el.dataset.zoom)+'px'}
  setStatus('Editing…');clearTimeout(timer.current);timer.current=setTimeout(()=>save(),550);
 };
 const revert=()=>{clearTimeout(timer.current);setError('');draft.current=saved.current;if(element.current)element.current.textContent=saved.current;if(current.current)current.current.error=null;finish()};
 return {blocks,ready,needsOcr,active,face,masked,status,element,activate,createAt,input,save,finish,blur,revert,get dirty(){return draft.current!==saved.current}};
}

export function InlineText({model:m,zoom,canvasMask}) {
 const a=m.active,show=a&&m.face&&m.masked&&!(a.closing&&canvasMask==='');
 return <>
  {(m.ready?m.blocks:[]).filter(b=>b.id!==a?.id).map(b=><div key={b.id} role="textbox" tabIndex={b.editable?0:-1} aria-label={'Edit paragraph: '+b.text.slice(0,85)} aria-readonly={!b.editable} className={'paragraph-hit '+(!b.editable?'paragraph-readonly':'')} style={{left:b.rect[0]*zoom,top:b.rect[1]*zoom,width:(b.rect[2]-b.rect[0])*zoom,height:(b.rect[3]-b.rect[1])*zoom}} onPointerDown={e=>{e.stopPropagation();m.activate(b,{x:e.clientX,y:e.clientY,clicks:e.detail,zoom})}} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();m.activate(b)}}}/>) }
  {a&&<div ref={m.element} data-zoom={zoom} role="textbox" aria-label="Edit text directly on PDF" aria-multiline="true" contentEditable={!a.closing} suppressContentEditableWarning spellCheck={false} className={'inline-text '+(a.error?'inline-error':'')} style={{left:a.rect[0]*zoom,top:(a.rect[1]+((a.ascender-a.descender-a.lineheight)*a.size)/2)*zoom,width:((a.flow_rect||a.rect)[2]-a.rect[0])*zoom,minHeight:(a.rect[3]-a.rect[1])*zoom,maxHeight:Math.max(a.rect[3]-a.rect[1],(a.flow_rect||a.rect)[3]-a.rect[1])*zoom,overflowY:'auto',fontFamily:m.face||'sans-serif',fontSize:(a.max_size||a.size)*zoom,lineHeight:a.lineheight,color:a.color,opacity:show?1:0,pointerEvents:a.closing?'none':'auto'}} onInput={m.input} onPointerDown={e=>e.stopPropagation()} onBlur={()=>m.blur()} onKeyDown={e=>{if(e.key==='Escape'){e.preventDefault();m.revert()}if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();m.finish()}}} onPaste={e=>{e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain').replace(/\t/g,'    '))}}/>}
 </>;
}
