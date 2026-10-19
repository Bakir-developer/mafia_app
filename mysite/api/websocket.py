import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from jose import jwt, JWTError
from mysite.config import SECRET_KEY, ALGORITHM
from mysite.db.database import SessionLocal
from mysite.db.models import UserProfile, Game, GamePlayer, GamePhase, GameRole

logger = logging.getLogger(__name__)

chat_router = APIRouter(prefix="/ws", tags=["Chat"])

ALLOWED_CHANNELS = {"all", "mafia", "dead"}
AUTH_TIMEOUT_SECONDS = 10

PlayersState = Dict[int, Tuple[GameRole, bool]]


class ConnectionManager:

    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.connection_users: Dict[WebSocket, int] = {}
        self.connection_games: Dict[WebSocket, int] = {}

    async def connect(self, websocket: WebSocket, game_id: int, user_id: int):
        self.active_connections.setdefault(game_id, []).append(websocket)
        self.connection_users[websocket] = user_id
        self.connection_games[websocket] = game_id

    def disconnect(self, websocket: WebSocket, game_id: int):
        connections = self.active_connections.get(game_id)
        if connections is not None:
            if websocket in connections:
                connections.remove(websocket)
            if not connections:
                del self.active_connections[game_id]

        self.connection_users.pop(websocket, None)
        self.connection_games.pop(websocket, None)

    async def _send_to(self, game_id: int, websockets: List[WebSocket], data: dict):
        disconnected = []
        for websocket in websockets:
            try:
                await websocket.send_json(data)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket, game_id)

    async def broadcast(self, game_id: int, data: dict):
        await self._send_to(game_id, list(self.active_connections.get(game_id, [])), data)

    async def send_to_user(self, game_id: int, user_id: int, data: dict):
        targets = [
            ws for ws in self.active_connections.get(game_id, [])
            if self.connection_users.get(ws) == user_id
        ]
        await self._send_to(game_id, targets, data)

    async def send_personal(self, websocket: WebSocket, data: dict):
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    async def broadcast_channel(self, game_id: int, channel: str, data: dict, players: PlayersState):
        targets = []
        for websocket in list(self.active_connections.get(game_id, [])):
            state = players.get(self.connection_users.get(websocket))
            if state is None:
                continue
            role, is_alive = state

            if channel == "mafia" and not (role == GameRole.mafia and is_alive):
                continue
            if channel == "dead" and is_alive:
                continue
            targets.append(websocket)

        await self._send_to(game_id, targets, data)

    async def broadcast_last_words(self, game_id: int, data: dict, players: PlayersState):
        targets = []
        for websocket in list(self.active_connections.get(game_id, [])):
            state = players.get(self.connection_users.get(websocket))
            if state is not None and state[1]:
                targets.append(websocket)
        await self._send_to(game_id, targets, data)


manager = ConnectionManager()

def decode_websocket_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


def _authenticate(token: str, game_id: int):
    payload = decode_websocket_token(token)
    if not payload:
        return "Invalid token or user not found", None, None

    db = SessionLocal()
    try:
        user = db.query(UserProfile).filter(UserProfile.id == payload.get("user_id")).first()
        if not user:
            return "Invalid token or user not found", None, None
        if not db.query(Game).filter(Game.id == game_id).first():
            return "Game not found", None, None
        if not db.query(GamePlayer).filter(GamePlayer.game_id == game_id, GamePlayer.user_id == user.id).first():
            return "You are not a player in this game", None, None
        return None, user.id, user.username
    finally:
        db.close()


def _load_state(game_id: int, user_id: int) -> Optional[dict]:
    db = SessionLocal()
    try:
        game = db.query(Game).filter(Game.id == game_id).first()
        player = db.query(GamePlayer).filter(GamePlayer.game_id == game_id, GamePlayer.user_id == user_id).first()
        if not game or not player:
            return None
        return {
            "winner": game.winner,
            "phase": game.current_phase,
            "role": player.role,
            "alive": player.is_alive,
            "last_words_sent": player.has_sent_last_words,
        }
    finally:
        db.close()


def _load_players(game_id: int) -> PlayersState:
    db = SessionLocal()
    try:
        players = db.query(GamePlayer).filter(GamePlayer.game_id == game_id).all()
        return {p.user_id: (p.role, p.is_alive) for p in players}
    finally:
        db.close()


def _save_last_words(game_id: int, user_id: int, text: str) -> Optional[str]:
    db = SessionLocal()
    try:
        player = (db.query(GamePlayer)
                  .filter(GamePlayer.game_id == game_id, GamePlayer.user_id == user_id)
                  .with_for_update().first())
        if not player:
            return "Game or player not found"
        if player.is_alive:
            return "Only eliminated players can send last words"
        if player.has_sent_last_words:
            return "Last words have already been sent"
        player.last_words = text
        player.has_sent_last_words = True
        db.commit()
        return None
    finally:
        db.close()

