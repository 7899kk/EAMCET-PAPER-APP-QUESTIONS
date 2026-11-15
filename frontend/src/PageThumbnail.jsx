import React,{useEffect,useRef,useState} from 'react';
import {FileText} from 'lucide-react';

export function PageThumbnail({api,index,version}) {
 const element=useRef(),[visible,setVisible]=useState(false),[src,setSrc]=useState(null);
 useEffect(()=>{
  if(!window.IntersectionObserver){setVisible(true);return}
  const observer=new IntersectionObserver(entries=>setVisible(entries[0].isIntersecting),{rootMargin:'200px'});
  observer.observe(element.current);return()=>observer.disconnect();
 },[]);
 useEffect(()=>{
  if(!visible)return;
  const controller=new AbortController();let active=true,url;
  api(`/document/page/${index}/thumbnail`,{signal:controller.signal,priority:'low'}).then(r=>r.blob()).then(blob=>{if(active){url=URL.createObjectURL(blob);setSrc(url)}}).catch(()=>{});
  return()=>{active=false;controller.abort();if(url)URL.revokeObjectURL(url)};
 },[api,index,version,visible]);
 return <span className="thumbnail-preview" ref={element}>{src?<img src={src} alt={`Page ${index+1}`}/>:<FileText size={30}/>}</span>;
}
