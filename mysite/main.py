from fastapi import FastAPI
from mysite.api.room import room_router
from mysite.api import user_profile, auth, statistic, room, room_player
from mysite.admin.setup import setup_admin

Mafia_app = FastAPI(title='FastAPI Mafia_app')

Mafia_app.include_router(room.room_router)
Mafia_app.include_router(room_player.room_player_router)
Mafia_app.include_router(user_profile.user_router)
Mafia_app.include_router(auth.auth_router)
Mafia_app.include_router(statistic.statistic_router)

setup_admin(Mafia_app)
