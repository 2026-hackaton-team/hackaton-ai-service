"""회원가입·로그인·내 정보 수정 API.

세션은 HttpOnly 쿠키(maeum_session)로 주고받는다. 스크립트·테스트용으로 Authorization: Bearer 토큰도 받는다.
"""

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response

from .account_store import (SESSION_COOKIE, SESSION_DAYS, AccountStore, LoginInput, ProfileUpdateInput,
                            SignupInput, workspace_owner)


router = APIRouter(prefix="/api/auth")


def get_account_store():
    """계정 저장소를 반환한다. (테스트는 GYEONGJOSA_ACCOUNTS_DB로 바꾼다)"""
    return AccountStore()


def bearer_token(authorization: str = Header(default=""),
                 maeum_session: str | None = Cookie(default=None)):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return maeum_session or ""


def current_account(token: str = Depends(bearer_token), store: AccountStore = Depends(get_account_store)):
    profile = store.authenticate(token)
    if profile is None:
        raise HTTPException(401, "로그인이 필요해요.")
    return profile


def _refresh_ai_accounts():
    """회원 목록이 바뀌면 다음 AI·추천 요청이 최신 계정을 읽게 한다."""
    from .dependencies import get_service
    get_service.cache_clear()


def _session(result, response):
    response.set_cookie(SESSION_COOKIE, result["token"], max_age=SESSION_DAYS * 86400,
                        httponly=True, samesite="lax", secure=False, path="/")
    owner = workspace_owner(result["profile"]["username"])
    return {**result, "userId": owner, "workspaceOwner": owner}


@router.post("/signup", status_code=201)
def signup(data: SignupInput, response: Response, store: AccountStore = Depends(get_account_store)):
    result = _session(store.signup(data), response)
    _refresh_ai_accounts()
    return result


@router.post("/login")
def login(data: LoginInput, response: Response, store: AccountStore = Depends(get_account_store)):
    result = _session(store.login(data), response)
    _refresh_ai_accounts()
    return result


@router.get("/me")
def me(profile=Depends(current_account)):
    owner = workspace_owner(profile["username"])
    return {"profile": profile, "userId": owner, "workspaceOwner": owner}


@router.put("/me")
def update_me(data: ProfileUpdateInput, profile=Depends(current_account),
              store: AccountStore = Depends(get_account_store)):
    updated = store.update(profile["username"], data)
    _refresh_ai_accounts()
    return {"profile": updated}


@router.post("/logout", status_code=204)
def logout(response: Response, token: str = Depends(bearer_token),
           store: AccountStore = Depends(get_account_store)):
    store.logout(token)
    response.delete_cookie(SESSION_COOKIE, path="/")
