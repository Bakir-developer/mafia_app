from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from mysite.api.dependencies import get_current_user, is_admin
from mysite.db.database import SessionLocal
from mysite.db.models import RoomPlayer, Room, RoomStatus, UserProfile
from mysite.db.schema import (RoomPlayerCreateSchema, RoomPlayerListSchema, RoomPlayerDetailSchema,)

room_player_router = APIRouter(prefix='/room-player', tags=['RoomPlayer'])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@room_player_router.post('/create', response_model=RoomPlayerDetailSchema)
def create_room_player(room_player_data: RoomPlayerCreateSchema, db: Session = Depends(get_db),
                       current_user: UserProfile = Depends(get_current_user)):
    user_id = room_player_data.user_id if room_player_data.user_id is not None else current_user.id
    if user_id != current_user.id and not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="you can only join as yourself")

    room = db.query(Room).filter(Room.id == room_player_data.room_id).with_for_update().first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if room.status != RoomStatus.WAITING:
        raise HTTPException(status_code=400, detail="room is not accepting players")

    existing = (db.query(RoomPlayer)
        .filter(RoomPlayer.room_id == room.id, RoomPlayer.user_id == user_id).first())
    if existing:
        raise HTTPException(status_code=400, detail="user already joined this room")

    joined = db.query(RoomPlayer).filter(RoomPlayer.room_id == room.id).count()
    if joined >= room.max_players:
        raise HTTPException(status_code=400, detail="room is full")

    room_player_db = RoomPlayer(room_id=room.id, user_id=user_id)
    db.add(room_player_db)
    db.commit()
    db.refresh(room_player_db)
    return room_player_db


@room_player_router.get('/list', response_model=List[RoomPlayerListSchema])
def list_room_player(room_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(RoomPlayer)
    if room_id is not None:
        query = query.filter(RoomPlayer.room_id == room_id)
    return query.all()


@room_player_router.get('/detail', response_model=RoomPlayerDetailSchema)
def detail_room_player(room_player_id: int, db: Session = Depends(get_db)):
    room_player_db = db.query(RoomPlayer).filter(RoomPlayer.id == room_player_id).first()
    if not room_player_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return room_player_db


@room_player_router.delete('/delete/{room_player_id}', response_model=dict)
def delete_room_player(room_player_id: int, db: Session = Depends(get_db),
                       current_user: UserProfile = Depends(get_current_user)):
    room_player_db = db.query(RoomPlayer).filter(RoomPlayer.id == room_player_id).first()
    if not room_player_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    room = db.query(Room).filter(Room.id == room_player_db.room_id).first()
    allowed = (
        room_player_db.user_id == current_user.id
        or (room is not None and room.owner_id == current_user.id)
        or is_admin(current_user)
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed to remove this player")

    if room is not None and room.status in (RoomStatus.IN_PROGRESS,) and not is_admin(current_user):
        raise HTTPException(status_code=400, detail="cannot leave a room while the game is in progress")

    db.delete(room_player_db)
    db.commit()
    return {'status': 'success deleted'}