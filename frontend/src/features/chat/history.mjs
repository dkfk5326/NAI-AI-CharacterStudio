export const CHAT_KEY='nai-studio:chats:v1';
export function newConversation(){return {id:crypto.randomUUID(),title:'새 대화',messages:[],draft:'',includeContext:true,pending:null,error:'',notice:''}}
export function readConversations(storage){
 const raw=storage.getItem(CHAT_KEY);
 if(!raw)return [newConversation()];
 const parsed=JSON.parse(raw);
 if(!Array.isArray(parsed)||!parsed.every(c=>c&&typeof c.id==='string'&&typeof c.title==='string'&&typeof c.draft==='string'&&Array.isArray(c.messages)&&c.messages.every(m=>m&&['user','assistant'].includes(m.role)&&typeof m.content==='string'&&typeof m.id==='string')&&(!c.pending||(typeof c.pending.id==='string'&&typeof c.pending.status==='string'))))throw Error('저장된 대화 기록의 형식을 읽을 수 없습니다.');
 return parsed.length?parsed:[newConversation()];
}
export function requestMessages(messages){
 const result=[];
 for(const message of messages){
  const last=result.at(-1);
  if(last?.role===message.role)last.content+='\n\n'+message.content;
  else result.push({role:message.role,content:message.content});
 }
 while(result[0]?.role==='assistant')result.shift();
 const kept=result.slice(-81);
 return {messages:kept,dropped:result.length-kept.length};
}

export function editMessage(messages,id,content){return messages.map(m=>m.id===id?{...m,content,edited:true}:m)}
export function deleteMessage(messages,id){return messages.filter(m=>m.id!==id)}
