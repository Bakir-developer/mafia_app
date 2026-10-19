from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from mysite.api.dependencies import get_current_user, is_admin
from mysite.db.database import SessionLocal
from mysite.db.models import Room, RoomPlayer, RoomStatus, UserProfile
from mysite.db.schema import (RoomCreateSchema, RoomUpdateSchema, RoomListSchema, RoomDetailSchema,)
from mysite.game_logic import validate_role_counts

room_router = APIRouter(prefix='/room', tags=['Room'])

MIN_ROOM_PLAYERS = 4
MAX_ROOM_PLAYERS = 30
MIN_PHASE_SECONDS = 10
MAX_PHASE_SECONDS = 600

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _bad_request(detail: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

def _validate_room_config(max_players: int, mafia: int, doctor: int, commissar: int,
                          day_time: int, night_time: int):
    if not (MIN_ROOM_PLAYERS <= max_players <= MAX_ROOM_PLAYERS):
        _bad_request(f'max_players must be between {MIN_ROOM_PLAYERS} and {MAX_ROOM_PLAYERS}')
    error = validate_role_counts(max_players, mafia, doctor, commissar)
    if error:
        _bad_request(error)
    for value in (day_time, night_time):
        if not (MIN_PHASE_SECONDS <= value <= MAX_PHASE_SECONDS):
            _bad_request(f'day_time/night_time must be between {MIN_PHASE_SECONDS} and {MAX_PHASE_SECONDS} seconds')

def _get_room_or_404(db: Session, room_id: int) -> Room:
    room_db = db.query(Room).filter(Room.id == room_id).first()
    if not room_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room not found")
    return room_db

def _check_owner_or_admin(room: Room, user: UserProfile):
    if room.owner_id != user.id and not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only the room owner can do this")

@room_router.post('/create', response_model=RoomDetailSchema)
def create_room(room_data: RoomCreateSchema, db: Session = Depends(get_db),
                current_user: UserProfile = Depends(get_current_user)):
    _validate_room_config(room_data.max_players, room_data.mafia_count, room_data.doctor_count,
                          room_data.commissar_count, room_data.day_time, room_data.night_time)

    data = room_data.dict()
    data['owner_id'] = current_user.id
    room_db = Room(**data)
    db.add(room_db)
    db.commit()
    db.refresh(room_db)
    return room_db


@room_router.get('/list', response_model=List[RoomListSchema])
def list_room(db: Session = Depends(get_db)):
    return db.query(Room).all()


@room_router.get('/detail', response_model=RoomDetailSchema)
def detail_room(room_id: int, db: Session = Depends(get_db)):
    return _get_room_or_404(db, room_id)


@room_router.put('/update/{room_id}', response_model=RoomDetailSchema)
def update_room(room_id: int, room_data: RoomUpdateSchema, db: Session = Depends(get_db),
                current_user: UserProfile = Depends(get_current_user)):
    room_db = _get_room_or_404(db, room_id)
    _check_owner_or_admin(room_db, current_user)

    update_data = room_data.dict(exclude_unset=True)

    if 'status' in update_data and not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only admin can change room status")

    if room_db.status != RoomStatus.WAITING and not is_admin(current_user):
        _bad_request("room can only be edited while it is waiting for players")

    if 'max_players' in update_data:
        new_max = update_data['max_players']
        if not (MIN_ROOM_PLAYERS <= new_max <= MAX_ROOM_PLAYERS):
            _bad_request(f'max_players must be between {MIN_ROOM_PLAYERS} and {MAX_ROOM_PLAYERS}')
        joined = db.query(RoomPlayer).filter(RoomPlayer.room_id == room_id).count()
        if new_max < joined:
            _bad_request("max_players is less than the number of players already in the room")
        error = validate_role_counts(new_max, room_db.mafia_count, room_db.doctor_count, room_db.commissar_count)
        if error:
            _bad_request(error)

    for key, value in update_data.items():
        setattr(room_db, key, value)

    db.commit()
    db.refresh(room_db)
    return room_db


@room_router.delete('/delete/{room_id}', response_model=dict)
def delete_room(room_id: int, db: Session = Depends(get_db),
                current_user: UserProfile = Depends(get_current_user)):
    room_db = _get_room_or_404(db, room_id)
    _check_owner_or_admin(room_db, current_user)
    db.delete(room_db)
    db.commit()
    return {'status': 'success deleted'}