import test from 'node:test';
import assert from 'node:assert/strict';
import {removeResultRecords,resultContext} from '../src/features/results/history.mjs';
import {candidateTitle,mergeCandidates} from '../src/features/results/text.mjs';
test('deleted result records and overrides cannot reappear through undo or delayed responses',()=>{
 const candidates=[{id:'one'},{id:'two'}],overrides={'one:c0:prompt':'delete','two:c0:prompt':'keep'};
 const p={candidates,manual_overrides:overrides,history:[{candidates,manual_overrides:overrides}],legacy:{custom:'keep'}};
 const next=removeResultRecords(p,['one']);assert.deepEqual(next.candidates,[{id:'two'}]);assert.equal(next.manual_overrides['one:c0:prompt'],undefined);assert.deepEqual(next.history[0].candidates,[{id:'two'}]);assert.equal(next.legacy.custom,'keep');assert.equal(p.candidates.length,2);
 assert.deepEqual(mergeCandidates(next.candidates,[{id:'one'},{id:'three'}],next.legacy.deleted_candidate_ids),[{id:'two'},{id:'three'}]);
 const empty=removeResultRecords(next,['two']);assert.equal(empty.candidates.length,0);assert.deepEqual(empty.manual_overrides,{});
});
test('custom record names and manual edits are the versions sent to workspace chat',()=>{
 const c={id:'c',title:'Edited name',rendered:{characters:[{id:'a',label:'A',prompt:'old',uc:'old uc'}],shared_fragment:'old shared'}};
 assert.equal(candidateTitle(c),'Edited name');
 assert.deepEqual(resultContext(c,{'c:a:prompt':'new','c:a:uc':'','c:shared:prompt':'new shared'}),{title:'Edited name',characters:[{label:'A',prompt:'new',uc:''}],shared_fragment:'new shared'});
});
