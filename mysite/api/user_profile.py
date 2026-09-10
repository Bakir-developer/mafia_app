from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from mysite.db.database import SessionLocal
from mysite.db.models import UserProfile
from mysite.db.schema import UserProfileSchema
from typing import List

user_router = APIRouter(prefix='/user', tags=['User'])

async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@user_router.get('/list', response_model=List[UserProfileSchema])
async def list_user(db: Session= Depends(get_db)):
    user_db = db.query(UserProfile).all()
    return user_db

@user_router.get('/detail', response_model=UserProfileSchema)
async def detail_user(user_id: int, db: Session = Depends(get_db)):
    user_db = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Munday adam jok')
    return user_db

@user_router.put('/update')
async def update_user(user_id: int, user_data: UserProfileSchema, db: Session = Depends(get_db)):
    user_db = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mynday adam jok')
    for user_key, user_value in user_data.dict().items():
        setattr(user_db, user_key, user_value)
    db.commit()
    db.refresh(user_db)
    return user_db

@user_router.delete('/delete')
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    user_db = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Munday adam jok')
    db.delete(user_db)
    db.commit()
    return {'message': 'success deleted'}



