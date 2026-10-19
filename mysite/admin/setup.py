from datetime import timedelta
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from sqladmin import Admin
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from mysite.api.auth import create_access_token, decode_token, verify_password
from mysite.config import SECRET_KEY
from mysite.db.database import engine, SessionLocal
from mysite.db.models import UserProfile, UserRole
from .view import (UserProfileView, UserStatisticView, RoomView, RoomPlayerView, ReviewView, GameView,
                   GamePlayerView, GameRoundView, NightActionView, VoteView, AchievementView,
                   UserAchievementView, FriendView, GroupView, ChatgroupView)

ADMIN_SESSION_HOURS = 8


def _find_admin(username: str, password: str):
    db = SessionLocal()
    try:
        user = db.query(UserProfile).filter(UserProfile.username == username).first()
        if user and user.role == UserRole.admin and verify_password(password, user.password):
            return user.id
        return None
    finally:
        db.close()


def _is_admin(user_id: int) -> bool:
    db = SessionLocal()
    try:
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        return bool(user and user.role == UserRole.admin)
    finally:
        db.close()


class AdminAuth(AuthenticationBackend):

    async def login(self, request: Request) -> bool:
        form = await request.form()
        user_id = await run_in_threadpool(_find_admin, str(form.get("username", "")), str(form.get("password", "")))
        if user_id is None:
            return False
        request.session["admin_token"] = create_access_token(
            {"user_id": user_id, "type": "admin"}, expires_delta=timedelta(hours=ADMIN_SESSION_HOURS))
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("admin_token")
        if not token:
            return False
        try:
            payload = decode_token(token, expected_type="admin")
        except Exception:
            return False
        return await run_in_threadpool(_is_admin, payload["user_id"])


def setup_admin(app: FastAPI):
    admin = Admin(app, engine=engine, authentication_backend=AdminAuth(secret_key=SECRET_KEY))
    for view in (UserProfileView, UserStatisticView, RoomView, RoomPlayerView, ReviewView, GameView,
                 GamePlayerView, GameRoundView, NightActionView, VoteView, AchievementView,
                 UserAchievementView, FriendView, GroupView, ChatgroupView):
        admin.add_view(view)
