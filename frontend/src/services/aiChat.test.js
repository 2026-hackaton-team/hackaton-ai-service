import test from 'node:test';
import assert from 'node:assert/strict';
import { aiConfig, createAiChat, validateAdvice, validateContext } from './aiChat.js';

const context = { people:[{id:'p1',name:'김도윤',relation:'친구',group:'대학 동기',importance:'매우 중요'}],provider:'mock',dataSource:'mock',today:'2026-10-31' };
const advice = {title:'기록을 참고해 보세요',text:'100,000원을 받은 가상 기록이 있어요.',amount:100000,evidence:[{label:'받은 기록',value:'100,000원'}],suggestions:['참석하지 못한다면?'],isMessage:false,provider:'mock',dataSource:'mock',demo:true};
const json = value => new Response(JSON.stringify(value),{status:200});

test('development selects server demo, static production keeps browser mode unless explicitly configured', () => {
  assert.equal(aiConfig({DEV:true}).defaultSource,'server');
  assert.equal(aiConfig({DEV:true,VITE_AI_MODE:'local'}).defaultSource,'local');
  assert.deepEqual(aiConfig({}),{serverAvailable:false,defaultSource:'local',baseUrl:'/api'});
  assert.equal(aiConfig({VITE_AI_MODE:'server'}).defaultSource,'server');
  assert.equal(aiConfig({VITE_AI_API_BASE_URL:'https://example.test/api'}).serverAvailable,true);
  assert.equal(aiConfig({VITE_AI_API_BASE_URL:'https://example.test/api'}).defaultSource,'local');
});

test('server context is fetched and browser-private extra fields are not retained', async () => {
  const api=createAiChat({fetchImpl:async (url,options) => {
    assert.equal(url,'/api/demo/context');assert.equal(options.method,'GET');
    return json({...context,records:[{private:true}],people:[{...context.people[0],memo:'not needed'}]});
  }});
  assert.deepEqual(await api.context(),context);
});

test('advice sends only the question, mode and identifiers; a response retains authoritative metadata', async () => {
  const api=createAiChat({baseUrl:'http://127.0.0.1:8000/api',fetchImpl:async (url,options) => {
    assert.equal(url,'http://127.0.0.1:8000/api/ai/advice');
    assert.equal(options.method,'POST');
    assert.deepEqual(JSON.parse(options.body),{question:'얼마를 참고할까요?',mode:'금액 참고',personId:'p1',eventId:'e1'});
    return json(advice);
  }});
  assert.deepEqual(await api.advice({question:'  얼마를 참고할까요?  ',mode:'금액 참고',personId:'p1',eventId:'e1',people:[{private:true}],records:[{private:true}],userId:'untrusted'}),advice);
});

test('malformed context and advice are rejected before the UI renders them', () => {
  for(const value of [null,{...context,provider:'unknown'},{...context,dataSource:'db'},{...context,people:[...context.people,...context.people]}]) assert.throws(()=>validateContext(value),error=>error.code==='invalid_response');
  for(const value of [null,{...advice,evidence:null},{...advice,amount:-1},{...advice,suggestions:['']},{...advice,demo:false},{...advice,isMessage:'true'},{...advice,text:'x'.repeat(12001)}]) assert.throws(()=>validateAdvice(value),error=>error.code==='invalid_response');
});

test('invalid questions do not issue requests and server failures never become local success', async () => {
  let calls=0;
  const api=createAiChat({fetchImpl:async()=>{calls++;return new Response(JSON.stringify({error:{code:'provider_busy',message:'잠시 후 다시 시도해 주세요.'}}),{status:503});}});
  await assert.rejects(api.advice({question:' ',mode:'금액 참고',personId:'p1'}),error=>error.code==='invalid_input');
  assert.equal(calls,0);
  await assert.rejects(api.advice({question:'금액 참고',mode:'금액 참고',personId:'p1'}),error=>error.status===503&&error.code==='provider_busy');
  assert.equal(calls,1);
});

test('request cancellation reaches fetch and rejects with an aborted error', async () => {
  let signalReceived;
  const controller=new AbortController();
  const api=createAiChat({fetchImpl:async (url,options)=>new Promise((resolve,reject)=>{
    signalReceived=options.signal;
    signalReceived.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true});
  })});
  const pending=api.context({signal:controller.signal});
  controller.abort();
  await assert.rejects(pending,error=>error.code==='aborted');
  assert.equal(signalReceived.aborted,true);
});

test('real provider metadata uses the same validated display contract', () => {
  assert.equal(validateAdvice({...advice,provider:'openai'}).provider,'openai');
  assert.equal(validateContext({...context,provider:'openai'}).provider,'openai');
});
