"""v3 local demo API: profile onboarding, consent-gated resolution and RAG policy."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .knowledge import KB
from .recommender import DEMO, owned_person
from .legal_policy import PROFILES
from .profile_store import ProfileStore, profile_for_recipient
from .orchestrator import run
from .relationship_analysis import analyze
from .llm import MODEL, explain

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title='경조사 RAG+LLM+추천엔진 v3',version='0.4.0',docs_url='/api/docs',redoc_url=None)
DEMO_USERS = {u['id']:u for u in DEMO['users'] if u.get('demo_account')}
STORE = ProfileStore()

class RecommendationRequest(BaseModel):
    demo_user_id: str
    person_id: str
    identity_confirmed: bool = False
    event_type: str
    attendance_with_meal: bool | None = None
    budget_krw: int | None = Field(default=None,ge=0,le=10000000)
    scenario_id: str = 'default'
    explanation_mode: Literal['auto','offline','llm'] = 'auto'
    legal_risk: bool = False  # backward compatible, never a gate
    duty_context: Literal['unknown','none','duty_related','contract_active'] = 'unknown'
    exception_context: Literal['unknown','yes','no'] = 'unknown'
    relationship_text: str = Field(default='',max_length=400)
    facts_confirmed: bool = False
    allow_llm_analysis: bool = False

class OnboardingRequest(BaseModel):
    demo_user_id: str
    occupation: Literal['unknown','private_employee','civil_servant','public_institution_employee','school_teacher','journalist','other']
    institution: Literal['unknown','private_company','government','public_institution','school','press','other']
    allow_recommendation: bool = False
    visibility: Literal['none','accepted_contacts'] = 'none'
    duty_role: Literal['unknown','general','procurement','licensing','evaluation','supervision','audit','hr'] = 'unknown'

@app.get('/api/health')
def health():
    return {'status':'ok','mode':'synthetic_demo_only','policy_engine':'v4',
            'profile_source':'sqlite_demo','knowledge_documents':len(KB.documents),
            'llm_configured':bool(os.getenv('OPENAI_API_KEY')),'llm_model':MODEL}

@app.get('/api/demo/users')
def users():
    return [{'id':u['id'],'name':u['name'],'affiliation':u['fictional_affiliation']}
            for u in DEMO_USERS.values()]

@app.get('/api/demo/people')
def people(user_id: str = Query(min_length=1), include_special: bool = False):
    if user_id not in DEMO_USERS: raise HTTPException(404,'데모 계정이 없습니다.')
    return [{'id':p['id'],'name':p['name'],'relationship':p['relationship'],
             'affiliation':p['fictional_affiliation']} for p in DEMO['people']
             if p['owner_user_id']==user_id and (include_special or not p['id'].startswith('V4P'))]

@app.get('/api/demo/scenarios')
def scenarios(person_id: str = Query(min_length=1)):
    return [{'id':sid,'label':sc.get('label',sid),
             'description':sc.get('description') or sc.get('profile',{}).get('description') or sc.get('label',sid)}
            for sid,sc in PROFILES['scenarios'].items()
            if sid=='default' or (not sid.startswith('chat_') and sc.get('person_id')==person_id)]

@app.get('/api/demo/me/profile')
def my_profile(demo_user_id: str = Query(min_length=1)):
    if demo_user_id not in DEMO_USERS: raise HTTPException(404,'데모 계정이 없습니다.')
    return {'profile':STORE.get(demo_user_id),'demo_authentication':False}

@app.post('/api/demo/onboarding')
def onboarding(req: OnboardingRequest):
    if req.demo_user_id not in DEMO_USERS: raise HTTPException(404,'데모 계정이 없습니다.')
    return {'profile':STORE.put(req.demo_user_id,occupation=req.occupation,
             institution=req.institution,allow_recommendation=req.allow_recommendation,
             visibility=req.visibility,duty_role=req.duty_role),'demo_authentication':False}

@app.get('/api/demo/profile-access')
def recipient_profile_access(demo_user_id: str,person_id: str):
    if demo_user_id not in DEMO_USERS:raise HTTPException(404,'데모 계정이 없습니다.')
    if owned_person(demo_user_id,person_id) is None:
        raise HTTPException(404,'해당 인물 기록이 없습니다.')
    result = profile_for_recipient(store=STORE,data=DEMO,viewer_id=demo_user_id,person_id=person_id)
    return {'access':result['access'],'occupation_disclosed':False}

@app.get('/api/evidence/search')
def evidence_search(q: str=Query(min_length=2,max_length=200), event_type: str|None=None):
    if event_type and event_type not in DEMO['event_categories']:
        raise HTTPException(422,'지원하지 않는 행사입니다.')
    return {'results':KB.retrieve(q,event_type=event_type,legal_risk=True),
            'index_type':'local_char_ngram_tfidf','pii_indexed':False}

@app.post('/api/recommend')
def recommendation(req: RecommendationRequest):
    if req.demo_user_id not in DEMO_USERS:raise HTTPException(404,'데모 계정이 없습니다.')
    if owned_person(req.demo_user_id,req.person_id) is None:
        raise HTTPException(404,'선택 계정에 속한 인물이 아닙니다.')
    if req.event_type not in DEMO['event_categories']:
        raise HTTPException(422,'지원하지 않는 행사입니다.')
    access = profile_for_recipient(store=STORE,data=DEMO,viewer_id=req.demo_user_id,person_id=req.person_id)
    policy = dict(access['policy'] or {
        'covered':'unknown','duty_related':'unknown','exception_confirmed':'unknown',
        'conflict':'unknown','provenance':'unavailable_profile',
        'description':'상대방의 직업 정보가 추천 목적으로 제공되지 않았습니다.'
    })
    sender_profile = STORE.get(req.demo_user_id)
    if req.scenario_id == 'chat_sender_public':
        # 이 시연에만 제공자가 계약 업무를 담당하는 공무원이라고 가정한다.
        sender_profile = {'occupation':'civil_servant', 'institution':'government', 'duty_role':'procurement'}
    relation = analyze(sender=sender_profile, recipient=policy,
        relationship_text=req.relationship_text,duty_context=req.duty_context,
        exception_context=req.exception_context,facts_confirmed=req.facts_confirmed,
        allow_llm_analysis=req.allow_llm_analysis)
    if req.scenario_id == 'chat_sender_public':
        policy['sender_ethics_risk'] = relation['sender_ethics_risk']
    if req.scenario_id == 'default':
        if policy['covered'] != 'unknown':
            # Only explicit structured or user-confirmed text may set policy facts.
            if relation['duty_context'] == 'none':
                policy['duty_related'] = 'no'
            elif relation['duty_context'] == 'duty_related':
                policy['duty_related'] = 'yes'
                policy['exception_confirmed'] = req.exception_context
                if req.exception_context == 'yes': policy['conflict'] = 'none'
            elif relation['duty_context'] == 'contract_active':
                policy['duty_related'] = 'yes'
                policy['conflict'] = 'high'
                policy['exception_confirmed'] = req.exception_context
            if relation['duty_context'] != 'unknown':
                policy['provenance'] = 'user_confirmed_context'
        policy['sender_ethics_risk'] = relation['sender_ethics_risk']
        policy['unconfirmed_high_risk'] = (relation['high_risk_hint']
                                           and relation['duty_context'] == 'unknown')
    report = run(user_id=req.demo_user_id,person_id=req.person_id,
                 identity_confirmed=req.identity_confirmed,event_type=req.event_type,
                 attendance_with_meal=req.attendance_with_meal,budget_krw=req.budget_krw,
                 scenario_id=req.scenario_id,explanation_mode=req.explanation_mode,
                 profile_override=policy if req.scenario_id in ('default','chat_sender_public') else None,
                 profile_access=access['access'] if req.scenario_id=='default' else 'hypothetical_override',
                 relation_assessment=relation)
    result,evidence=report['result'],report['evidence']
    explanation,used,warning=explain(result,evidence,mode=req.explanation_mode)
    return {'result':result,'explanation':explanation,'llm_used':used,
            'llm_warning':warning,'evidence':evidence,'query_plan':report.get('query_plan'),
            'relationship_analysis':relation,'demo_only':True}

app.mount('/',StaticFiles(directory=ROOT/'v4_demo_frontend',html=True),name='frontend')