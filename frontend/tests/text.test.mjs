import test from 'node:test';import assert from 'node:assert/strict';import {splitPrompt,replacePart,changedElements,mergeCandidates,candidateTitle} from '../src/features/results/text.mjs';
test('tag view round trips literal current copy text',()=>{for(const text of ['girl, black hair, 1.2::white shirt::','girl, 1.2::black hair, short hair::, blue eyes','source#hug. She hugs the woman on her right.','character_(series), [tag]',''])assert.equal(splitPrompt(text).map(x=>x.text+x.separator).join(''),text)});
test('tag edits preserve unaffected syntax and separators',()=>assert.equal(replacePart('girl,  1.2::black hair::, blue eyes',2,'green eyes'),'girl,  1.2::black hair::, green eyes'));
test('asynchronous candidates do not replace existing edits',()=>assert.deepEqual(mergeCandidates([{id:'a',prompt:'manual'}],[{id:'a',prompt:'model'},{id:'b'}]),[{id:'a',prompt:'manual'},{id:'b'}]));
test('variant differences identify actual changed elements',()=>assert.deepEqual(changedElements('girl, blue jacket','girl, red jacket'),{added:['red jacket'],removed:['blue jacket']}));

test('candidate label uses character names and readable prompt terms',()=>assert.equal(candidateTitle({rendered:{characters:[{label:'아쿠아',prompt:'girl, 0.81::blush::, looking at viewer, white socks'}]}}),'아쿠아 · blush · looking at viewer · white socks'));
