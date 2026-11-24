import os
import secrets
import time
from uuid import UUID

import jwt
from fastapi import HTTPException, Request
from starlette.responses import Response

from schemas.users import UserInfoResponse


COOKIE_NAME = "zjhx_print_session"
SESSION_SECONDS = 12 * 60 * 60
_SIGNING_KEY = os.environ.get("PRINT_SESSION_SECRET") or secrets.token_urlsafe(32)


def set_print_session(response: Response, user: UserInfoResponse, *, secure: bool) -> None:
    token = jwt.encode(
        {**user.model_dump(), "exp": int(time.time()) + SESSION_SECONDS},
        _SIGNING_KEY,
        algorithm="HS256",
    )
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True, secure=secure, samesite="lax", path="/api")


def get_print_session(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME, "")
    try:
        return jwt.decode(token, _SIGNING_KEY, algorithms=["HS256"], options={"require": ["exp", "role", "account", "id"]})
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录") from exc


def require_teacher(request: Request) -> None:
    if get_print_session(request)["role"] != "teacher":
        raise HTTPException(status_code=403, detail="该操作仅教师可用")


def require_student_login(request: Request, student_id: str, login_id: UUID) -> None:
    session = get_print_session(request)
    account_student_id = str(session.get("student_id") or "").strip().upper()
    if session["role"] != "student" or account_student_id != student_id:
        raise HTTPException(status_code=403, detail="只能为当前登录的学生生成建议或报告")
    if session.get("login_id") != login_id.hex:
        raise HTTPException(status_code=403, detail="登录编号已失效，请重新登录")
