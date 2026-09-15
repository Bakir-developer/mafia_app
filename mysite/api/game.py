import random
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mysite.db.database import SessionLocal
from mysite.db.models import Game, GamePlayer, GameRound, Room, RoomPlayer, RoomStatus, GameRole
from mysite.db.schema import (
    GameCreateSchema,
    GameListSchema,
    GameDetailSchema,
    GamePlayerListSchema,
    GamePlayerDetailSchema,
    GameRoundListSchema,
    GameRoundDetailSchema,
)
from mysite.db.schema import GamePhase, GameWinner

game_router = APIRouter(prefix='/game', tags=['Game'])
game_player_router = APIRouter(prefix='/game-player', tags=['GamePlayer'])
game_round_router = APIRouter(prefix='/game-round', tags=['GameRound'])

MIN_PLAYERS = 4  # 1 mafia + doctor + commissar + жок дегенде 1 civilian


async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class GameUpdateSchema(BaseModel):
    current_round: Optional[int] = None
    current_phase: Optional[GamePhase] = None
    winner: Optional[GameWinner] = None


def build_role_deck(total_players: int) -> List[GameRole]:
    mafia_count = max(1, total_players // 4)  # ~25%
    deck = [GameRole.mafia] * mafia_count
    deck.append(GameRole.doctor)
    deck.append(GameRole.commissar)
    while len(deck) < total_players:
        deck.append(GameRole.civilian)
    return deck


@game_router.post('/create', response_model=GameDetailSchema)
async def create_game(game_data: GameCreateSchema, db: Session = Depends(get_db)):
    room_db = db.query(Room).filter(Room.id == game_data.room_id).first()
    if not room_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room not found")

    existing_game = db.query(Game).filter(Game.room_id == game_data.room_id).first()
    if existing_game:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="game already exists for this room")

    room_players = db.query(RoomPlayer).filter(RoomPlayer.room_id == game_data.room_id).all()
    if len(room_players) < MIN_PLAYERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"need at least {MIN_PLAYERS} players to start a game",
        )

    # Ролдорду random бөлүү
    deck = build_role_deck(len(room_players))
    random.shuffle(deck)
    random.shuffle(room_players)

    game_db = Game(room_id=game_data.room_id, current_round=0, current_phase=GamePhase.NIGHT)
    db.add(game_db)
    db.flush()  # game_db.id алуу үчүн, commit'ке чейин

    for room_player, role in zip(room_players, deck):
        db.add(GamePlayer(game_id=game_db.id, user_id=room_player.user_id, role=role, is_alive=True))

    room_db.status = RoomStatus.IN_PROGRESS

    db.commit()
    db.refresh(game_db)
    return game_db


@game_router.get('/list', response_model=List[GameListSchema])
async def list_game(db: Session = Depends(get_db)):
    return db.query(Game).all()


@game_router.get('/detail', response_model=GameDetailSchema)
async def detail_game(game_id: int, db: Session = Depends(get_db)):
    game_db = db.query(Game).filter(Game.id == game_id).first()
    if not game_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game not found")
    return game_db


@game_router.put('/update/{game_id}', response_model=GameDetailSchema)
async def update_game(game_id: int, game_data: GameUpdateSchema, db: Session = Depends(get_db)):
    game_db = db.query(Game).filter(Game.id == game_id).first()
    if not game_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game not found")

    for key, value in game_data.dict(exclude_unset=True).items():
        setattr(game_db, key, value)

    # Жеңүүчү аныкталса, комнатаны да FINISHED кылабыз
    if game_data.winner is not None:
        game_db.room.status = RoomStatus.FINISHED

    db.commit()
    db.refresh(game_db)
    return game_db


@game_router.delete('/delete/{game_id}', response_model=dict)
async def delete_game(game_id: int, db: Session = Depends(get_db)):
    game_db = db.query(Game).filter(Game.id == game_id).first()
    if not game_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game not found")
    db.delete(game_db)
    db.commit()
    return {'status': 'success deleted'}


# ============================================================================
# GAME PLAYER
# (create/update/delete жок — ролдор create_game учурунда автоматтык бөлүнөт,
#  is_alive/eliminated_* талааларын night/voting логикасы гана өзгөртөт)
# ============================================================================

@game_player_router.get('/list', response_model=List[GamePlayerListSchema])
async def list_game_player(game_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(GamePlayer)
    if game_id is not None:
        query = query.filter(GamePlayer.game_id == game_id)
    return query.all()


@game_player_router.get('/detail', response_model=GamePlayerDetailSchema)
async def detail_game_player(game_player_id: int, db: Session = Depends(get_db)):
    game_player_db = db.query(GamePlayer).filter(GamePlayer.id == game_player_id).first()
    if not game_player_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game player not found")
    return game_player_db



@game_round_router.get('/list', response_model=List[GameRoundListSchema])
async def list_game_round(game_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(GameRound)
    if game_id is not None:
        query = query.filter(GameRound.game_id == game_id)
    return query.all()


@game_round_router.get('/detail', response_model=GameRoundDetailSchema)
async def detail_game_round(round_id: int, db: Session = Depends(get_db)):
    round_db = db.query(GameRound).filter(GameRound.id == round_id).first()
    if not round_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game round not found")
    return round_db