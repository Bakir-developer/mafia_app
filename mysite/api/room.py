from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional

from mysite.db.database import SessionLocal
from mysite.db.models import Room
from mysite.db.schema import (
    RoomCreateSchema,
    RoomUpdateSchema,
    RoomListSchema,
    RoomDetailSchema,
)

room_router = APIRouter(prefix='/room', tags=['Room'])
room_player_router = APIRouter(prefix='/room-player', tags=['RoomPlayer'])


async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@room_router.post('/create', response_model=RoomDetailSchema)
async def create_room(room_data: RoomCreateSchema, db: Session = Depends(get_db)):
    room_db = Room(**room_data.dict())
    db.add(room_db)
    db.commit()
    db.refresh(room_db)
    return room_db


@room_router.get('/list', response_model=List[RoomListSchema])
async def list_room(db: Session = Depends(get_db)):
    room = db.query(Room).all()
    return room


@room_router.get('/detail', response_model=RoomDetailSchema)
async def detail_room(room_id: int, db: Session = Depends(get_db)):
    room_db = db.query(Room).filter(Room.id == room_id).first()
    if not room_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room not found")
    return room_db


@room_router.put('/update/{room_id}', response_model=RoomDetailSchema)
async def update_room(room_id: int, room_data: RoomUpdateSchema, db: Session = Depends(get_db)):
    room_db = db.query(Room).filter(Room.id == room_id).first()
    if not room_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room not found")

    for key, value in room_data.dict(exclude_unset=True).items():
        setattr(room_db, key, value)

    db.commit()
    db.refresh(room_db)
    return room_db


@room_router.delete('/delete/{room_id}', response_model=dict)
async def delete_room(room_id: int, db: Session = Depends(get_db)):
    room_db = db.query(Room).filter(Room.id == room_id).first()
    if not room_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room not found")
    db.delete(room_db)
    db.commit()
    return {'status': 'success deleted'}










