import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mysite.admin.setup import setup_admin
from mysite.api import (user_profile, auth, statistic, room, room_player, reviews,
                        game, night_action, websocket, friends)
from mysite.api.game import game_scheduler
from mysite.config import CORS_ORIGINS
from mysite.db.database import SessionLocal

logger = logging.getLogger(__name__)

def _seed_achievements():
    db = SessionLocal()
    try:
        night_action.seed_achievements(db)
    except Exception:
        db.rollback()
        logger.exception("Could not seed achievements (is the database migrated?)")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(_seed_achievements)
    scheduler_task = asyncio.create_task(game_scheduler())
    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

Mafia_app = FastAPI(title='FastAPI Mafia_app', lifespan=lifespan)
Mafia_app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Mafia_app.include_router(room.room_router)
Mafia_app.include_router(room_player.room_player_router)
Mafia_app.include_router(user_profile.user_router)
Mafia_app.include_router(auth.auth_router)
Mafia_app.include_router(statistic.statistic_router)
Mafia_app.include_router(reviews.review_router)
Mafia_app.include_router(game.game_router)
Mafia_app.include_router(game.game_player_router)
Mafia_app.include_router(game.game_round_router)
Mafia_app.include_router(night_action.night_action_router)
Mafia_app.include_router(night_action.vote_router)
Mafia_app.include_router(night_action.achievement_router)
Mafia_app.include_router(night_action.user_achievement_router)
Mafia_app.include_router(websocket.chat_router)
Mafia_app.include_router(friends.friend_router)

setup_admin(Mafia_app)
