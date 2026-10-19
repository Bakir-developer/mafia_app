from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from mysite.api.dependencies import get_current_user, get_admin_user, is_admin
from mysite.db.database import SessionLocal
from mysite.db.models import (NightAction, Vote, Achievement, UserAchievement, GameRound, GamePlayer, GamePhase,
                              UserProfile, UserStatistic, AchievementCode, Game, GameWinner, GameRole, NightActionType)
from mysite.db.schema import (NightActionCreateSchema, NightActionDetailSchema, VoteCreateSchema,
                              VoteDetailSchema, AchievementCreateSchema, AchievementUpdateSchema,
                              AchievementListSchema, AchievementDetailSchema, UserAchievementListSchema,
                              UserAchievementDetailSchema)

night_action_router = APIRouter(prefix='/night-action', tags=['NightAction'])
vote_router = APIRouter(prefix='/vote', tags=['Vote'])
achievement_router = APIRouter(prefix='/achievement', tags=['Achievement'])
user_achievement_router = APIRouter(prefix='/user-achievement', tags=['UserAchievement'])

DEFAULT_ACHIEVEMENTS = {
    AchievementCode.FIRST_WIN: ("Первая победа", "Выиграйте свою первую игру"),
    AchievementCode.MAFIA_MASTERMIND: ("Криминальный авторитет", "Победите за мафию"),
    AchievementCode.GUARDIAN_ANGEL: ("Ангел-хранитель", "Спасите игрока, выбранного мафией"),
    AchievementCode.SHERLOCK: ("Шерлок", "Найдите мафию проверкой комиссара"),
    AchievementCode.SURVIVOR: ("Выживший", "Доживите до конца игры"),
    AchievementCode.PERFECT_TOWN: ("Идеальный город", "Выиграйте за мирных, оставшись в живых"),
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_achievements(db: Session):
    existing = {code for (code,) in db.query(Achievement.code).all()}
    for code, (title, description) in DEFAULT_ACHIEVEMENTS.items():
        if code not in existing:
            db.add(Achievement(code=code, title=title, description=description))
    db.commit()

def _check_round_and_players(db: Session, round_id: int, *player_ids: int):
    round_db = db.query(GameRound).filter(GameRound.id == round_id).first()
    if not round_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game round not found")

    for player_id in player_ids:
        player_db = db.query(GamePlayer).filter(GamePlayer.id == player_id).first()
        if not player_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"game player {player_id} not found")
        if player_db.game_id != round_db.game_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"game player {player_id} does not belong to this game",
            )
    return round_db


def _bad_request(detail: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

@night_action_router.post('/create', response_model=NightActionDetailSchema)
def create_night_action(
    action_data: NightActionCreateSchema,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    round_db = _check_round_and_players(db, action_data.round_id, action_data.actor_id, action_data.target_id)

    actor = db.query(GamePlayer).filter(GamePlayer.id == action_data.actor_id).with_for_update().first()
    target = db.query(GamePlayer).filter(GamePlayer.id == action_data.target_id).first()
    game = db.query(Game).filter(Game.id == round_db.game_id).first()

    if actor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your player")

    if game.winner is not None:
        _bad_request("game is finished")

    if not actor.is_alive:
        _bad_request("dead players cannot act")

    if game.current_phase != GamePhase.NIGHT:
        _bad_request("not night phase")

    if round_db.round_number != game.current_round:
        _bad_request("this is not the current round")

    expected_role = {
        NightActionType.KILL: GameRole.mafia,
        NightActionType.HEAL: GameRole.doctor,
        NightActionType.CHECK: GameRole.commissar,
    }[action_data.action_type]

    if actor.role != expected_role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="wrong role for this action")

    if not target.is_alive:
        _bad_request("target is dead")

    if action_data.action_type == NightActionType.KILL and target.role == GameRole.mafia:
        _bad_request("mafia cannot kill a mafia member")

    if action_data.action_type == NightActionType.CHECK and target.id == actor.id:
        _bad_request("you cannot check yourself")

    existing = (
        db.query(NightAction)
        .filter(NightAction.round_id == action_data.round_id, NightAction.actor_id == action_data.actor_id)
        .first()
    )

    if existing and action_data.action_type == NightActionType.CHECK:
        _bad_request("commissar can check only once per night")

    if existing:
        existing.target_id = action_data.target_id
        db.commit()
        db.refresh(existing)
        action_db = existing
    else:
        action_db = NightAction(**action_data.dict())
        db.add(action_db)
        db.commit()
        db.refresh(action_db)

    response = NightActionDetailSchema.from_orm(action_db).dict()
    if action_data.action_type == NightActionType.CHECK:
        response["is_mafia"] = target.role == GameRole.mafia

    return response


def _night_actions_query(db: Session, user: UserProfile):
    query = db.query(NightAction)
    if is_admin(user):
        return query
    my_ids = [pid for (pid,) in db.query(GamePlayer.id).filter(GamePlayer.user_id == user.id).all()]
    return (query.join(GameRound, NightAction.round_id == GameRound.id)
            .join(Game, Game.id == GameRound.game_id)
            .filter(or_(NightAction.actor_id.in_(my_ids), Game.winner.isnot(None))))


@night_action_router.get('/list', response_model=List[NightActionDetailSchema])
def list_night_action(round_id: Optional[int] = None, db: Session = Depends(get_db),
                      current_user: UserProfile = Depends(get_current_user)):
    query = _night_actions_query(db, current_user)
    if round_id is not None:
        query = query.filter(NightAction.round_id == round_id)
    return query.all()


@night_action_router.get('/detail', response_model=NightActionDetailSchema)
def detail_night_action(action_id: int, db: Session = Depends(get_db),
                        current_user: UserProfile = Depends(get_current_user)):
    action_db = _night_actions_query(db, current_user).filter(NightAction.id == action_id).first()
    if not action_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="night action not found")
    return action_db


