import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session
from mysite.api.dependencies import get_current_user, get_admin_user, is_admin
from mysite.api.night_action import check_game_achievements, unlock_achievement
from mysite.api.websocket import manager
from mysite.db.database import SessionLocal
from mysite.db.models import (Game, GamePlayer, GameRound, NightAction, Room, Vote, RoomPlayer, RoomStatus,
                              GameRole, GamePhase, GameWinner, NightActionType, EliminationReason,
                              UserStatistic, UserProfile, AchievementCode)
from mysite.db.schema import (GameCreateSchema, GameListSchema, GameDetailSchema, GamePlayerListSchema,
                              GamePlayerDetailSchema, GameRoundListSchema, GameRoundDetailSchema)
from mysite.game_logic import (decide_winner, pick_kill_target, tally_votes, validate_role_counts,
                               role_stat_field)

logger = logging.getLogger(__name__)

game_router = APIRouter(prefix="/game", tags=["Game"])
game_player_router = APIRouter(prefix="/game-player", tags=["GamePlayer"])
game_round_router = APIRouter(prefix="/game-round", tags=["GameRound"])

MIN_PLAYERS = 4
VOTING_TIME = 30
WIN_REWARD_COINS = 10
PROTECTION_PRICE = 100
Event = Tuple[Optional[int], Dict[str, Any]]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class GameUpdateSchema(BaseModel):
    current_round: Optional[int] = None
    winner: Optional[GameWinner] = None


def _now() -> datetime:
    return datetime.utcnow()


def _bad_request(detail: str):
    raise HTTPException(status_code=400, detail=detail)

def build_role_deck(total_players: int, mafia_count: int, doctor_count: int, commissar_count: int) -> List[GameRole]:
    error = validate_role_counts(total_players, mafia_count, doctor_count, commissar_count)
    if error:
        _bad_request(error)

    deck = [GameRole.mafia] * mafia_count
    deck += [GameRole.doctor] * doctor_count
    deck += [GameRole.commissar] * commissar_count
    deck += [GameRole.civilian] * (total_players - len(deck))
    random.shuffle(deck)
    return deck

def _lock_game(db: Session, game_id: int) -> Optional[Game]:
    return db.query(Game).filter(Game.id == game_id).populate_existing().with_for_update().first()


def _get_statistic(db: Session, user_id: int) -> UserStatistic:
    statistic = db.query(UserStatistic).filter(UserStatistic.user_id == user_id).first()
    if not statistic:
        statistic = UserStatistic(
            user_id=user_id, games_played=0, wins=0, losses=0, total_game_time=0,
            mafia_games=0, citizen_games=0, detective_games=0, doctor_games=0, coins=0, protections=0,
        )
        db.add(statistic)
        db.flush()
    return statistic


def _player_won(winner: GameWinner, role: GameRole) -> bool:
    return (winner == GameWinner.MAFIA) == (role == GameRole.mafia)


def check_winner(db: Session, game: Game) -> Optional[GameWinner]:
    alive_roles = [role for (role,) in db.query(GamePlayer.role)
                   .filter(GamePlayer.game_id == game.id, GamePlayer.is_alive == True).all()]  # noqa: E712
    mafia = sum(1 for role in alive_roles if role == GameRole.mafia)
    result = decide_winner(mafia, len(alive_roles) - mafia)
    return GameWinner(result) if result else None


def _apply_game_results(db: Session, game: Game, now: datetime):
    duration = max((now - game.started_at).total_seconds(), 0.0) if game.started_at else 0.0

    for player in db.query(GamePlayer).filter(GamePlayer.game_id == game.id).all():
        statistic = _get_statistic(db, player.user_id)
        statistic.games_played += 1
        statistic.total_game_time += duration

        field = role_stat_field(player.role.value)
        setattr(statistic, field, getattr(statistic, field) + 1)

        if _player_won(game.winner, player.role):
            statistic.wins += 1
            statistic.coins += WIN_REWARD_COINS
        else:
            statistic.losses += 1
    db.flush()


