"""v3 synthetic demo profile store. Demo user selector is NOT authentication."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OCCUPATIONS = {
    'unknown': '미입력', 'private_employee': '민간기업 직원',
    'civil_servant': '공무원', 'public_institution_employee': '공공기관 직원',
    'school_teacher': '교직원', 'journalist': '언론인', 'other': '기타'
}
INSTITUTIONS = {'unknown', 'private_company', 'government', 'public_institution', 'school', 'press', 'other'}
VISIBILITIES = {'none', 'accepted_contacts'}
DUTY_ROLES = {'unknown','general','procurement','licensing','evaluation','supervision','audit','hr'}
# 직업은 실재 여부 검증된 것이 아니라 사용자 본인의 합성 입력이다.
SEEDS = {
    'U002': ('private_employee','private_company',1,'accepted_contacts'),
    'U005': ('private_employee','private_company',0,'none'),
    'U006': ('civil_servant','government',1,'accepted_contacts'),
    'U007': ('civil_servant','government',1,'accepted_contacts'),
    'U008': ('civil_servant','government',1,'accepted_contacts'),
    'U009': ('civil_servant','government',1,'accepted_contacts'),
    'V4U001': ('school_teacher','school',1,'accepted_contacts'),
    'V4U002': ('private_employee','private_company',1,'accepted_contacts'),
    'V4U003': ('civil_servant','government',0,'none'),
    'V4U004': ('civil_servant','government',1,'accepted_contacts'),
    'V4U005': ('civil_servant','government',1,'accepted_contacts'),
    'V4U006': ('civil_servant','government',1,'accepted_contacts'),
    'V4U011': ('private_employee','private_company',1,'accepted_contacts'),
    'V4U012': ('private_employee','private_company',1,'accepted_contacts'),
    'V4U013': ('private_employee','private_company',1,'accepted_contacts'),
    'V4U014': ('private_employee','private_company',1,'accepted_contacts'),
    'V4U015': ('private_employee','private_company',1,'accepted_contacts'),
    'V4U016': ('private_employee','private_company',1,'accepted_contacts'),
    'V4U017': ('private_employee','private_company',1,'accepted_contacts'),
    'V4U018': ('private_employee','private_company',1,'accepted_contacts'),
    'V4U019': ('private_employee','private_company',1,'accepted_contacts'),
    'V4U020': ('private_employee','private_company',1,'accepted_contacts'),
}

class ProfileStore:
    def __init__(self, db_path: Path | str | None = None, *, seed: bool = True):
        self.db_path = str(db_path or ROOT/'data'/'demo_profiles.db')
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY, occupation TEXT NOT NULL DEFAULT 'unknown',
                institution TEXT NOT NULL DEFAULT 'unknown',
                allow_recommendation INTEGER NOT NULL DEFAULT 0,
                visibility TEXT NOT NULL DEFAULT 'none',
                updated_at TEXT NOT NULL)''')
            columns = {row[1] for row in db.execute('PRAGMA table_info(profiles)')}
            if 'duty_role' not in columns:
                db.execute("ALTER TABLE profiles ADD COLUMN duty_role TEXT NOT NULL DEFAULT 'unknown'")
            if seed:
                for user_id, (occupation, institution, consent, visibility) in SEEDS.items():
                    db.execute('''INSERT OR IGNORE INTO profiles
                        (user_id,occupation,institution,allow_recommendation,visibility,updated_at)
                        VALUES (?,?,?,?,?,?)''',
                        (user_id,occupation,institution,consent,visibility,'2026-10-31T00:00:00+00:00'))

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db_path,timeout=5)
        try:
            with db:yield db
        finally:
            db.close()

    def get(self, user_id: str) -> dict:
        with self.connect() as db:
            row = db.execute('SELECT occupation,institution,allow_recommendation,visibility,updated_at,duty_role FROM profiles WHERE user_id=?',(user_id,)).fetchone()
        if row is None:
            return {'occupation':'unknown','institution':'unknown','allow_recommendation':False,
                    'visibility':'none','updated_at':None,'duty_role':'unknown'}
        return {'occupation':row[0], 'institution':row[1], 'allow_recommendation':bool(row[2]),
                'visibility':row[3], 'updated_at':row[4], 'duty_role':row[5]}

    def put(self,user_id: str,*,occupation: str,institution: str,allow_recommendation: bool,visibility: str,duty_role: str='unknown') -> dict:
        if occupation not in OCCUPATIONS or institution not in INSTITUTIONS or visibility not in VISIBILITIES or duty_role not in DUTY_ROLES:
            raise ValueError('INVALID_PROFILE_FIELD')
        ts = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('''INSERT INTO profiles
                (user_id,occupation,institution,allow_recommendation,visibility,updated_at,duty_role)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                occupation=excluded.occupation,institution=excluded.institution,
                allow_recommendation=excluded.allow_recommendation,visibility=excluded.visibility,
                updated_at=excluded.updated_at,duty_role=excluded.duty_role''',
                (user_id,occupation,institution,int(allow_recommendation),visibility,ts,duty_role))
        return self.get(user_id)


def _accepted_connection(data:dict, viewer_id:str, target_id:str)->bool:
    return any(f['status']=='accepted' and f.get('allow_connection_for_recommendation') is True
               and {f['user_a_id'], f['user_b_id']}=={viewer_id,target_id}
               for f in data['friendships'])


def profile_for_recipient(*,store:ProfileStore,data:dict,viewer_id:str,person_id:str)->dict:
    """Never return a recipient's raw occupation to another account.
    The narrow returned policy properties are server-side inputs only.
    No fallback to hardcoded person-based v2 synthetic risk flags.
    """
    person=next((p for p in data['people'] if p['id']==person_id and p['owner_user_id']==viewer_id),None)
    if person is None:
        return {'access':'not_found', 'policy':None}
    target=person.get('linked_user_id')
    if not target or target==viewer_id or not _accepted_connection(data,viewer_id,target):
        return {'access':'not_authorized','policy':None}
    p=store.get(target)
    if not p['allow_recommendation'] or p['visibility']!='accepted_contacts':
        return {'access':'not_shared','policy':None}
    # 직업 문자열 그대로를 AI나 상대방에게 보내지 않고, 법 적용성 후보로만 변환.
    covered = 'unknown'
    if p['occupation']=='private_employee' and p['institution']=='private_company':
        covered='no'
    elif (p['occupation']=='civil_servant' and p['institution']=='government') or (
        p['occupation']=='school_teacher' and p['institution']=='school') or (
        p['occupation']=='journalist' and p['institution']=='press'):
        covered='yes'
    # 공공기관 범위가 기관마다 달라질 수 있어 보수적으로 미확정.
    return {'access':'consented', 'policy':{
        'covered':covered, 'duty_related':'unknown', 'exception_confirmed':'unknown',
        'conflict':'unknown', 'provenance':'self_reported_demo',
        'description':'회원이 추천 목적으로 제공한 직업 분류(미검증)'
    }}