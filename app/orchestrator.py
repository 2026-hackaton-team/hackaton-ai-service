"""공개 RAG→사실/법률 적용성→금액 랭킹→정책 제약 처리 순서를 보장한다."""
from __future__ import annotations
from .knowledge import KB
from .legal_policy import assess, profile_for
from .evidence_resolver import collect
from .recommender import recommend,owned_person
from .query_planner import plan


def run(*, user_id:str, person_id:str, identity_confirmed:bool, event_type:str,
        attendance_with_meal:bool|None, budget_krw:int|None,
        scenario_id:str='default', kb=None, explanation_mode:str='auto',
        profile_override:dict|None=None, profile_access:str|None=None,
        relation_assessment:dict|None=None, closeness_override:int|None=None,
        special_care:bool=False, recent_received_override:int|None=None)->dict:
    if kb is None: kb=KB
    person=owned_person(user_id,person_id)
    if person is None:
        return {'result':{'status':'FORBIDDEN_OR_NOT_FOUND','message':'접근 가능한 인물 기록이 없습니다.'},'evidence':[]}
    if not identity_confirmed:
        return {'result':{'status':'NEEDS_IDENTITY_CONFIRMATION','message':'동명이인 여부를 먼저 확인하세요.'},'evidence':[]}
    try:
        legal=assess(person_id,event_type,scenario_id=scenario_id,kb=kb,profile_override=profile_override)
    except ValueError:
        return {'result':{'status':'INVALID_SCENARIO','message':'선택한 인물에 적용할 수 없는 시연 상황입니다.'},'evidence':[]}
    query_plan=plan(event_type,person['relationship'],attendance_with_meal,mode=explanation_mode)
    evidence=collect(event_type=event_type,relationship=person['relationship'],
                     attendance_with_meal=attendance_with_meal,legal_assessment=legal,kb=kb,
                     search_plan=query_plan['queries'])
    base=recommend(user_id=user_id,person_id=person_id,identity_confirmed=True,
                   event_type=event_type,attendance_with_meal=attendance_with_meal,
                   budget_krw=budget_krw,legal_risk=False,kb=kb,
                   closeness_override=closeness_override,special_care=special_care,
                   recent_received_override=recent_received_override)
    initial = base.get('amount_krw')
    status=legal['status']
    if base['status']=='RECOMMENDED':
        base['event_type']=event_type
        base['unconstrained_amount_krw']=initial
        base['policy_adjusted']=False
        if status=='CONDITIONALLY_ALLOWED':
            cap=legal['cash_limit_krw']
            eligible=[x for x in base['scores'] if x['amount_krw']<=cap]
            if eligible:
                base['amount_krw']=eligible[0]['amount_krw']
                base['alternatives_krw']=[x['amount_krw'] for x in eligible[1:3]]
                base['scores']=eligible
                base['policy_adjusted']=initial!=base['amount_krw']
                base['reasons'].append(f'부조 목적 예외가 성립한다는 가상 조건에서 현금 {cap:,}원 기준 안의 후보만 재평가했습니다.')
            else:
                base={'status':'NO_POLICY_COMPLIANT_CANDIDATE','message':'확인된 조건부 금액 범위 안에 추천 후보가 없습니다.'}
        elif status in ('NEEDS_FACTS','NEEDS_EXPERT_REVIEW','POTENTIALLY_PROHIBITED'):
            # 일반 개인화 참고액은 행동 추천액과 구분한다. 법적 결과 미확정이면 송금액 반환 금지.
            base={'status':status,'message':legal['reason'],'reference_only_amount_krw':initial,
                  'missing_questions':legal['missing_questions'],
                  'disclaimer':'참고액은 법적 송금 가능 금액이 아닙니다.'}
        else:
            base['reasons'].append('등록된 합성 인물·업무 관계에서 직무 관련 경조사 한도 적용이 확인되지 않아 일반 추천을 유지했습니다.')
    if profile_access is not None:
        legal['profile_access']=profile_access
    if relation_assessment is not None:
        legal['relationship_status']=relation_assessment['status']
        legal['sender_profile_used']=relation_assessment['sender_profile_used']
        legal['relation_source']=relation_assessment['source']
        legal['missing_questions']=list(dict.fromkeys(legal['missing_questions']+relation_assessment['missing_questions']))
        if base['status'] != 'RECOMMENDED':
            base['missing_questions']=legal['missing_questions']
    base['legal_assessment']=legal
    base['evidence_trace']={'applied_ids':evidence['applied_ids'],'excluded_ids':evidence['excluded_ids']}
    return {'result':base,'evidence':evidence['evidence'],'query_plan':query_plan}