def finish_game(db: Session, game: Game, winner: GameWinner) -> Event:
    if game.winner is not None:
        raise HTTPException(status_code=400, detail="game already finished")

    now = _now()
    game.winner = winner
    game.current_phase = GamePhase.DAY
    game.phase_ends_at = None
    game.finished_at = now
    game.room.status = RoomStatus.FINISHED
    game.room.finished_at = now
    db.flush()

    _apply_game_results(db, game, now)
    check_game_achievements(db, game.id)

    return None, {
        "type": "game_finished",
        "winner": winner.value,
        "phase": GamePhase.DAY.value,
        "phase_ends_at": None,
    }


def _ensure_round(db: Session, game: Game) -> GameRound:
    round_db = (db.query(GameRound)
                .filter(GameRound.game_id == game.id, GameRound.round_number == game.current_round).first())
    if not round_db:
        round_db = GameRound(game_id=game.id, round_number=game.current_round)
        db.add(round_db)
        db.flush()
    return round_db


def _start_next_night(db: Session, game: Game) -> str:
    game.current_round += 1
    game.current_phase = GamePhase.NIGHT
    ends_at = _now() + timedelta(seconds=game.room.night_time)
    game.phase_ends_at = ends_at
    _ensure_round(db, game)
    return ends_at.isoformat()


def _phase_event(phase: GamePhase, ends_at_iso: Optional[str]) -> Event:
    return None, {"type": "phase_changed", "phase": phase.value, "phase_ends_at": ends_at_iso}

def process_night_sync(db: Session, game_id: int) -> Tuple[List[Event], Optional[dict]]:
    game = _lock_game(db, game_id)
    if not game or game.winner is not None or game.current_phase != GamePhase.NIGHT:
        db.rollback()
        return [], None

    round_db = _ensure_round(db, game)
    players = {p.id: p for p in db.query(GamePlayer).filter(GamePlayer.game_id == game.id).all()}
    actions = db.query(NightAction).filter(NightAction.round_id == round_db.id).all()

    def actor(action):
        player = players.get(action.actor_id)
        return player if player and player.is_alive else None

    kill_targets = [
        a.target_id for a in actions
        if a.action_type == NightActionType.KILL
        and (actor(a) is not None and actor(a).role == GameRole.mafia)
        and players.get(a.target_id) is not None and players[a.target_id].is_alive
    ]
    heals = [
        a for a in actions
        if a.action_type == NightActionType.HEAL and actor(a) is not None and actor(a).role == GameRole.doctor
    ]

    personal: List[Event] = []
    public: List[Event] = []
    killed_player_id = None

    target_id = pick_kill_target(kill_targets)
    if target_id is not None:
        target = players[target_id]
        healers = [a for a in heals if a.target_id == target_id]

        if healers:
            round_db.saved_by_doctor = True
            personal.append((target.user_id, {"type": "doctor_saved", "message": "Доктор спас вас этой ночью"}))
            for heal in healers:
                doctor = players[heal.actor_id]
                personal.append((doctor.user_id, {"type": "doctor_heal_success",
                                                  "message": "Вы спасли игрока этой ночью"}))
                unlock_achievement(db, doctor.user_id, AchievementCode.GUARDIAN_ANGEL)
        else:
            statistic = db.query(UserStatistic).filter(UserStatistic.user_id == target.user_id).first()
            if statistic and statistic.protections > 0:
                statistic.protections -= 1
                personal.append((target.user_id, {
                    "type": "protection_used",
                    "message": "Вас спасла накопленная защита.",
                    "protections_left": statistic.protections,
                }))
            else:
                target.is_alive = False
                target.eliminated_round = round_db.round_number
                target.eliminated_reason = EliminationReason.NIGHT_KILL
                round_db.killed_player_id = target.id
                killed_player_id = target.id
                username = target.user.username
                public.append((None, {
                    "type": "player_killed",
                    "user_id": target.user_id,
                    "username": username,
                    "reason": "NIGHT_KILL",
                    "message": f"{username} был убит этой ночью",
                }))

    db.flush()
    round_id = round_db.id
    winner = check_winner(db, game)

    events: List[Event] = []
    if winner:
        finish_event = finish_game(db, game, winner)
        events = public + personal + [finish_event]
        phase, ends_at = GamePhase.DAY, None
    else:
        ends_at_dt = _now() + timedelta(seconds=game.room.day_time)
        game.current_phase = GamePhase.DAY
        game.phase_ends_at = ends_at_dt
        ends_at = ends_at_dt.isoformat()
        phase = GamePhase.DAY
        events = [_phase_event(phase, ends_at)] + public + personal

    result = {
        "message": "Night ended",
        "game_id": game.id,
        "round_id": round_id,
        "phase": phase.value,
        "phase_ends_at": ends_at,
        "killed_player_id": killed_player_id,
        "winner": winner.value if winner else None,
    }
    db.commit()
    return events, result

