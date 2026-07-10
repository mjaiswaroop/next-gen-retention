import contextvars
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session, with_loader_criteria
from sqlalchemy.pool import NullPool, QueuePool
from config import settings

# Thread-safe global tenant context
active_tenant_id: contextvars.ContextVar[int] = contextvars.ContextVar("active_tenant_id", default=None)

@event.listens_for(Session, "do_orm_execute")
def receive_do_orm_execute(execute_state):
    # Only enforce if we're not running internal setup or migrations
    if execute_state.execution_options.get("skip_tenant_check", False):
        return
        
    tenant = active_tenant_id.get()
    if tenant is None:
        raise PermissionError("Security Violation: No active tenant context established.")

    # Apply global filtering to all models inheriting from MultiTenantModelMixin
    if execute_state.is_select:
        from models import MultiTenantModelMixin
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                MultiTenantModelMixin,
                lambda cls: getattr(cls, 'tenant_id', getattr(cls, 'merchant_id', None)) == tenant,
                include_aliases=True,
                propagate_to_loaders=True
            )
        )

@event.listens_for(Session, "before_flush")
def _enforce_tenant_integrity(session, flush_context, instances):
    tenant = active_tenant_id.get()
    if tenant is None:
        return # Setup/migrations might flush without tenant
        
    from models import MultiTenantModelMixin
    for obj in session.new | session.dirty:
        if isinstance(obj, MultiTenantModelMixin):
            obj_tenant = getattr(obj, 'tenant_id', getattr(obj, 'merchant_id', None))
            if obj_tenant is not None and obj_tenant != tenant:
                raise ValueError(f"Security Violation: Tenant ID mismatch on database write. Expected {tenant}, got {obj_tenant}")

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


