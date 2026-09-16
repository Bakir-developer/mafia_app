import json
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from mysite.db.database import SessionLocal
from mysite.db.models import Game, GamePlayer

chat_router = APIRouter(prefix='/ws', tags=['Chat'])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ConnectionManager:
    def __init__(self):
        # room_id -> список активных соединений этой комнаты
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # websocket -> user_id, чтобы знать, кто прислал сообщение
        self.connection_users: Dict[WebSocket, int] = {}

    async def connect(self, websocket: WebSocket, room_id: int, user_id: int):
        await websocket.accept()
        self.active_connections.setdefault(room_id, []).append(websocket)
        self.connection_users[websocket] = user_id

    def disconnect(self, websocket: WebSocket, room_id: int):
        if room_id in self.active_connections and websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)
        self.connection_users.pop(websocket, None)

    async def broadcast(self, room_id: int, payload: dict):
        for connection in self.active_connections.get(room_id, []):
            await connection.send_json(payload)

    async def send_personal(self, websocket: WebSocket, payload: dict):
        await websocket.send_json(payload)


manager = ConnectionManager()


def is_player_muted(db: Session, room_id: int, user_id: int) -> bool:
    """
    True кайтарат эгер:
      - бул room'до активдүү Game бар
      - жана ошол Game'де бул user GamePlayer катары катталган
      - жана is_alive=False (өлгөн)
    Game жок болсо (лобби чаты) же оюнчу GamePlayer катары жок болсо — мутed эмес.
    """
    game = db.query(Game).filter(Game.room_id == room_id).first()
    if not game:
        return False

    game_player = db.query(GamePlayer).filter(
        GamePlayer.game_id == game.id,
        GamePlayer.user_id == user_id,
    ).first()

    if not game_player:
        return False

    return not game_player.is_alive


@chat_router.websocket('/chat/{room_id}')
async def chat_endpoint(
    websocket: WebSocket,
    room_id: int,
    user_id: int = Query(...),  # ⚠️ убрать, когда появится auth через токен — user_id должен приходить из сессии
    db: Session = Depends(get_db),
):
    await manager.connect(websocket, room_id, user_id)
    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
                message_text = data.get('message', '')
            except json.JSONDecodeError:
                message_text = raw

            if is_player_muted(db, room_id, user_id):
                await manager.send_personal(websocket, {
                    'type': 'error',
                    'detail': 'Сен өлгөнсүң, жалпы чатка жаза албайсың',
                })
                continue

            await manager.broadcast(room_id, {
                'type': 'message',
                'user_id': user_id,
                'message': message_text,
            })

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)