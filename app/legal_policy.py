"""가상 인물의 확인된 속성과 공식 RAG 근거를 결합하는 보수적 정책 판정기."""
from __future__ import annotations
import hashlib
from gyeongjosa_ai import seed_db
from .knowledge import KB

PROFILES = seed_db.load('person_policy_profiles')
RULEBOOK = seed_db.load('legal_rules')
RULES = RULEBOOK['rules']


def profile_for(person_id: str, scenario_id: str = 'default') -> dict:
    if scenario_id == 'default':
        return dict(PROFILES['profiles'].get(person_id, dict(covered='unknown', duty_related='unknown',
            exception_confirmed='unknown', conflict='unknown', provenance='synthetic_unknown',
            description='법 적용 정보를 등록하지 않은 인물')))
    scenario = PROFILES['scenarios'].get(scenario_id)
    if not scenario or scenario.get('person_id') != person_id:
        raise ValueError('INVALID_SCENARIO_FOR_PERSON')
    return dict(scenario['profile'])


def assess(person_id: str, event_type: str, *, scenario_id: str='default', kb=None, profile_override: dict | None = None) -> dict:
    if kb is None: kb = KB
    profile = dict(profile_override) if profile_override is not None else profile_for(person_id, scenario_id)
    status = 'NEEDS_FACTS'
    reason = ''
    source_ids = []
    rule_ids = []
    limit = None
    questions = []
    # 합성 인물 속성은 RAG가 추측하지 않는다. 적용할 법규의 근거만 검색한다.
    if profile.get('sender_ethics_risk'):
        status = 'NEEDS_EXPERT_REVIEW'
        reason = '제공자의 공적 업무와 계약·심사 상대방의 이해관계가 의심되어, 수령자 신분과 무관하게 기관 행동강령 등 별도 검토가 필요합니다.'
        questions = ['제공자인 본인의 직무 권한과 상대방의 계약·평가 관계를 기관 담당자에게 확인해 주세요.']
    elif profile.get('unconfirmed_high_risk'):
        status = 'NEEDS_FACTS'
        reason = '자연어에서 계약·심사 등 이해관계 단서가 발견되었지만 해당 사실이 확인되지 않았습니다.'
        questions = ['문장에 언급한 관계가 실제 현재의 직무 관련성인지 확인해 주세요.']
    elif profile['covered'] == 'no':
        status = 'OUT_OF_SCOPE'
        reason = '시연용 등록 프로필에서 민간 기업 직원임을 확인했으며 공직자등 적용 사실은 없습니다.'
    elif profile['covered'] == 'unknown':
        reason = '공직자등 해당 여부가 확인되지 않았습니다.'
        questions = ['경조금 수령자가 공직자등인지 확인해 주세요.']
    elif profile['duty_related'] == 'unknown':
        reason = '공직자등에 해당하지만 직무 관련성은 확인되지 않았습니다.'
        questions = ['업무·계약·평가·인허가 관계를 포함해 직무 관련성을 확인해 주세요.']
    elif profile['duty_related'] == 'yes' and profile['exception_confirmed'] == 'unknown':
        reason = '직무 관련성이 있지만 부조 목적 예외가 인정되는지는 확인되지 않았습니다.'
        questions = ['제공 목적, 친분, 직무 밀접성, 제공 시기 등을 확인해 주세요.']
    else:
        candidates = []
        for rule in RULES:
            if event_type not in rule['event_types']: continue
            if rule['covered'] != profile['covered'] or rule['duty_related'] != profile['duty_related']: continue
            if 'exception_confirmed' in rule and rule['exception_confirmed'] != profile['exception_confirmed']: continue
            if 'conflict' in rule and rule['conflict'] != profile['conflict']: continue
            candidates.append(rule)
        if candidates:
            rule = candidates[0]
            # 법률 근거가 RAG KB에서 검증된 문서로 확보되었는지 확인한다.
            retrieved = kb.retrieve('청탁금지법 공직자등 직무 관련 부조 경조사비 예외 일반 동료',
                                    event_type=event_type, legal_risk=True, top_k=20)
            retrieved_ids = {d['id'] for d in retrieved}
            eligible = {d['id'] for d in kb.documents if d['id'] in retrieved_ids
                        and d['source_type']=='legal_guidance' and d.get('verified') is True
                        and d.get('url') and event_type in d['event_types']
                        and hashlib.sha256(d['text'].encode('utf-8')).hexdigest()
                        == RULEBOOK['source_checksums'].get(d['id'])}
            if all(s in eligible for s in rule['source_ids']):
                status,reason = rule['status'],rule['reason']
                rule_ids,source_ids=[rule['id']],list(rule['source_ids'])
                limit = rule.get('cash_limit_krw')
            else:
                status = 'NEEDS_EXPERT_REVIEW'
                reason = '적용 규칙의 공식 근거를 현재 RAG 지식베이스에서 확인하지 못했습니다.'
                questions = ['공식 근거와 적용 시점을 검증해 주세요.']
        else:
            status = 'NEEDS_EXPERT_REVIEW'
            reason = '현재 상황에 검증된 예외 판단 규칙이 없습니다.'
            questions = ['해당 금전 제공의 적법성에 관한 추가 검토가 필요합니다.']
    return {'status':status,'reason':reason,'rule_ids':rule_ids,'source_ids':source_ids,
            'cash_limit_krw':limit,'missing_questions':questions,
            'profile_summary':profile['description'],'profile_provenance':profile['provenance'],
            'is_hypothetical':scenario_id!='default','scenario_id':scenario_id,
            'provisional': profile.get('provenance') in ('self_reported_demo','self_reported_context','user_confirmed_context','unavailable_profile')}