def process_start_voting_sync(db: Session, game_id: int) -> Tuple[List[Event], Optional[dict]]:
    game = _lock_game(db, game_id)
    if not game or game.winner is not None or game.current_phase != GamePhase.DAY:
        db.rollback()
        return [], None

    ends_at_dt = _now() + timedelta(seconds=VOTING_TIME)
    game.current_phase = GamePhase.VOTING
    game.phase_ends_at = ends_at_dt
    result = {
        "message": "Voting started",
        "game_id": game.id,
        "round_id": game.current_round,
        "phase": GamePhase.VOTING.value,
        "phase_ends_at": ends_at_dt.isoformat(),
    }
    db.commit()
    return [_phase_event(GamePhase.VOTING, result["phase_ends_at"])], result

def process_voting_sync(db: Session, game_id: int) -> Tuple[List[Event], Optional[dict]]:
    game = _lock_game(db, game_id)
    if not game or game.winner is not None or game.current_phase != GamePhase.VOTING:
        db.rollback()
        return [], None

    round_db = (db.query(GameRound).filter(GameRound.game_id == game.id, GameRound.round_number == game.current_round).first())
    if not round_db:
        db.rollback()
        return [], None

    votes = db.query(Vote).filter(Vote.round_id == round_db.id).all()
    votes_data = [{"voter_id": v.voter_id, "target_id": v.target_id} for v in votes]
    _counts, leaders = tally_votes((v.voter_id, v.target_id) for v in votes)

    if len(leaders) != 1:
        tie = len(leaders) > 1
        message = "Ничья по голосам. Никто не выходит." if tie else "Голосов нет. Никто не выходит."
        ends_at = _start_next_night(db, game)

        vote_event: Dict[str, Any] = {"type": "voting_result", "message": message, "tie": tie,
                                      "eliminated_player_id": None, "votes": votes_data}
        result = {"message": message if tie else "Voting ended without votes", "game_id": game.id,
                  "eliminated_player_id": None, "winner": None, "tie": tie, "votes": votes_data,
                  "next_round": game.current_round, "phase": GamePhase.NIGHT.value, "phase_ends_at": ends_at}
        if tie:
            vote_event["players"] = leaders
            result["players"] = leaders
        db.commit()
        return [(None, vote_event), _phase_event(GamePhase.NIGHT, ends_at)], result

    eliminated = (db.query(GamePlayer).filter(GamePlayer.id == leaders[0], GamePlayer.game_id == game.id).first())
    if not eliminated:
        db.rollback()
        return [], None

    eliminated.is_alive = False
    eliminated.eliminated_round = round_db.round_number
    eliminated.eliminated_reason = EliminationReason.VOTE
    round_db.eliminated_player_id = eliminated.id
    eliminated_id, eliminated_user_id, username = eliminated.id, eliminated.user_id, eliminated.user.username
    db.flush()

    events: List[Event] = [
        (None, {"type": "voting_result", "message": "Игрок исключён голосованием.", "tie": False,
                "eliminated_player_id": eliminated_id, "votes": votes_data}),
        (None, {"type": "player_killed", "user_id": eliminated_user_id, "username": username, "reason": "VOTE"}),
    ]

    winner = check_winner(db, game)
    result = {"game_id": game.id, "eliminated_player_id": eliminated_id, "votes": votes_data, "tie": False}

    if winner:
        events.append(finish_game(db, game, winner))
        result.update({"message": "Mafia wins" if winner == GameWinner.MAFIA else "Citizens win",
                       "winner": winner.value, "phase": GamePhase.DAY.value, "phase_ends_at": None})
    else:
        ends_at = _start_next_night(db, game)
        events.append(_phase_event(GamePhase.NIGHT, ends_at))
        result.update({"message": "Voting ended", "winner": None, "next_round": game.current_round,
                       "phase": GamePhase.NIGHT.value, "phase_ends_at": ends_at})

    db.commit()
    return events, result

