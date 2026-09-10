from .view import (UserProfileView, UserStatisticView, RoomView, RoomPlayerView, ReviewView,
                   GameView, GamePlayerView, GameRoundView, NightActionView, VoteView, AchievementView, UserAchievementView)
from sqladmin import Admin
from fastapi import FastAPI
from mysite.db.database import engine

def setup_admin(app: FastAPI):
    admin = Admin(app, engine=engine)
    admin.add_view(UserProfileView)
    admin.add_view(UserStatisticView)
    admin.add_view(RoomView)
    admin.add_view(RoomPlayerView)
    admin.add_view(ReviewView)
    admin.add_view(GameView)
    admin.add_view(GamePlayerView)
    admin.add_view(GameRoundView)
    admin.add_view(NightActionView)
    admin.add_view(VoteView)
    admin.add_view(AchievementView)
    admin.add_view(UserAchievementView)