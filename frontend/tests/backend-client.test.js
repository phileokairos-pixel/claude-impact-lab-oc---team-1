import test from 'node:test';
import assert from 'node:assert/strict';
import {validateTextRecord,validateTextDraft} from '../backend-client.js';
const fixture=()=>({schemaVersion:'0.1',referralId:'synthetic',version:1,document:{documentId:'synthetic',pageCount:2},pages:[{page:1,state:'ready',text:'Example one'},{page:2,state:'ocr_failed',text:''}],reviews:{},job:{},analysis:{status:'not_connected'},formFields:[],findings:[]});
test('packet adapter preserves original page gaps and rejects another packet or unsupported extraction',()=>{
 assert.equal(validateTextRecord(fixture(),'synthetic').pages[1].page,2);
 assert.throws(()=>validateTextRecord(fixture(),'other'),/unsupported/);
 const renumbered=fixture();renumbered.pages[1].page=1;assert.throws(()=>validateTextRecord(renumbered,'synthetic'),/page/);
 const clinical=fixture();clinical.formFields=[{id:'new'}];assert.throws(()=>validateTextRecord(clinical,'synthetic'),/adapter/);
});
test('server draft must match confirmed revision and be unsent',()=>{
 assert.equal(validateTextDraft({version:2,text:'Unsent',sent:false},2).version,2);
 assert.throws(()=>validateTextDraft({version:1,text:'Old',sent:false},2),/match/);
 assert.throws(()=>validateTextDraft({version:2,text:'Sent',sent:true},2),/match/);
});