async def dispatch_events(game_id: int, events: List[Event]):
    for user_id, data in events:
        if user_id is None:
            await manager.broadcast(game_id, data)
        else:
            await manager.send_to_user(game_id, user_id, data)


def night_actions_completed(db: Session, game: Game) -> bool:
    if game.current_phase != GamePhase.NIGHT:
        return False

    round_db = (db.query(GameRound).filter(GameRound.game_id == game.id, GameRound.round_number == game.current_round).first())
    if not round_db:
        return False

    alive = {p.id: p for p in db.query(GamePlayer)
             .filter(GamePlayer.game_id == game.id, GamePlayer.is_alive == True).all()}  # noqa: E712
    actions = db.query(NightAction).filter(NightAction.round_id == round_db.id).all()

    def acted(action_type: NightActionType, role: GameRole) -> bool:
        return any(a.action_type == action_type and a.actor_id in alive and alive[a.actor_id].role == role
                   for a in actions)

    for action_type, role in ((NightActionType.KILL, GameRole.mafia),
                              (NightActionType.HEAL, GameRole.doctor),
                              (NightActionType.CHECK, GameRole.commissar)):
        if any(p.role == role for p in alive.values()) and not acted(action_type, role):
            return False
    return True

def _scheduler_tick() -> List[Tuple[int, List[Event]]]:
    db = SessionLocal()
    batches: List[Tuple[int, List[Event]]] = []
    try:
        now = _now()
        due = (db.query(Game.id, Game.current_phase, Game.phase_ends_at)
               .filter(Game.winner.is_(None), Game.phase_ends_at.isnot(None)).all())

        for game_id, phase, ends_at in due:
            try:
                events: List[Event] = []
                if phase == GamePhase.NIGHT:
                    game = db.get(Game, game_id)
                    if now >= ends_at or night_actions_completed(db, game):
                        events, _ = process_night_sync(db, game_id)
                elif phase == GamePhase.DAY and now >= ends_at:
                    events, _ = process_start_voting_sync(db, game_id)
                elif phase == GamePhase.VOTING and now >= ends_at:
                    events, _ = process_voting_sync(db, game_id)

                if events:
                    batches.append((game_id, events))
            except Exception:
                db.rollback()
                logger.exception("Game scheduler error (game_id=%s)", game_id)
    finally:
        db.close()
    return batches


async def game_scheduler():
    while True:
        try:
            for game_id, events in await run_in_threadpool(_scheduler_tick):
                await dispatch_events(game_id, events)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Game scheduler crashed, retrying")
        await asyncio.sleep(1)

def _load_game_for_manager(db: Session, game_id: int, user: UserProfile) -> Game:
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="game not found")
    if game.room.owner_id != user.id and not is_admin(user):
        raise HTTPException(status_code=403, detail="only the room owner can manage game phases")
    return game

