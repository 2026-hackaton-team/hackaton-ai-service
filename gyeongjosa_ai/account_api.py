"""회원가입·로그인·내 정보 수정 API. 세션은 Authorization: Bearer 토큰으로 확인한다."""

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_store import AccountStore, LoginInput, ProfileUpdateInput, SignupInput, workspace_owner


router = APIRouter(prefix="/api/auth")


def get_account_store():
    """계정 저장소를 반환한다. (테스트는 GYEONGJOSA_ACCOUNTS_DB로 바꾼다)"""
    return AccountStore()


def bearer_token(authorization: str = Header(default="")):
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def current_account(token: str = Depends(bearer_token), store: AccountStore = Depends(get_account_store)):
    profile = store.authenticate(token)
    if profile is None:
        raise HTTPException(401, "로그인이 필요해요.")
    return profile


def _session(result):
    return {**result, "workspaceOwner": workspace_owner(result["profile"]["username"])}


@router.post("/signup", status_code=201)
def signup(data: SignupInput, store: AccountStore = Depends(get_account_store)):
    return _session(store.signup(data))


@router.post("/login")
def login(data: LoginInput, store: AccountStore = Depends(get_account_store)):
    return _session(store.login(data))


@router.get("/me")
def me(profile=Depends(current_account)):
    return {"profile": profile, "workspaceOwner": workspace_owner(profile["username"])}


@router.put("/me")
def update_me(data: ProfileUpdateInput, profile=Depends(current_account),
              store: AccountStore = Depends(get_account_store)):
    return {"profile": store.update(profile["username"], data)}


@router.post("/logout", status_code=204)
def logout(token: str = Depends(bearer_token), store: AccountStore = Depends(get_account_store)):
    store.logout(token)
