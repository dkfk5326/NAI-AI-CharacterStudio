import {useEffect,useRef,useState} from 'react';
import {ChatPromptEditor} from './ChatPromptEditor';
import {api,download} from '../../api';
import type {Project} from '../../types';
import {CHAT_KEY,newConversation,readConversations,requestMessages,editMessage,deleteMessage} from './history.mjs';

function ChatText({text}:{text:string}){
 const chunks=text.split(/(```[\s\S]*?```)/g);
 return <>{chunks.map((chunk,i)=>chunk.startsWith('```')?<pre key={i}><code>{chunk.replace(/^```[^\n]*\n?/, '').replace(/```$/, '')}</code></pre>:<span key={i}>{chunk.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part,j)=>part.startsWith('**')?<strong key={j}>{part.slice(2,-2)}</strong>:part.startsWith('`')?<code key={j}>{part.slice(1,-1)}</code>:part)}</span>)}</>;
}

type Message={id:string;role:'user'|'assistant';content:string;edited?:boolean;reference_sources?:{section_ids:string[];version:string}[]};
type Conversation={id:string;title:string;titleEdited?:boolean;messages:Message[];draft:string;includeContext:boolean;pending:{id:string;status:string}|null;error:string;notice:string};
export function ChatPanel({project,live,visible,onSettings,onUseText,result:workResult,draftRequest}:{project:Project;live:boolean;visible:boolean;onSettings:()=>void;onUseText:(text:string)=>void;result:unknown;draftRequest:{id:string;text:string}|null}){
 const [loadError]=useState(()=>{try{readConversations(localStorage);return ''}catch(e){return String(e)}});
 const [conversations,setConversations]=useState<Conversation[]>(()=>{try{return readConversations(localStorage)}catch{return [newConversation()]}});
 const [selected,setSelected]=useState(()=>{try{return localStorage.getItem('nai-studio:chat-selected')||conversations[0].id}catch{return conversations[0].id}});
 const [promptOpen,setPromptOpen]=useState(false);
 const [storageError,setStorageError]=useState('');
 const [starting,setStarting]=useState(false);
 const [changing,setChanging]=useState(false);
 const [editor,setEditor]=useState<{owner:string;id:string;value:string}|null>(null);
 const compose=useRef<HTMLTextAreaElement>(null);
 const sending=useRef(false);
 const active=conversations.find(c=>c.id===selected)||conversations[0];
 const pendingConversation=conversations.find(c=>c.pending);
 const pending=pendingConversation?.pending;
 const bottom=useRef<HTMLDivElement>(null);
 const patch=(id:string,change:Partial<Conversation>)=>setConversations(old=>old.map(c=>c.id===id?{...c,...change}:c));
 useEffect(()=>{try{localStorage.setItem('nai-studio:chat-selected',selected)}catch{};setEditor(null)},[selected]);
 useEffect(()=>{if(draftRequest){patch(active.id,{draft:draftRequest.text,includeContext:true});compose.current?.focus()}},[draftRequest?.id]);
 useEffect(()=>{if(loadError)return;try{localStorage.setItem(CHAT_KEY,JSON.stringify(conversations));setStorageError('')}catch{setStorageError('대화 기록을 기기에 저장하지 못했습니다. 대화 내보내기로 보관해 주세요.')}},[conversations,loadError]);
 useEffect(()=>{if(visible)bottom.current?.scrollIntoView?.({block:'nearest'})},[active.messages.length,visible,selected]);
 useEffect(()=>{
  if(!pending||!pendingConversation)return;
  const owner=pendingConversation.id,id=pending.id;let stopped=false;let timer:ReturnType<typeof setTimeout>;
  async function poll(){
   try{
    const result=await api('/chat/requests/'+id);
    if(stopped)return;
    if(['completed','failed','cancelled'].includes(result.status)){
     setConversations(old=>old.map(c=>{
      if(c.id!==owner||c.pending?.id!==id)return c;
      const notice=result.status==='cancelled'?'응답을 중단했습니다.':result.finish_reason==='length'?'답변이 출력 길이 한도에 도달했습니다. 이어서 설명해 달라고 요청할 수 있습니다.':result.dropped_messages?'문맥 한도로 오래된 대화 일부를 이번 요청에서 제외했습니다. 대화 기록은 보관됩니다.':c.notice;
      return {...c,pending:null,error:result.status==='failed'?result.error?.message||'모델 응답에 실패했습니다.':'',notice,messages:result.status==='completed'?[...c.messages,{id,role:'assistant',content:result.content,reference_sources:result.reference_sources}]:c.messages};
     }));return;
    }
    patch(owner,{pending:{id,status:result.status},error:''});
   }catch(e){if(stopped)return;patch(owner,{error:'응답 상태를 확인하지 못했습니다. 자동으로 다시 확인합니다. '+String(e)})}
   if(!stopped)timer=setTimeout(poll,800);
  }
  void poll();return()=>{stopped=true;clearTimeout(timer)};
 },[pending?.id,pendingConversation?.id]);
 async function send(retry=false){
  if(sending.current||pendingConversation||changing||editor||!live)return;
  const text=active.draft.trim();if(!retry&&!text)return;
  const id=active.id;
  const messages:Message[]=retry?active.messages:[...active.messages,{id:crypto.randomUUID(),role:'user',content:text}];
  if(messages.at(-1)?.role!=='user')return;
  sending.current=true;setStarting(true);
  patch(id,{messages,draft:retry?active.draft:'',error:'',notice:'',title:active.titleEdited||active.messages.length?active.title:text.slice(0,28)});
  try{
   const request=requestMessages(messages);
   const context=active.includeContext?JSON.stringify({name:project.name,scene:project.input.request_ko,model:project.input.nai_profile_id,characters:project.input.characters,relations:project.input.relations,selected_result:workResult}):'';
   const result=await api('/chat',{messages:request.messages,context});
   patch(id,{pending:{id:result.request_id,status:result.status},notice:request.dropped?'최근 대화를 모델에 전달합니다. 이전 대화는 기록에 그대로 남습니다.':''});
  }catch(e){patch(id,{error:String(e)})}finally{sending.current=false;setStarting(false)}
 }
 async function cancel(){if(!active.pending)return;try{const r=await api('/chat/cancel/'+active.pending.id,{});patch(active.id,{pending:{id:r.request_id,status:r.status}})}catch(e){patch(active.id,{error:String(e)})}}
 async function saveEdit(){
  if(!editor||changing)return;
  const owner=conversations.find(c=>c.id===editor.owner),message=owner?.messages.find(m=>m.id===editor.id);
  if(!owner||!message||owner.pending||starting||!editor.value.trim())return;
  setChanging(true);
  try{
   if(message.role==='assistant')await api('/chat/messages/'+message.id,{content:editor.value},'PUT');
   patch(owner.id,{messages:editMessage(owner.messages,message.id,editor.value),notice:'수정한 내용은 다음 대화부터 반영됩니다.',error:''});setEditor(null);
  }catch(e){patch(owner.id,{error:String(e)})}finally{setChanging(false)}
 }
 async function erase(kind:'message'|'clear'|'conversation',messageId?:string){
  if(active.pending||starting||changing)return;
  const owner=active;
  if(kind!=='message'&&!confirm(kind==='conversation'?'이 대화 전체를 삭제할까요?':'현재 대화의 모든 메시지를 삭제할까요?'))return;
  const removed=kind==='message'?owner.messages.filter(m=>m.id===messageId):owner.messages;
  setChanging(true);
  try{
   const ids=removed.filter(m=>m.role==='assistant').map(m=>m.id);
   if(ids.length)await api('/chat/history/delete',{request_ids:ids});
   setEditor(null);
   if(kind==='conversation'){
    const next=conversations.filter(c=>c.id!==owner.id);if(!next.length)next.push(newConversation());
    const fallback=next[0];setConversations(old=>{const kept=old.filter(c=>c.id!==owner.id);return kept.length?kept:[fallback]});setSelected(next[0].id);
   }else patch(owner.id,{messages:kind==='clear'?[]:deleteMessage(owner.messages,messageId!),error:'',notice:''});
  }catch(e){patch(owner.id,{error:String(e)})}finally{setChanging(false)}
 }
 const starters=['캐릭터의 성격과 외형을 함께 다듬어 봐요.','현재 장면의 구도를 같이 검토해 주세요.'];
 const locked=!!active.pending||starting||changing;
 return <section hidden={!visible} className="chat-page workspace-chat" aria-label="작업 공간 채팅">
  <div className="chat-dock-heading"><h2>작업 채팅</h2><button onClick={()=>setPromptOpen(true)}>대화 프롬프트</button><button onClick={()=>{const c=newConversation();setConversations(old=>[c,...old]);setSelected(c.id)}} disabled={changing}>+ 새 대화</button></div>
  {!live&&<div className="notice">현재 모의 모드입니다. <button onClick={onSettings}>모델 연결 설정</button></div>}
  {(loadError||storageError)&&<div role="alert" className="notice">{loadError?loadError+' 기존 기록을 덮어쓰지 않고 임시로 대화합니다.':storageError}{loadError&&<button onClick={()=>download('chat-history-backup.json',localStorage.getItem(CHAT_KEY)||'')}>기존 기록 내려받기</button>}</div>}
  <div className="chat-room">
   <div className="chat-conversation-controls"><select aria-label="대화 선택" value={active.id} onChange={e=>setSelected(e.target.value)} disabled={changing}>{conversations.map(c=><option key={c.id} value={c.id}>{c.title}{c.pending?' · 응답 대기':''}</option>)}</select><details className="conversation-menu"><summary>대화 관리</summary><label className="field">대화 이름<input aria-label="대화 이름" value={active.title} maxLength={120} disabled={changing} onChange={e=>patch(active.id,{title:e.target.value,titleEdited:true})}/></label><div className="toolbar"><button disabled={!active.messages.length} onClick={()=>download('nai-chat.txt',active.messages.map(m=>(m.role==='user'?'나':'모델')+'\n'+m.content).join('\n\n'),'text/plain')}>내보내기</button><button className="danger" disabled={locked||!active.messages.length} onClick={()=>erase('clear')}>메시지 전체 삭제</button><button className="danger" disabled={locked} onClick={()=>erase('conversation')}>대화 삭제</button></div></details></div>
    <div className="chat-messages" role="log" aria-label="대화 내용" aria-live="polite">
     {!active.messages.length&&<div className="chat-empty"><p>작업을 보면서 편하게 이야기하세요.</p><div className="chat-starters">{starters.map(s=><button key={s} onClick={()=>patch(active.id,{draft:s})}>{s}</button>)}</div></div>}
     {active.messages.map((m,i)=><article key={m.id} className={'chat-message '+m.role}><div className="chat-message-head"><strong>{m.role==='user'?'나':'모델'}{m.edited&&' · 수정됨'}</strong><div><button className="quiet" disabled={locked} aria-label={`메시지 ${i+1} 수정`} onClick={()=>setEditor({owner:active.id,id:m.id,value:m.content})}>수정</button><button className="quiet danger" disabled={locked} aria-label={`메시지 ${i+1} 삭제`} onClick={()=>erase('message',m.id)}>삭제</button><button className="quiet" onClick={async()=>{try{await navigator.clipboard.writeText(m.content);patch(active.id,{notice:'메시지를 복사했습니다.'})}catch{patch(active.id,{error:'텍스트를 선택해 복사해 주세요.'})}}}>복사</button></div></div>
      {editor?.owner===active.id&&editor.id===m.id?<div className="message-editor"><textarea aria-label="메시지 수정 내용" value={editor.value} maxLength={16000} onChange={e=>setEditor({...editor,value:e.target.value})} rows={5}/><div className="toolbar"><button className="primary" disabled={changing||!editor.value.trim()} onClick={saveEdit}>수정 저장</button><button disabled={changing} onClick={()=>setEditor(null)}>취소</button></div></div>:<div className="chat-message-text"><ChatText text={m.content}/></div>}
      {m.role==='assistant'&&<button className="quiet use-message" onClick={()=>onUseText(m.content)}>장면 입력에 추가</button>}
      {m.reference_sources?.length&&<details className="chat-reference"><summary>참고한 LLM 가이드</summary><span className="small">{m.reference_sources.map(s=>`v${s.version} · ${s.section_ids.join(', ')}`).join(' / ')}</span></details>}
     </article>)}
     {active.pending&&<p role="status" className="chat-wait">{active.pending.status==='queued'?'모델 차례를 기다리고 있습니다.':active.pending.status==='cancelling'?'중단 요청됨 · 모델 호출 종료를 기다립니다.':'모델이 답변을 작성하고 있습니다.'}</p>}
     <div ref={bottom}/>
    </div>
    {active.notice&&<p className="small" role="status">{active.notice}</p>}
    {active.error&&<div className="notice" role="alert">{active.error}</div>}
    {!active.pending&&!starting&&active.messages.at(-1)?.role==='user'&&<div className="toolbar chat-retry"><button disabled={changing||!!editor||!!pendingConversation||!live} onClick={()=>send(true)}>다시 보내기</button></div>}
    <form className="chat-composer" onSubmit={e=>{e.preventDefault();void send()}}>
     <label className="check"><input type="checkbox" checked={active.includeContext} onChange={e=>patch(active.id,{includeContext:e.target.checked})}/>현재 캐릭터·장면·선택 결과 참고</label>
     <textarea ref={compose} aria-label="채팅 메시지" placeholder="메시지 입력 · Shift+Enter 줄바꿈" rows={3} maxLength={16000} value={active.draft} onChange={e=>patch(active.id,{draft:e.target.value})} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing&&e.keyCode!==229){e.preventDefault();void send()}}}/>
     <div className="toolbar"><span className="small">{active.includeContext?project.name:'프로젝트 참고 꺼짐'}</span><div className="spacer"/>{active.pending?<button type="button" disabled={active.pending.status==='cancelling'} onClick={cancel}>응답 중단</button>:<button className="primary" disabled={!live||starting||changing||!!editor||!!pendingConversation||!active.draft.trim()}>{starting?'보내는 중…':pendingConversation?'다른 대화 응답 대기':'보내기'}</button>}</div>
    </form>
   </div>
  {promptOpen&&<ChatPromptEditor onClose={()=>setPromptOpen(false)}/>}
 </section>;
}
