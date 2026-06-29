from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from auth_config import DATABASE_URL


Base = declarative_base()
_engine = None
_SessionLocal: Optional[sessionmaker] = None


def _get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        kwargs = {}
        if DATABASE_URL.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["pool_pre_ping"] = True
        _engine = create_engine(DATABASE_URL, **kwargs)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_db() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        _get_engine()
    if _SessionLocal is None:
        raise RuntimeError("Database session is not initialized.")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_auth_db() -> None:
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
