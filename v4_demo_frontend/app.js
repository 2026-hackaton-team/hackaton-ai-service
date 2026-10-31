'use strict';
const $ = id => document.getElementById(id);
const won = n => Number(n).toLocaleString('ko-KR') + '원';
async function getJSON(path, options={}) {
  const res = await fetch(path, {cache:'no-store', ...options});
  let body; try {body=await res.json();} catch (_) {throw new Error('JSON 응답을 받지 못했습니다.');}
  if(!res.ok) throw new Error(typeof body.detail==='string'?body.detail:`요청 실패 (${res.status})`);
  return body;
}
function element(tag, cl, content) {const e=document.createElement(tag);if(cl)e.className=cl;if(content!=null)e.textContent=content;return e;}
function fillSelect(el,items,label){el.replaceChildren(...items.map(x=>{const o=element('option',null,label(x));o.value=x.id;return o;}));}
async function init(){
  const health=await getJSON('/api/health');
  $('apiBadge').textContent=health.llm_configured?'LLM 키 설정됨':'로컬 RAG / 오프라인';
  fillSelect($('demoUser'),await getJSON('/api/demo/users'),u=>u.name+' · '+u.affiliation);
  $('demoUser').value='U001';await updatePeople();$('person').value='P001';await updatePerson();await loadMyProfile();await updateAccess();
}
async function updatePeople(){
  const ps=await getJSON('/api/demo/people?user_id='+encodeURIComponent($('demoUser').value));
  fillSelect($('person'),ps,p=>p.name+' · '+p.relationship+' · '+p.affiliation);
  await updatePerson(); await loadMyProfile(); await updateAccess();
}
async function updatePerson(){
  const opt=$('person').selectedOptions[0];
  $('personDescription').textContent=opt?`선택한 인물: ${opt.textContent} (ID ${opt.value})`:'대상이 없습니다.';
  $('confirmed').checked=false;
  const fallback=[{id:'default',label:'등록된 인물 프로필 자동 판단'}];
  if (!$('person').value) {
    fillSelect($('scenario'),fallback,s=>s.label);
    $('scenario').value='default';
    return;
  }
  try {
    const options=await getJSON('/api/demo/scenarios?person_id='+encodeURIComponent($('person').value));
    fillSelect($('scenario'),options.length?options:fallback,s=>s.label);
  } catch (err) {
    fillSelect($('scenario'),fallback,s=>s.label);
    $('personDescription').textContent+=' / 시나리오 목록 조회 실패: 기본 자동 판단으로 진행합니다.';
  }
  $('scenario').value='default';
  await updateAccess();
}
async function loadMyProfile(){
  const p=(await getJSON('/api/demo/me/profile?demo_user_id='+encodeURIComponent($('demoUser').value))).profile;
  $('myOccupation').value=p.occupation; $('myInstitution').value=p.institution;
  $('myDutyRole').value=p.duty_role||'unknown'; $('myConsent').checked=!!p.allow_recommendation;
  $('myVisibility').value=p.visibility;
}
async function updateAccess(){
  if(!$('person').value)return;
  const a=await getJSON('/api/demo/profile-access?demo_user_id='+encodeURIComponent($('demoUser').value)+'&person_id='+encodeURIComponent($('person').value));
  const labels={consented:'상대가 추천 목적 직업정보 이용을 허용했습니다.',not_shared:'상대가 직업정보 이용을 허용하지 않았습니다.',not_authorized:'승인된 추천용 연결이 없습니다.'};
  $('accessStatus').textContent=labels[a.access]||'프로필을 확인하지 못했습니다.';
}
function evidenceNode(d){
  const node=element('article','evidence');
  const link=element('a',null,d.title);link.href=d.url;link.target='_blank';link.rel='noopener noreferrer';node.append(link);
  const meta=element('div','meta');
  meta.append(element('span',null,d.publisher));
  if(d.published_at)meta.append(element('span',null,d.published_at));
  const labels={applied_legal:'판정에 적용한 법률 근거',applied_statistic:'금액 계산 적용',context_only:'참고·제외된 근거'};
  meta.append(element('span','role '+(d.decision_role==='context_only'?'excluded':''),labels[d.decision_role]||'검색 자료'));
  node.append(meta,element('p',null,d.excerpt));
  if(d.excluded_reason)node.append(element('div','why','금액/정책 판단에서 제외: '+d.excluded_reason));
  return node;
}
function showEvidence(items,targetId){
  const el=$(targetId);el.replaceChildren();
  if(!items.length){el.append(element('p','help','일치하는 공개자료가 없습니다.'));return;}
  items.forEach(x=>el.append(evidenceNode(x)));
}
function showPolicy(policy,r){
  $('policyDetail').hidden=!policy;
  if(!policy)return;
  const names={OUT_OF_SCOPE:'일반 민간 관계: 직무 관련 경조사 한도 미적용',
    CONDITIONALLY_ALLOWED:'부조 예외가 성립한다는 가정: 조건부 금액 제한 적용',
    NO_DUTY_CEREMONY_LIMIT:'직무관련 5만 원 기준 미적용: 다른 법률 기준은 별도 확인',
    POTENTIALLY_PROHIBITED:'금전 제공 위험: 송금 추천 보류',
    NEEDS_FACTS:'법률 적용 요건 확인 필요',NEEDS_EXPERT_REVIEW:'공식 근거·예외 추가 검토 필요'};
  $('policyStatus').textContent=names[policy.status]||policy.status;
  $('policyReason').textContent=policy.reason;
  $('policyContext').textContent=`근거 프로필: ${policy.profile_summary} / ${policy.is_hypothetical?'별도 가상 시나리오':'기본 합성 프로필'} / 규칙: ${policy.rule_ids.join(', ')||'미선택'} / 법률 출처: ${policy.source_ids.join(', ')||'적용 규칙 없음'}`;
  $('policyQuestions').textContent=policy.missing_questions.length?'확인할 사항: '+policy.missing_questions.join(' '):'';
  $('referenceAmount').textContent=r.reference_only_amount_krw!=null?'법적 판정 미완료. 개인 이력 기반 참고액 '+won(r.reference_only_amount_krw)+'은 송금 권고가 아닙니다.':'';
}
function showResult(data){
  $('emptyResult').hidden=true;$('results').hidden=false;
  $('errorMessage').hidden=true;$('recoDetail').hidden=true;
  const r=data.result;
  $('llmState').textContent=data.llm_used?'LLM 설명 생성':'결정적 설명';
  showEvidence(data.evidence,'evidence');showPolicy(r.legal_assessment,r);
  const a=data.relationship_analysis; $('relationDetail').hidden=!a;
  if(a){
    const states={confirmed_by_user:'사용자가 확인한 직무 관계',hypothesis_needs_confirmation:'직무 단서 발견 — 사실 확인 전',insufficient_facts:'직무 관계 정보 부족'};
    $('relationStatus').textContent=(states[a.status]||a.status)+' / 내 직업 반영: '+(a.sender_profile_used?'예':'미확인')+' / 외부 LLM 보조: '+(a.used_llm?'사용':'미사용');
    $('relationQuestions').textContent=a.missing_questions.join(' ')+(a.llm_warning?' '+a.llm_warning:'');
  }
  $('queryPlan').textContent=data.query_plan?`검색계획: ${data.query_plan.llm_used?'LLM 보조':'결정적 검색'} / ${Object.entries(data.query_plan.queries).map(([k,v])=>k+': '+v).join(' | ')}`:'';
  $('disclaimer').textContent='모든 인물·업무 관계는 가상입니다. 이 추천은 적정 금액과 법적 적합성을 보증하지 않습니다.'+(data.llm_warning?' '+data.llm_warning:'');
  if(r.status!=='RECOMMENDED'){
    $('errorMessage').hidden=false;$('errorMessage').textContent=r.status+': '+r.message;
    return;
  }
  $('recoDetail').hidden=false;
  $('recommendedAmount').textContent=won(r.amount_krw);
  $('evidenceLevel').textContent=r.evidence_level==='moderate'?'통계+개인 근거':'개인 이력 중심';
  $('alternatives').textContent=r.alternatives_krw.map(won).join(' · ')||'없음';
  const changed=r.policy_adjusted?` 일반 계산 ${won(r.unconstrained_amount_krw)} → 조건부 재평가 ${won(r.amount_krw)}.`:'';
  $('explanation').textContent=data.explanation+changed;
  $('scores').replaceChildren(...r.scores.slice(0,4).map(x=>{
    const row=element('div','score-row');row.append(element('span',null,won(x.amount_krw)));
    const track=element('div','score-track');const fill=element('div','score-fill');
    fill.style.width=Math.min(100,Math.round(x.score*100))+'%';track.append(fill);
    row.append(track,element('strong',null,(x.score*100).toFixed(1)));return row;
  }));
  const h=r.personal_history;
  $('history').replaceChildren(...[
    ['보낸 거래',`${h.paid_count}건 / ${won(h.paid_total_krw)}`],
    ['받은 거래',`${h.received_count}건 / ${won(h.received_total_krw)}`],
    ['명시적 0원',`${h.explicit_zero_paid_count}건`]
  ].map(([n,v])=>{const box=element('div','stat');box.append(element('label',null,n),element('strong',null,v));return box;}));
  const labels={matched_survey:'일치 설문',same_type_paid:'동일 행사',paid_to_person:'동일 인물 지급',received_from_person:'동일 인물 수령'};
  $('weights').replaceChildren(...Object.entries(r.weights_used).map(([k,v])=>element('span','chip',`${labels[k]||k}: ${(v*100).toFixed(1)}%`)));
}
$('demoUser').addEventListener('change',()=>updatePeople().catch(e=>alert(e.message)));
$('person').addEventListener('change',()=>updatePerson().catch(e=>alert(e.message)));
$('onboardingForm').addEventListener('submit',async e=>{
  e.preventDefault();
  try{
    await getJSON('/api/demo/onboarding',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      demo_user_id:$('demoUser').value,occupation:$('myOccupation').value,institution:$('myInstitution').value,duty_role:$('myDutyRole').value,
      allow_recommendation:$('myConsent').checked,visibility:$('myVisibility').value
    })});
    $('onboardingStatus').textContent='저장됨. 다른 계정으로 전환하면 접근 허용 상태가 즉시 반영됩니다.';
    await updateAccess();
  }catch(err){$('onboardingStatus').textContent='실패: '+err.message;}
});
$('form').addEventListener('submit',async e=>{
  e.preventDefault();$('submit').disabled=true;$('submit').firstChild.textContent='계산 중...';
  try{
    const a=$('attendance').value;
    const data=await getJSON('/api/recommend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      demo_user_id:$('demoUser').value,person_id:$('person').value,
      identity_confirmed:$('confirmed').checked,event_type:$('event').value,
      attendance_with_meal:a==='unknown'?null:a==='yes',
      budget_krw:$('budget').value===''?null:Number($('budget').value),
      scenario_id:$('scenario').value||'default',explanation_mode:$('mode').value,
      relationship_text:$('relationshipText').value,facts_confirmed:$('factsConfirmed').checked,
      allow_llm_analysis:$('allowLLMAnalysis').checked,
      duty_context:$('dutyContext').value,exception_context:$('exceptionContext').value
    })});showResult(data);
  } catch(ex){$('emptyResult').hidden=false;$('results').hidden=true;alert(ex.message);}
  finally{$('submit').disabled=false;$('submit').firstChild.textContent='추천 계산하고 근거 보기 ';}
});
$('searchForm').addEventListener('submit',async e=>{
  e.preventDefault();try{const x=await getJSON('/api/evidence/search?q='+encodeURIComponent($('query').value));showEvidence(x.results,'searchResults');}
  catch(ex){$('searchResults').replaceChildren(element('p','alert',ex.message));}
});
document.querySelectorAll('[data-preset]').forEach(btn=>btn.addEventListener('click',async()=>{
  $('demoUser').value='U001';await updatePeople();$('person').value='P001';await updatePerson();
  const mode=btn.dataset.preset;
  $('event').value=mode==='funeral'?'장례':'결혼';
  $('attendance').value=mode==='funeral'?'unknown':'yes';
  $('budget').value=mode==='funeral'?'80000':'150000';
  $('scenario').value=(mode==='public_exception'||mode==='public_procurement')?mode:'default';
  $('confirmed').checked=true;$('form').requestSubmit();
}));
init().catch(e=>{$('apiBadge').textContent='서버 연결 실패';console.error(e);});