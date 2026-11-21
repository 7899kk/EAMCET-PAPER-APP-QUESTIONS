// Private per-document resources. No persistent storage or third-party requests.
export function createEditResources(getApi) {
 const fonts=new Map(),patches=new Map();let serial=0,bytes=0,fontBytes=0,pinned='',generation=0;
 const signature=(b,p)=>JSON.stringify([p,b.rect,b.text,b.font_key,b.font_fallback]);
 const trim=()=>{for(const [key,value] of patches){if(patches.size<=96&&bytes<=16*1024*1024)break;if(key===pinned||!value.result)continue;URL.revokeObjectURL(value.result.url);bytes-=value.bytes;patches.delete(key)}};
 const clearPatches=()=>{generation++;for(const entry of patches.values())if(entry.result)URL.revokeObjectURL(entry.result.url);patches.clear();bytes=0;pinned=''};
 const reset=()=>{clearPatches();for(const entry of fonts.values())if(entry.face)document.fonts.delete(entry.face);fonts.clear();fontBytes=0};
 const font=async(b,page)=>{
  const key=JSON.stringify([b.font_key||b.id,b.ascender,b.descender,!!b.font_fallback]);
  if(fonts.has(key))return fonts.get(key).promise;
  const entry={};
  entry.promise=(async()=>{
   let compatible=!!b.font_fallback;
   for(let attempt=0;attempt<2;attempt++){
    const r=await getApi()(`/document/page/${page}/font?block=${encodeURIComponent(b.id)}${compatible?'&compatible=true':''}`,{timeoutMs:20000});
    const buffer=await r.arrayBuffer(),asc=Number(r.headers.get('X-Font-Ascender'))||b.ascender,desc=Number(r.headers.get('X-Font-Descender'))||b.descender;
    try{
     const face=new FontFace('folio-prepared-'+(++serial),buffer,{ascentOverride:`${asc*100}%`,descentOverride:`${Math.abs(desc)*100}%`,lineGapOverride:'0%'});await face.load();
     if(!fonts.has(key)||fonts.get(key)!==entry)throw new Error('Document changed during font preparation.');
     document.fonts.add(face);entry.face=face;entry.bytes=buffer.byteLength;fontBytes+=entry.bytes;
     for(const [oldKey,old] of fonts){if(fonts.size<=32&&fontBytes<=24*1024*1024)break;if(old===entry||!old.face||document.querySelector('.inline-text')?.style.fontFamily?.includes(old.face.family))continue;document.fonts.delete(old.face);fontBytes-=old.bytes;fonts.delete(oldKey)}
     return {face:face.family,ascender:asc,descender:desc,font_fallback:compatible,font_notice:compatible?'A compatible font is used at the same point size because the original font could not be loaded.':b.font_notice};
    }catch(e){if(compatible)throw e;compatible=true}
   }
  })().catch(e=>{if(fonts.get(key)===entry)fonts.delete(key);throw e});fonts.set(key,entry);return entry.promise;
 };
 const patch=async(b,page)=>{
  const key=signature(b,page);if(patches.has(key))return patches.get(key).promise;
  const entry={};const ownGeneration=generation;
  entry.promise=(async()=>{
   const r=await getApi()(`/document/page/${page}/edit-patch?block=${encodeURIComponent(b.id)}`,{timeoutMs:20000});
   const blob=await r.blob(),rect=JSON.parse(r.headers.get('X-Patch-Rect'));
   if(ownGeneration!==generation)throw new Error('Document changed during preview preparation.');
   const url=URL.createObjectURL(blob);try{const img=new Image();img.src=url;await img.decode()}catch(e){URL.revokeObjectURL(url);throw e}
   if(ownGeneration!==generation){URL.revokeObjectURL(url);throw new Error('Document changed during preview preparation.')}
   entry.result={url,rect,key};entry.bytes=blob.size;bytes+=blob.size;trim();return entry.result;
  })().catch(e=>{if(patches.get(key)===entry)patches.delete(key);throw e});patches.set(key,entry);return entry.promise;
 };
 const prepare=async(b,page)=>{const [f,p]=await Promise.all([font(b,page),b.id==='new'?Promise.resolve(null):patch(b,page)]);return {...f,patch:p}};
 const warm=async(blocks,page,progress,cancelled)=>{
  // Bound speculative native parsing/rasterization. Other paragraphs prepare on
  // demand rather than competing with typing and autosaves on a small server.
  const queue=blocks.filter(b=>b.editable).slice(0,8);let index=0,done=0,failures=0,error='';progress(0,queue.length);
  const worker=async()=>{while(index<queue.length&&!cancelled()){const b=queue[index++];try{await prepare(b,page)}catch(e){error=e.message;if(++failures>=3)index=queue.length}if(!cancelled())progress(++done,queue.length)}};
  await Promise.all([worker(),worker()]);return {failures,error};
 };
 return {prepare,warm,reset,clearPatches,pin:key=>{pinned=key||'';trim()}};
}