@game_router.post("/create", response_model=GameDetailSchema)
def create_game(game_data: GameCreateSchema, db: Session = Depends(get_db),
                current_user: UserProfile = Depends(get_current_user)):
    room_db = db.query(Room).filter(Room.id == game_data.room_id).with_for_update().first()
    if not room_db:
        raise HTTPException(status_code=404, detail="room not found")

    if room_db.owner_id != current_user.id and not is_admin(current_user):
        raise HTTPException(status_code=403, detail="only the room owner can start the game")

    if db.query(Game).filter(Game.room_id == game_data.room_id).first():
        _bad_request("game already exists for this room")

    if room_db.status != RoomStatus.WAITING:
        _bad_request("room is not waiting for players")

    room_players = db.query(RoomPlayer).filter(RoomPlayer.room_id == game_data.room_id).all()
    total_players = len(room_players)

    if total_players < MIN_PLAYERS:
        _bad_request(f"need at least {MIN_PLAYERS} players to start a game")

    deck = build_role_deck(total_players, room_db.mafia_count, room_db.doctor_count, room_db.commissar_count)
    random.shuffle(room_players)

    now = _now()
    game_db = Game(
        room_id=room_db.id,
        current_round=1,
        current_phase=GamePhase.NIGHT,
        started_at=now,
        phase_ends_at=now + timedelta(seconds=room_db.night_time),
    )
    db.add(game_db)
    db.flush()

    for room_player, role in zip(room_players, deck):
        db.add(GamePlayer(game_id=game_db.id, user_id=room_player.user_id, role=role, is_alive=True))

    db.add(GameRound(game_id=game_db.id, round_number=1))
    room_db.status = RoomStatus.IN_PROGRESS
    room_db.started_at = now
    db.commit()
    db.refresh(game_db)
    return game_db


@game_router.post("/exchange-protection")
def exchange_protection(db: Session = Depends(get_db), current_user: UserProfile = Depends(get_current_user)):
    statistic = (db.query(UserStatistic).filter(UserStatistic.user_id == current_user.id)
                 .with_for_update().first())
    if not statistic:
        raise HTTPException(status_code=404, detail="statistics not found")

    if statistic.coins < PROTECTION_PRICE:
        _bad_request(f"Need {PROTECTION_PRICE} coins to get 1 protection")

    statistic.coins -= PROTECTION_PRICE
    statistic.protections += 1
    db.commit()
    db.refresh(statistic)

    return {
        "message": f"{PROTECTION_PRICE} coins exchanged for 1 protection",
        "coins": statistic.coins,
        "protections": statistic.protections,
    }

@game_router.post("/end-night/{game_id}")
async def end_night(game_id: int, db: Session = Depends(get_db),
                    current_user: UserProfile = Depends(get_current_user)):
    await run_in_threadpool(_load_game_for_manager, db, game_id, current_user)
    events, result = await run_in_threadpool(process_night_sync, db, game_id)
    if result is None:
        _bad_request("game is not in NIGHT phase")
    await dispatch_events(game_id, events)
    return result

@game_router.post("/start-voting/{game_id}")
async def start_voting(game_id: int, db: Session = Depends(get_db),
                       current_user: UserProfile = Depends(get_current_user)):
    await run_in_threadpool(_load_game_for_manager, db, game_id, current_user)
    events, result = await run_in_threadpool(process_start_voting_sync, db, game_id)
    if result is None:
        _bad_request("game is not in DAY phase")
    await dispatch_events(game_id, events)
    return result

@game_router.post("/end-voting/{game_id}")
async def end_voting(game_id: int, db: Session = Depends(get_db),
                     current_user: UserProfile = Depends(get_current_user)):
    await run_in_threadpool(_load_game_for_manager, db, game_id, current_user)
    events, result = await run_in_threadpool(process_voting_sync, db, game_id)
    if result is None:
        _bad_request("game is not in VOTING phase")
    await dispatch_events(game_id, events)
    return result

@game_router.get("/list", response_model=List[GameListSchema])
def list_game(db: Session = Depends(get_db)):
    return db.query(Game).all()

@game_router.get("/detail", response_model=GameDetailSchema)
def detail_game(game_id: int, db: Session = Depends(get_db)):
    game_db = db.query(Game).filter(Game.id == game_id).first()
    if not game_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game not found")
    return game_db

