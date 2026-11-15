import {useEffect,useRef,useState} from 'react';

// Four current-revision pages only. Documents and old revisions are discarded.
export function usePageWords({api,session,page,version,pageCount,setError}) {
 const cache=useRef({key:null,pages:new Map()}),[result,setResult]=useState(null);
 const key=`${session}:${version}`;
 useEffect(()=>{
  if(!session){cache.current={key:null,pages:new Map()};setResult(null);return}
  if(cache.current.key!==key)cache.current={key,pages:new Map()};
  const pages=cache.current.pages,controller=new AbortController();let active=true,timer;
  const remember=(index,words)=>{pages.delete(index);pages.set(index,words);while(pages.size>4)pages.delete(pages.keys().next().value);return words};
  const load=async index=>{
   if(pages.has(index))return pages.get(index);
   const response=await api(`/document/page/${index}/text?words_only=true`,{signal:controller.signal});
   return remember(index,(await response.json()).words||[]);
  };
  const show=words=>{if(active){setResult({key,page,words});if(page+1<pageCount)timer=setTimeout(()=>load(page+1).catch(()=>{}),350)}};
  if(pages.has(page))show(pages.get(page));
  else load(page).then(show).catch(e=>{if(active)setError(e.message)});
  return()=>{active=false;clearTimeout(timer);controller.abort()};
 },[api,session,page,version,pageCount,key,setError]);
 const ready=!!session&&result?.key===key&&result?.page===page;
 return {spans:ready?result.words:[],textReady:ready};
}
