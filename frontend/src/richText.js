// Local style inheritance for the typing preview. Saved PDF layout is validated
// independently by the server using its original font bytes and style runs.
export function inheritRuns(runs,text){
 if(!runs?.length)return null;
 const before=runs.map(r=>r.text).join('');if(before===text)return runs;
 let start=0;while(start<before.length&&start<text.length&&before[start]===text[start])start++;
 let end=0;while(end<before.length-start&&end<text.length-start&&before[before.length-1-end]===text[text.length-1-end])end++;
 const styles=runs.flatMap((r,i)=>Array(r.text.length).fill(i));
 const at=start<before.length?start:Math.max(0,start-1),replacement=styles[at]??0;
 const mapped=[...styles.slice(0,start),...Array(text.length-start-end).fill(replacement),...(end?styles.slice(-end):[])];
 const output=[];
 for(let i=0;i<text.length;i++){
  const index=mapped[i]??replacement,previous=output.at(-1);
  if(previous?._index===index)previous.text+=text[i];else output.push({...runs[index],text:text[i],_index:index});
 }
 return output.map(({_index,...r})=>r);
}

export function paintRuns(el,text,runs,faces,preserve=false){
 let offsets=null;const selection=window.getSelection();
 if(preserve&&selection?.anchorNode&&el.contains(selection.anchorNode)&&el.contains(selection.focusNode)){
  const offset=(node,n)=>{const r=document.createRange();r.selectNodeContents(el);r.setEnd(node,n);return r.toString().length};
  offsets=[offset(selection.anchorNode,selection.anchorOffset),offset(selection.focusNode,selection.focusOffset)];
 }
 el.replaceChildren();
 if(!runs?.length)el.textContent=text;
 else for(const run of runs){const span=document.createElement('span');span.textContent=run.text;if(faces?.[run.font_key])span.style.fontFamily=faces[run.font_key];if(run.color)span.style.color=run.color;el.append(span)}
 // Chromium otherwise places typed text before a terminal newline, even when
 // the DOM selection points after it. This UI-only tail gives the empty line
 // a caret position; it is stripped before forming the saved draft.
 if(text.endsWith('\n')){const tail=document.createElement('span');tail.dataset.caretTail='true';tail.setAttribute('aria-hidden','true');tail.textContent='\u200b';el.append(tail)}
 if(offsets){
  const point=offset=>{const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let node,last;while((node=walker.nextNode())){last=node;if(offset<=node.length)return [node,offset];offset-=node.length}return last?[last,last.length]:[el,0]};
  selection.setBaseAndExtent(...point(Math.min(text.length,offsets[0])),...point(Math.min(text.length,offsets[1])));
 }
}

export function readDraft(el){
 let text=el?.innerText||'';const tail=el?.querySelector('[data-caret-tail]')?.innerText;
 if(tail){const at=text.lastIndexOf(tail);if(at>=0)text=text.slice(0,at)+tail.replace('\u200b','')+text.slice(at+tail.length)}
 return text;
}