@vote_router.post('/create', response_model=VoteDetailSchema)
def create_vote(vote_data: VoteCreateSchema, db: Session = Depends(get_db),
                current_user: UserProfile = Depends(get_current_user)):
    round_db = _check_round_and_players(db, vote_data.round_id, vote_data.voter_id, vote_data.target_id)

    game = db.query(Game).filter(Game.id == round_db.game_id).first()
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game not found")

    if game.winner is not None:
        _bad_request("game is finished")

    if game.current_phase != GamePhase.VOTING:
        _bad_request("voting is not active")

    voter = (db.query(GamePlayer)
             .filter(GamePlayer.id == vote_data.voter_id, GamePlayer.game_id == game.id)
             .with_for_update().first())
    target = db.query(GamePlayer).filter(GamePlayer.id == vote_data.target_id, GamePlayer.game_id == game.id).first()

    if not voter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="voter not found")
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="target not found")

    if voter.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your player")
    if not voter.is_alive:
        _bad_request("dead players cannot vote")
    if not target.is_alive:
        _bad_request("cannot vote for dead player")
    if voter.id == target.id:
        _bad_request("cannot vote for yourself")
    if round_db.round_number != game.current_round:
        _bad_request("this is not the current round")

    existing_vote = (db.query(Vote)
                     .filter(Vote.round_id == vote_data.round_id, Vote.voter_id == vote_data.voter_id)
                     .first())
    if existing_vote:
        existing_vote.target_id = vote_data.target_id
        db.commit()
        db.refresh(existing_vote)
        return existing_vote

    vote_db = Vote(round_id=vote_data.round_id, voter_id=vote_data.voter_id, target_id=vote_data.target_id)
    db.add(vote_db)
    db.commit()
    db.refresh(vote_db)
    return vote_db


def _votes_query(db: Session, user: UserProfile):
    query = db.query(Vote)
    if is_admin(user):
        return query
    my_ids = [pid for (pid,) in db.query(GamePlayer.id).filter(GamePlayer.user_id == user.id).all()]
    return (query.join(GameRound, Vote.round_id == GameRound.id)
            .join(Game, Game.id == GameRound.game_id)
            .filter(or_(Vote.voter_id.in_(my_ids),
                        Game.winner.isnot(None),
                        GameRound.round_number < Game.current_round)))


@vote_router.get('/list', response_model=List[VoteDetailSchema])
def list_vote(round_id: Optional[int] = None, db: Session = Depends(get_db),
              current_user: UserProfile = Depends(get_current_user)):
    query = _votes_query(db, current_user)
    if round_id is not None:
        query = query.filter(Vote.round_id == round_id)
    return query.all()


@vote_router.get('/detail', response_model=VoteDetailSchema)
def detail_vote(vote_id: int, db: Session = Depends(get_db),
                current_user: UserProfile = Depends(get_current_user)):
    vote_db = _votes_query(db, current_user).filter(Vote.id == vote_id).first()
    if not vote_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vote not found")
    return vote_db


