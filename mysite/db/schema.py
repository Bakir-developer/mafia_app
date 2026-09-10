from socketserver import BaseServer
from datetime import datetime
from typing import Optional

from sqlalchemy import Text
from pydantic import BaseModel, EmailStr

from mysite.db.models import UserRole, RoomStatus, GameRole, GamePhase, GameWinner, EliminationReason, NightActionType, AchievementCode


class UserProfileCreateSchema(BaseModel):
    id: int
    username:str
    email: EmailStr
    age:int
    profile_image:str
    role: UserRole
    password: str


class UserStatisticSchema(BaseModel):
    username: str
    games_played: int
    wins: int
    losses: int
    total_game_time: float
    mafia_games: int
    citizen_games: int
    detective_games: int
    doctor_games: int

class RoomSchema(BaseModel):
    id: int
    room_name: str
    max_player: int
    status: RoomStatus
    created_at: datetime
    started_at: datetime
    finished_at: datetime
    owner_id: int

class RoomPlayerSchema(BaseModel):
    id: int
    joined_at: datetime
    room_id: int
    user_id: int

class ReviewSchema(BaseModel):
    id: int
    user_id : int
    room_id: int
    text: Text
    stars: int

class GameSchema(BaseModel):
    id: int
    room_id: int
    current_round: int
    current_phase: Optional[GamePhase]
    winner: Optional[GameWinner]
    started_at: datetime
    finished_at: Optional[datetime]


class GamePlayerSchema(BaseModel):
    id: int
    game_id: int
    user_id: int
    role: GameRole
    is_alive: bool
    eliminated_round: Optional[int]
    eliminated_reason: Optional[EliminationReason]


class GameRoundSchema(BaseModel):
    id: int
    game_id: int
    round_number: int
    killed_player_id: Optional[int]
    saved_by_doctor: bool
    eliminated_player_id: Optional[int]
    created_at: datetime


class NightActionSchema(BaseModel):
    id: int
    round_id: int
    actor_id: int
    target_id: int
    action_type: NightActionType
    created_at: datetime


class VoteSchema(BaseModel):
    id: int
    round_id: int
    voter_id: int
    target_id: int
    created_at: datetime


class AchievementSchema(BaseModel):
    id: int
    code: AchievementCode
    title: str
    description: str


class UserAchievementSchema(BaseModel):
    id: int
    user_id: int
    achievement_id: int
    unlocked_at: datetime

