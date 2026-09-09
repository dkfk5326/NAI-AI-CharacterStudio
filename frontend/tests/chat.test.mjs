import test from 'node:test';
import assert from 'node:assert/strict';
import {requestMessages,readConversations,newConversation} from '../src/features/chat/history.mjs';
test('new conversations keep independent ids and begin with workspace context',()=>{const a=newConversation(),b=newConversation();assert.notEqual(a.id,b.id);assert.equal(a.includeContext,true)});
test('failed and cancelled user turns are joined without losing text',()=>{assert.deepEqual(requestMessages([{role:'user',content:'first'},{role:'user',content:'second'}]).messages,[{role:'user',content:'first\n\nsecond'}])});
test('long transcripts preserve complete recent turns and do not mutate saved history',()=>{const messages=Array.from({length:101},(_,i)=>({role:i%2?'assistant':'user',content:String(i)}));const r=requestMessages(messages);assert.equal(r.messages.length,81);assert.equal(r.dropped,20);assert.equal(r.messages[0].role,'user');assert.equal(r.messages.at(-1).content,'100');assert.equal(messages.length,101)});
test('corrupt history is reported without overwriting storage',()=>{let writes=0;const storage={getItem:()=>'{bad',setItem:()=>writes++};assert.throws(()=>readConversations(storage));assert.equal(writes,0)});
test('conversation restore preserves pending request and unsent draft',()=>{const c=newConversation();c.draft='작성 중';c.pending={id:'request-1',status:'running'};const restored=readConversations({getItem:()=>JSON.stringify([c])});assert.equal(restored[0].draft,'작성 중');assert.equal(restored[0].pending.id,'request-1')});

test('individual edits and deletions preserve other messages and affect next context',async()=>{
 const {editMessage,deleteMessage}=await import('../src/features/chat/history.mjs');
 const messages=[{id:'a',role:'user',content:'old'},{id:'b',role:'assistant',content:'answer'},{id:'c',role:'user',content:'next'}];
 const edited=editMessage(messages,'a','new');assert.equal(edited[0].edited,true);assert.equal(edited[1],messages[1]);assert.equal(messages[0].content,'old');
 const removed=deleteMessage(edited,'b');assert.deepEqual(removed.map(m=>m.id),['a','c']);assert.deepEqual(requestMessages(removed).messages,[{role:'user',content:'new\n\nnext'}]);
});
