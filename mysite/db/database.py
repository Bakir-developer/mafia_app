from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import create_engine

DB_URL = 'postgresql://postgres:admin@localhost/mafia_app'
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass