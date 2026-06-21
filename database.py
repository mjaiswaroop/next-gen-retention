from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool, QueuePool
from config import settings

def build_engine():
    """
    SQLite for dev/test. PostgreSQL for production.
    NullPool required for FastAPI async workers to prevent
    connection sharing across threads.
    """
    if settings.environment == "test":
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )
        # Import models here to avoid circular imports, then create tables for tests
        import models
        models.Base.metadata.create_all(bind=engine)
        return engine

    if "sqlite" in settings.database_url:
        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
        )
        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")   # Readers don't block writers
            cursor.execute("PRAGMA foreign_keys=ON")    # SQLite ignores FKs by default
            cursor.close()
        return engine

    # Production PostgreSQL
    return create_engine(
        settings.database_url,
        poolclass=QueuePool,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,     # Test connections before use
        pool_recycle=3600,      # Recycle connections after 1 hour
    )

engine = build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    """
    FastAPI dependency. Yields a session and guarantees cleanup.
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


