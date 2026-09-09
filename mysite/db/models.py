from typing import Optional, List
from datetime import datetime
from enum import Enum as PyEnum

from mako.ext.autohandler import autohandler
from sqlalchemy import String, SmallInteger, ForeignKey, Enum, DateTime, func, Text, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mysite.db.database import Base

class UserRole(str, PyEnum):
    player = 'player'
    admin = 'admin'

class UserProfile(Base):
    tablename = 'user_profile'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(50), unique=True)
    age: Mapped[int] = mapped_column(SmallInteger, default=0)
    profile_image: Mapped[Optional[str]] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.player)
    password: Mapped[str] = mapped_column(String)

    profile: Mapped[List['UserStatistic']] = relationship('UserStatistic',
                                                        back_populates='user', cascade='all, delete-orphan')
    room_owner: Mapped[list['Room']] = relationship(back_populates='user_profile', cascade='all, delete-orphan')
    room_memberships:  Mapped[list['RoomPlayer']] = relationship(back_populates='user_profile', cascade='all, delete-orphan')
    reviews: Mapped[list['Review']] =  relationship(back_populates='user_profile', cascade='all, delete-orphan')

class UserStatistic(Base):
    tablename = 'user_statistics'

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user_profile.id'), unique=True)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    total_game_time: Mapped[float] = mapped_column(Float, default=0)
    mafia_games: Mapped[int] = mapped_column(Integer, default=0)
    citizen_games: Mapped[int] = mapped_column(Integer, default=0)
    detective_games: Mapped[int]= mapped_column(Integer, default=0)
    doctor_games: Mapped[int] =mapped_column(Integer, default=0)

    user: Mapped['UserProfile'] = relationship('UserProfile', back_populates='profile')

class RoomStatus(str, PyEnum):
    WAITING = "WAITING"
    STARTING = "STARTING"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"


class Room(Base):
    __tablename__ = 'room'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    room_name: Mapped[str] = mapped_column(String(100))
    max_players: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[RoomStatus] = mapped_column(Enum(RoomStatus), default=RoomStatus.WAITING)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    owner_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id"))

    owner: Mapped["UserProfile"] = relationship(back_populates="room_owner")
    players: Mapped[List["RoomPlayer"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    reviews: Mapped[list['Room']] = relationship(back_populates='room', cascade='all, delete-orphan')

class RoomPlayer(Base):
    __tablename__ = 'room_player'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    room_id: Mapped[int] = mapped_column(ForeignKey("room.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id"))

    room: Mapped["Room"] = relationship(back_populates="players")
    user: Mapped["UserProfile"] = relationship(back_populates="room_memberships")

class Review(Base):
    __tablename__ = 'review'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id"))
    room_id: Mapped[int] = mapped_column(ForeignKey("room.id"))
    text: Mapped[Optional[str]] = mapped_column(Text)
    stars: Mapped[int] = mapped_column(SmallInteger)

    user: Mapped["UserProfile"] = relationship(back_populates="reviews")
    room: Mapped["Room"] = relationship(back_populates="reviews")