# src/database/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from src.core.config import config

DATABASE_URL = os.getenv("DATABASE_URL", config.get("database.url"))

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=int(config.get("database.pool_size", 10)),
    max_overflow=int(config.get("database.max_overflow", 20)),
    pool_timeout=int(config.get("database.pool_timeout", 30)),
    pool_recycle=int(config.get("database.pool_recycle", 1800)),
    pool_pre_ping=bool(config.get("database.pool_pre_ping", True)),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()