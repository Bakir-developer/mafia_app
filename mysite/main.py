from fastapi import FastAPI
from mysite.api.room import room_router

Mafia_app = FastAPI(title='FastAPI Mafia_app')

Mafia_app.include_router(room_router)
# app.include_router(room_player_router)