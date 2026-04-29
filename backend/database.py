# database.py - SQLite kapcsolat és session factory
# MotoMeter backend

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os

# Adatbázis fájl helye (környezeti változóból, vagy alapértelmezett)
DB_PATH = os.environ.get("MOTOMETER_DB", "motometer.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite + FastAPI async
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Táblák létrehozása (ha még nem léteznek)."""
    from models import Track, Session, Lap  # noqa: F401 — import kell a metadata-hoz
    Base.metadata.create_all(bind=engine)
    print(f"DB: init kesz -> {DB_PATH}")
