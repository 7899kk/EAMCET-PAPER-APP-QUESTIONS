import React,{useEffect,useRef,useState} from 'react';
export function PassivePage({api,index,version,root,width,height,zoom}){
 const holder=useRef(),[near,setNear]=useState(false),[url,setUrl]=useState('');
 useEffect(()=>{const observer=new IntersectionObserver(entries=>{setNear(entries.some(e=>e.isIntersecting))},{root:root.current,rootMargin:'700px'});if(holder.current)observer.observe(holder.current);return()=>observer.disconnect()},[root]);
 useEffect(()=>{
  if(!near)return;let alive=true,objectURL;const controller=new AbortController();
  api(`/document/page/${index}/view`,{signal:controller.signal}).then(r=>r.blob()).then(blob=>{if(alive){objectURL=URL.createObjectURL(blob);setUrl(objectURL)}}).catch(()=>{});
  return()=>{alive=false;controller.abort();if(objectURL)URL.revokeObjectURL(objectURL);setUrl('')};
 },[api,index,version,near]);
 return <div ref={holder} className="passive-page" style={{width:width*zoom,height:height*zoom}}>{url?<img src={url} alt={'Page '+(index+1)+' preview'} draggable={false}/>:<span>Page {index+1}</span>}</div>;
}
