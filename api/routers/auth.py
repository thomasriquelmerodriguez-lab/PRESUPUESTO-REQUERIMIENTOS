from fastapi import APIRouter, Request, Response

from app.api.deps import CurrentUser, CsrfUser, DbDep
from app.schemas.auth import LoginOption, LoginRequest, SessionResponse
from app.schemas.common import MessageResponse
from app.services.audit import audit_action
from app.services.auth import create_session, delete_session, random_token, token_digest
from app.services.users import login_options

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/login-options", response_model=list[LoginOption])
def available_login_users(db: DbDep):
    return login_options(db)


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: DbDep):
    user, csrf_token = create_session(
        db,
        request,
        response,
        password=payload.password,
        user_id=payload.user_id,
        username=payload.username,
    )
    audit_action(
        db,
        request,
        user=user,
        action="auth.login",
        entity_type="session",
        result="success",
        details={"areas": user["areas"]},
    )
    db.commit()
    return {"user": user, "csrf_token": csrf_token}


@router.get("/session", response_model=SessionResponse)
def session(request: Request, db: DbDep, user: CurrentUser):
    csrf_token = random_token(24)
    request.state.session_record.csrf_hash = token_digest(csrf_token)
    db.commit()
    return {"user": user, "csrf_token": csrf_token}


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response, db: DbDep, user: CsrfUser):
    audit_action(
        db,
        request,
        user=user,
        action="auth.logout",
        entity_type="session",
        result="success",
    )
    delete_session(db, request, response)
    db.commit()
    return {"message": "Sesión cerrada correctamente."}
