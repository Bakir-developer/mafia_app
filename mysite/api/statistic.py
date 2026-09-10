from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from mysite.db.database import SessionLocal
from mysite.db.models import UserProfile, UserStatistic

statistic_router = APIRouter(
    prefix="/statistic",
    tags=["Statistic"]
)


async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@statistic_router.get("/{user_id}")
async def get_statistic(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    statistic = db.query(UserStatistic).filter(UserStatistic.user_id == user_id).first()

    if not statistic:
        statistic = UserStatistic(
            user_id=user_id,
            games_played=0,
            wins=0,
            losses=0,
            total_game_time=0,
            mafia_games=0,
            citizen_games=0,
            detective_games=0,
            doctor_games=0
        )

        db.add(statistic)
        db.commit()
        db.refresh(statistic)

    winrate = 0
    average_game_time = 0

    if statistic.games_played > 0:
        winrate = (statistic.wins / statistic.games_played) * 100

        average_game_time = (statistic.total_game_time / statistic.games_played)

    roles = {
        "mafia": statistic.mafia_games,
        "citizen": statistic.citizen_games,
        "detective": statistic.detective_games,
        "doctor": statistic.doctor_games
    }

    most_played_role = max(roles,key=roles.get)

    return {
        "username": user.username,
        "games_played": statistic.games_played,
        "wins": statistic.wins,
        "losses": statistic.losses,
        "winrate": round(winrate, 2),
        "average_game_time": round(average_game_time, 2),
        "total_game_time": statistic.total_game_time,
        "most_played_role": most_played_role
    }