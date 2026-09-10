from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

DB_URL = 'postgresql://postgres:admin@localhost/mafia'
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()
