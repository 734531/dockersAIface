import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv('DATABASE_URL', 'mysql+pymysql://nba:change-me@localhost:3307/nba_lab?charset=utf8mb4')

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={'charset': 'utf8mb4', 'use_unicode': True},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        db.execute(text('SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci'))
        yield db
    finally:
        db.close()