@achievement_router.post('/create', response_model=AchievementDetailSchema)
def create_achievement(achievement_data: AchievementCreateSchema, db: Session = Depends(get_db),
                       admin: UserProfile = Depends(get_admin_user)):
    existing = db.query(Achievement).filter(Achievement.code == achievement_data.code).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="achievement with this code already exists")

    achievement_db = Achievement(**achievement_data.dict())
    db.add(achievement_db)
    db.commit()
    db.refresh(achievement_db)
    return achievement_db


@achievement_router.get('/list', response_model=List[AchievementListSchema])
def list_achievement(db: Session = Depends(get_db)):
    return db.query(Achievement).all()


@achievement_router.get('/detail', response_model=AchievementDetailSchema)
def detail_achievement(achievement_id: int, db: Session = Depends(get_db)):
    achievement_db = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not achievement_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="achievement not found")
    return achievement_db


@achievement_router.put('/update/{achievement_id}', response_model=AchievementDetailSchema)
def update_achievement(achievement_id: int, achievement_data: AchievementUpdateSchema,
                       db: Session = Depends(get_db), admin: UserProfile = Depends(get_admin_user)):
    achievement_db = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not achievement_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="achievement not found")

    for key, value in achievement_data.dict(exclude_unset=True).items():
        setattr(achievement_db, key, value)

    db.commit()
    db.refresh(achievement_db)
    return achievement_db


@achievement_router.delete('/delete/{achievement_id}', response_model=dict)
def delete_achievement(achievement_id: int, db: Session = Depends(get_db),
                       admin: UserProfile = Depends(get_admin_user)):
    achievement_db = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not achievement_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="achievement not found")
    db.delete(achievement_db)
    db.commit()
    return {'status': 'success deleted'}


def unlock_achievement(db: Session, user_id: int, achievement_code: AchievementCode):
    achievement = db.query(Achievement).filter(Achievement.code == achievement_code).first()
    if not achievement:
        return None

    existing = (db.query(UserAchievement)
                .filter(UserAchievement.user_id == user_id, UserAchievement.achievement_id == achievement.id).first())
    if existing:
        return existing

    user_achievement = UserAchievement(user_id=user_id, achievement_id=achievement.id)
    db.add(user_achievement)
    db.flush()
    return user_achievement


def check_game_achievements(db: Session, game_id: int):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game or not game.winner:
        return []

    players = db.query(GamePlayer).filter(GamePlayer.game_id == game_id).all()
    players_by_id = {p.id: p for p in players}
    unlocked = []

    def unlock(user_id, code):
        result = unlock_achievement(db, user_id, code)
        if result:
            unlocked.append(result)

    for player in players:
        won = (game.winner == GameWinner.MAFIA) == (player.role == GameRole.mafia)

        if won:
            statistic = db.query(UserStatistic).filter(UserStatistic.user_id == player.user_id).first()
            if statistic and statistic.wins >= 1:
                unlock(player.user_id, AchievementCode.FIRST_WIN)

        if player.role == GameRole.mafia and game.winner == GameWinner.MAFIA:
            unlock(player.user_id, AchievementCode.MAFIA_MASTERMIND)

        if player.is_alive:
            unlock(player.user_id, AchievementCode.SURVIVOR)

        if player.role != GameRole.mafia and player.is_alive and game.winner == GameWinner.CITIZENS:
            unlock(player.user_id, AchievementCode.PERFECT_TOWN)

    round_ids = [r.id for r in db.query(GameRound).filter(GameRound.game_id == game_id).all()]
    if round_ids:
        check_actions = (db.query(NightAction)
                         .filter(NightAction.round_id.in_(round_ids), NightAction.action_type == NightActionType.CHECK)
                         .all())
        for action in check_actions:
            commissar = players_by_id.get(action.actor_id)
            target = players_by_id.get(action.target_id)
            if commissar and target and commissar.role == GameRole.commissar and target.role == GameRole.mafia:
                unlock(commissar.user_id, AchievementCode.SHERLOCK)

    return unlocked


@user_achievement_router.get('/list', response_model=List[UserAchievementListSchema])
def list_user_achievement(user_id: int, db: Session = Depends(get_db)):
    return db.query(UserAchievement).filter(UserAchievement.user_id == user_id).all()


@user_achievement_router.get('/detail', response_model=UserAchievementDetailSchema)
def detail_user_achievement(user_achievement_id: int, db: Session = Depends(get_db)):
    ua_db = db.query(UserAchievement).filter(UserAchievement.id == user_achievement_id).first()
    if not ua_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user achievement not found")
    return ua_db