def can_send_message(state: dict, channel: str) -> bool:
    role, alive, phase = state["role"], state["alive"], state["phase"]

    if channel == "dead":
        return not alive

    if channel == "mafia":
        return state["winner"] is None and alive and role == GameRole.mafia and phase == GamePhase.NIGHT

    if channel == "all":
        if state["winner"] is not None:
            return alive
        return alive and phase == GamePhase.DAY

    return False

def _denied_reason(state: dict, channel: str) -> str:
    if channel == "dead":
        return "Только мёртвые игроки могут писать в этот чат"
    if channel == "mafia":
        if state["role"] != GameRole.mafia or not state["alive"]:
            return "Чат мафии доступен только живой мафии"
        return "Чат мафии доступен только ночью"
    if state["phase"] == GamePhase.NIGHT:
        return "Ночью общий чат закрыт для всех игроков"
    if state["phase"] == GamePhase.VOTING:
        return "Во время голосования чат закрыт"
    return "Общий чат доступен только живым игрокам днём"


async def _error(websocket: WebSocket, detail: str):
    await manager.send_personal(websocket, {"type": "error", "detail": detail})


async def _receive_token(websocket: WebSocket, token: Optional[str]) -> Optional[str]:
    if token:
        return token
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
        data = json.loads(raw)
    except Exception:
        return None
    if isinstance(data, dict) and data.get("type") == "auth" and isinstance(data.get("token"), str):
        return data["token"]
    return None

@chat_router.websocket("/game/{game_id}")
async def chat_endpoint(websocket: WebSocket, game_id: int, token: Optional[str] = None):
    await websocket.accept()

    connected = False
    user_id = None
    username = None

    try:
        token = await _receive_token(websocket, token)
        if not token:
            await _error(websocket, "Invalid token or user not found")
            await websocket.close(code=1008)
            return

        error, user_id, username = await run_in_threadpool(_authenticate, token, game_id)
        if error:
            await _error(websocket, error)
            await websocket.close(code=1008)
            return

        await manager.connect(websocket, game_id, user_id)
        connected = True

        await manager.broadcast(game_id, {"type": "user_joined", "user_id": user_id, "username": username})

        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _error(websocket, "Message must be valid JSON")
                continue

            if not isinstance(data, dict):
                await _error(websocket, "Invalid message format")
                continue

            message_type = data.get("type")

            if message_type == "last_words":
                text = data.get("text", "")
                if not isinstance(text, str):
                    await _error(websocket, "Text must be string")
                    continue
                text = text.strip()
                if not text:
                    await _error(websocket, "Last words cannot be empty")
                    continue
                if len(text) > 500:
                    await _error(websocket, "Last words cannot exceed 500 characters")
                    continue

                error = await run_in_threadpool(_save_last_words, game_id, user_id, text)
                if error:
                    await _error(websocket, error)
                    continue

                players = await run_in_threadpool(_load_players, game_id)
                await manager.broadcast_last_words(
                    game_id,
                    {
                        "type": "last_words",
                        "user_id": user_id,
                        "username": username,
                        "text": text,
                        "time": datetime.utcnow().isoformat(),
                    },
                    players,
                )
                continue

            if message_type == "auth":
                continue

            if message_type != "chat":
                await _error(websocket, "Only chat and last_words messages are supported")
                continue

            channel = data.get("channel")
            if channel not in ALLOWED_CHANNELS:
                await _error(websocket, "Invalid channel")
                continue

            text = data.get("text", "")
            if not isinstance(text, str):
                await _error(websocket, "Text must be string")
                continue
            text = text.strip()
            if not text:
                await _error(websocket, "Message is empty")
                continue
            if len(text) > 1000:
                await _error(websocket, "Message is too long")
                continue

            state = await run_in_threadpool(_load_state, game_id, user_id)
            if state is None:
                await _error(websocket, "Game or player not found")
                continue

            if not can_send_message(state, channel):
                await _error(websocket, _denied_reason(state, channel))
                continue

            players = await run_in_threadpool(_load_players, game_id)
            await manager.broadcast_channel(
                game_id,
                channel,
                {
                    "type": "chat",
                    "channel": channel,
                    "from": username,
                    "user_id": user_id,
                    "text": text,
                    "time": datetime.utcnow().isoformat(),
                },
                players,
            )

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error (game_id=%s)", game_id)
    finally:
        if connected:
            manager.disconnect(websocket, game_id)
            await manager.broadcast(game_id, {"type": "user_left", "user_id": user_id, "username": username})