@game_router.put("/update/{game_id}", response_model=GameDetailSchema)
async def update_game(game_id: int, game_data: GameUpdateSchema, db: Session = Depends(get_db),
                      admin: UserProfile = Depends(get_admin_user)):
    def work():
        game_db = _lock_game(db, game_id)
        if not game_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game not found")

        if game_data.current_round is not None:
            if game_data.current_round < 1:
                _bad_request("current_round must be >= 1")
            game_db.current_round = game_data.current_round

        event = finish_game(db, game_db, game_data.winner) if game_data.winner is not None else None
        db.commit()
        db.refresh(game_db)
        return game_db, event

    game_db, event = await run_in_threadpool(work)
    if event:
        await dispatch_events(game_id, [event])
    return game_db

@game_router.delete("/delete/{game_id}", response_model=dict)
def delete_game(game_id: int, db: Session = Depends(get_db), admin: UserProfile = Depends(get_admin_user)):
    game_db = db.query(Game).filter(Game.id == game_id).first()
    if not game_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game not found")
    db.delete(game_db)
    db.commit()
    return {"status": "success deleted"}

def _visible_role(viewer: GamePlayer, target: GamePlayer, game: Game) -> Optional[GameRole]:
    if game.winner is not None:
        return target.role
    if viewer.id == target.id:
        return target.role
    if not target.is_alive:
        return target.role
    if viewer.role in {GameRole.mafia, GameRole.doctor, GameRole.commissar} and viewer.role == target.role:
        return target.role
    return None


@game_player_router.get("/list", response_model=List[GamePlayerListSchema])
def list_game_player(game_id: Optional[int] = None, db: Session = Depends(get_db),
                     current_user: UserProfile = Depends(get_current_user)):
    query = db.query(GamePlayer)
    if game_id is not None:
        query = query.filter(GamePlayer.game_id == game_id)

    games: Dict[int, Game] = {}
    viewers: Dict[int, Optional[GamePlayer]] = {}
    result = []
    for p in query.all():
        if p.game_id not in games:
            games[p.game_id] = db.get(Game, p.game_id)
            viewers[p.game_id] = (db.query(GamePlayer)
                                  .filter(GamePlayer.game_id == p.game_id, GamePlayer.user_id == current_user.id)
                                  .first())
        game, viewer = games[p.game_id], viewers[p.game_id]
        visible_role = _visible_role(viewer, p, game) if viewer else (p.role if game.winner else None)
        result.append(GamePlayerListSchema(id=p.id, user_id=p.user_id, role=visible_role, is_alive=p.is_alive))
    return result

@game_player_router.get("/detail", response_model=GamePlayerDetailSchema)
def detail_game_player(game_player_id: int, db: Session = Depends(get_db),
                       current_user: UserProfile = Depends(get_current_user)):
    target = db.query(GamePlayer).filter(GamePlayer.id == game_player_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game player not found")

    game = db.query(Game).filter(Game.id == target.game_id).first()
    viewer = (db.query(GamePlayer)
              .filter(GamePlayer.game_id == target.game_id, GamePlayer.user_id == current_user.id).first())
    if not viewer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="you are not in this game")

    return GamePlayerDetailSchema(
        id=target.id,
        game_id=target.game_id,
        user_id=target.user_id,
        role=_visible_role(viewer, target, game),
        is_alive=target.is_alive,
        eliminated_round=target.eliminated_round,
        eliminated_reason=target.eliminated_reason,
    )

@game_round_router.get("/list", response_model=List[GameRoundListSchema])
def list_game_round(game_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(GameRound)
    if game_id is not None:
        query = query.filter(GameRound.game_id == game_id)
    return query.all()

@game_round_router.get("/detail", response_model=GameRoundDetailSchema)
def detail_game_round(round_id: int, db: Session = Depends(get_db)):
    round_db = db.query(GameRound).filter(GameRound.id == round_id).first()
    if not round_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game round not found")
    return round_db