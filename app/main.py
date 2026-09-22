from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR
from .db import init_db
from .embeddings import embed_one
from .errors import EmbeddingError
from .repository import (
    complete_report,
    create_report,
    create_session,
    create_user,
    delete_session,
    get_home,
    get_user_by_session,
    get_user_by_username,
)
from .schemas import (
    CompleteResponse,
    HomeResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ReportCreate,
    ReportSubmitResponse,
    UserOut,
)
from .security import SESSION_DAYS, hash_password, verify_password

SESSION_COOKIE = "lost_found_session"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="校园失物招领语义匹配",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.exception_handler(EmbeddingError)
async def embedding_error_handler(_, exc: EmbeddingError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def _optional_user(request: Request) -> dict | None:
    return get_user_by_session(request.cookies.get(SESSION_COOKIE))


def _require_user(request: Request) -> dict:
    user = _optional_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录。")
    return user


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


@app.post("/api/auth/register", response_model=UserOut)
def register(payload: RegisterRequest, response: Response) -> UserOut:
    if get_user_by_username(payload.username):
        raise HTTPException(status_code=409, detail="用户名已存在。")
    try:
        user = create_user(
            username=payload.username,
            password_hash=hash_password(payload.password),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="用户名已存在。") from exc

    token, _ = create_session(int(user["id"]))
    _set_session_cookie(response, token)
    return UserOut(**user)


@app.post("/api/auth/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response) -> UserOut:
    user = get_user_by_username(payload.username)
    if not user or not verify_password(payload.password, str(user["password_hash"])):
        raise HTTPException(status_code=401, detail="用户名或密码错误。")

    token, _ = create_session(int(user["id"]))
    _set_session_cookie(response, token)
    return UserOut(id=int(user["id"]), username=str(user["username"]))


@app.post("/api/auth/logout", response_model=MessageResponse)
def logout(request: Request, response: Response) -> MessageResponse:
    delete_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return MessageResponse(ok=True)


@app.get("/api/home", response_model=HomeResponse)
def home(request: Request) -> HomeResponse:
    user = _optional_user(request)
    return HomeResponse(**get_home(int(user["id"]) if user else None))


@app.post("/api/report", response_model=ReportSubmitResponse)
def submit_report(payload: ReportCreate, request: Request) -> ReportSubmitResponse:
    user = _require_user(request)
    embedding = embed_one(payload.description)
    report_id, matches = create_report(
        user_id=int(user["id"]),
        kind=payload.kind,
        description=payload.description,
        location=payload.location,
        happened_at=payload.happened_at,
        contact=payload.contact,
        embedding=embedding,
    )
    return ReportSubmitResponse(report_id=report_id, match_count=len(matches))


@app.post("/api/reports/{report_id}/complete", response_model=CompleteResponse)
def confirm_found(report_id: int, request: Request) -> CompleteResponse:
    user = _require_user(request)
    try:
        deleted_ids = complete_report(int(user["id"]), report_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return CompleteResponse(deleted_report_ids=deleted_ids)


app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
