from socketserver import BaseServer
from datetime import datetime
from sqlalchemy import Text
from pydantic import BaseModel, EmailStr

class UserProfileSchema(BaseModel):
    id: int
    username:str
    email: EmailStr
    age:int
    profile_image:str
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
