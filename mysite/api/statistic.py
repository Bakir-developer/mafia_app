from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from mysite.db.database import SessionLocal
from mysite.db.models import UserProfile, UserStatistic
from mysite.game_logic import most_played_role

statistic_router = APIRouter(prefix="/statistic", tags=["Statistic"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_statistic(db: Session, user_id: int) -> UserStatistic:
    statistic = db.query(UserStatistic).filter(UserStatistic.user_id == user_id).first()
    if not statistic:
        statistic = UserStatistic(user_id=user_id)
        db.add(statistic)
        db.commit()
        db.refresh(statistic)
    return statistic

def build_statistic(statistic: UserStatistic) -> dict:
    winrate = 0
    average_game_time = 0
    if statistic.games_played > 0:
        winrate = statistic.wins / statistic.games_played * 100
        average_game_time = statistic.total_game_time / statistic.games_played

    roles = {
        "mafia": statistic.mafia_games,
        "citizen": statistic.citizen_games,
        "detective": statistic.detective_games,
        "doctor": statistic.doctor_games,
    }
    return {
        "games_played": statistic.games_played,
        "wins": statistic.wins,
        "losses": statistic.losses,
        "winrate": round(winrate, 2),
        "average_game_time": round(average_game_time, 2),
        "total_game_time": statistic.total_game_time,
        "most_played_role": most_played_role(roles),
    }

@statistic_router.get("/{user_id}")
def get_statistic(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    statistic = get_or_create_statistic(db, user_id)
    return {"username": user.username, **build_statistic(statistic)}