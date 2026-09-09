/** Lossless token view. Delimiters inside weights/braces/brackets are kept. */
export function splitPrompt(text){let out=[],start=0,depth=0,weighted=false;for(let i=0;i<text.length;i++){if(text.slice(i,i+2)==='::'){weighted=!weighted;i++;continue}if('{[('.includes(text[i]))depth++;if('}])'.includes(text[i]))depth=Math.max(0,depth-1);if(text[i]===','&&!weighted&&depth===0){let end=i+1;while(text[end]===' ')end++;out.push({text:text.slice(start,i),separator:text.slice(i,end)});start=end;i=end-1}}out.push({text:text.slice(start),separator:''});return out}
export function replacePart(text,index,value){return splitPrompt(text).map((p,i)=>(i===index?value:p.text)+p.separator).join('')}
export function changedElements(before,after){const b=new Set(splitPrompt(before).map(p=>p.text.trim())),a=new Set(splitPrompt(after).map(p=>p.text.trim()));return {added:[...a].filter(x=>x&&!b.has(x)),removed:[...b].filter(x=>x&&!a.has(x))}}
export function mergeCandidates(existing,incoming,deleted=[]){const blocked=new Set(deleted);const ids=new Set(existing.map(c=>c.id));return [...existing.filter(c=>!blocked.has(c.id)),...incoming.filter(c=>!ids.has(c.id)&&!blocked.has(c.id))]}

export function candidateTitle(candidate){
 if(typeof candidate?.title==='string'&&candidate.title.trim())return candidate.title.trim();
 const cards=candidate?.rendered?.characters||[];
 const names=cards.map(c=>String(c.label||'').trim()).filter(Boolean);
 const namePart=names.length>2?`${names.slice(0,2).join(' + ')} 외 ${names.length-2}명`:names.join(' + ');
 const skip=/^(?:girl|boy|other|\d+(?:girls?|boys?|others?)|(?:source|target|mutual)#)/i;
 const tags=[];
 for(const card of cards){
  for(const part of splitPrompt(card.prompt||'')){
   let text=part.text.trim().replace(/^[-+]?\d+(?:\.\d+)?::(.*)::$/,'$1').trim();
   if(!text||skip.test(text)||text.length>42||/[.!?]$/.test(text))continue;
   if(!tags.includes(text))tags.push(text);
   if(tags.length>=3)break;
  }
  if(tags.length>=3)break;
 }
 return [namePart,...tags].filter(Boolean).join(' · ')||'생성 결과';
}
