from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from mysite.api.dependencies import get_current_user, is_admin
from mysite.db.database import SessionLocal
from mysite.db.models import Review, Room, UserProfile
from mysite.db.schema import ReviewCreateSchema, ReviewUpdateSchema, ReviewListSchema, ReviewDetailSchema

review_router = APIRouter(prefix='/review', tags=['Review'])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_review_or_404(db: Session, review_id: int) -> Review:
    review_db = db.query(Review).filter(Review.id == review_id).first()
    if not review_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    return review_db

def _check_author_or_admin(review: Review, user: UserProfile):
    if review.user_id != user.id and not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only the author can modify this review")


@review_router.post('/create', response_model=ReviewDetailSchema)
def create_review(review_data: ReviewCreateSchema, db: Session = Depends(get_db),
                  current_user: UserProfile = Depends(get_current_user)):
    if not db.query(Room).filter(Room.id == review_data.room_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room not found")

    if not (1 <= review_data.stars <= 5):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="stars must be between 1 and 5")

    data = review_data.dict()
    data['user_id'] = current_user.id
    review_db = Review(**data)
    db.add(review_db)
    db.commit()
    db.refresh(review_db)
    return review_db


@review_router.get('/list', response_model=List[ReviewListSchema])
def list_review(room_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Review)
    if room_id is not None:
        query = query.filter(Review.room_id == room_id)
    return query.all()


@review_router.get('/detail', response_model=ReviewDetailSchema)
def detail_review(review_id: int, db: Session = Depends(get_db)):
    return _get_review_or_404(db, review_id)


@review_router.put('/update/{review_id}', response_model=ReviewDetailSchema)
def update_review(review_id: int, review_data: ReviewUpdateSchema, db: Session = Depends(get_db),
                  current_user: UserProfile = Depends(get_current_user)):
    review_db = _get_review_or_404(db, review_id)
    _check_author_or_admin(review_db, current_user)

    update_data = review_data.dict(exclude_unset=True)
    if "stars" in update_data and not (1 <= update_data["stars"] <= 5):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="stars must be between 1 and 5")

    for key, value in update_data.items():
        setattr(review_db, key, value)

    db.commit()
    db.refresh(review_db)
    return review_db


@review_router.delete('/delete/{review_id}', response_model=dict)
def delete_review(review_id: int, db: Session = Depends(get_db),
                  current_user: UserProfile = Depends(get_current_user)):
    review_db = _get_review_or_404(db, review_id)
    _check_author_or_admin(review_db, current_user)
    db.delete(review_db)
    db.commit()
    return {'status': 'success deleted'}