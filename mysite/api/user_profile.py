from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from mysite.api.dependencies import get_current_user, is_admin
from mysite.api.statistic import build_statistic, get_or_create_statistic
from mysite.db.database import SessionLocal
from mysite.db.models import UserProfile
from mysite.db.schema import (UserProfileListSchema, UserProfileDetailSchema, UserProfileUpdateSchema)

user_router = APIRouter(prefix='/user', tags=['User'])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _check_self_or_admin(user_id: int, current_user: UserProfile):
    if current_user.id != user_id and not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='You can only modify your own account')

@user_router.get('/list', response_model=List[UserProfileListSchema])
def list_user(db: Session = Depends(get_db)):
    return db.query(UserProfile).all()


@user_router.get('/detail', response_model=UserProfileDetailSchema)
def detail_user(user_id: int, db: Session = Depends(get_db)):
    user_db = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return user_db

@user_router.put('/update')
def update_user(user_id: int, user_data: UserProfileUpdateSchema, db: Session = Depends(get_db),
                current_user: UserProfile = Depends(get_current_user)):
    _check_self_or_admin(user_id, current_user)

    user_db = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    update_data = user_data.dict(exclude_unset=True)

    if update_data.get('username') and update_data['username'] != user_db.username:
        if db.query(UserProfile).filter(UserProfile.username == update_data['username']).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Such a username exists.')
    if update_data.get('email') and update_data['email'] != user_db.email:
        if db.query(UserProfile).filter(UserProfile.email == update_data['email']).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Such an email exists.')

    for key, value in update_data.items():
        setattr(user_db, key, value)

    db.commit()
    db.refresh(user_db)
    return user_db

@user_router.delete('/delete')
def delete_user(user_id: int, db: Session = Depends(get_db),
                current_user: UserProfile = Depends(get_current_user)):
    _check_self_or_admin(user_id, current_user)

    user_db = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    db.delete(user_db)
    db.commit()
    return {'message': 'success deleted'}


@user_router.get('/profile/{user_id}')
def user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    statistic = get_or_create_statistic(db, user_id)
    return {
        'username': user.username,
        'email': user.email,
        'age': user.age,
        **build_statistic(statistic),
    }