from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
from config.settings import DATABASE_URL
from contextlib import contextmanager
import os

# Create database engine with safe Supabase/PostgreSQL settings
is_postgres = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")

if is_postgres:
    import ssl

    db_url = DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+pg8000://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1)

    # Remove sslmode from db_url if it exists because pg8000 doesn't like it
    if "sslmode=" in db_url:
        db_url = db_url.replace("?sslmode=require", "").replace("&sslmode=require", "")

    # create default SSL context for pg8000
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # Allow runtime configuration of pool behavior via env vars:
    # - DB_USE_NULL_POOL (true/1) to use NullPool (no persistent connections)
    # - DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT to tune QueuePool
    use_null = os.getenv("DB_USE_NULL_POOL", "").lower() in ("1", "true", "yes")
    # Auto-enable NullPool for serverless providers (common pattern)
    if not use_null and ("supabase.co" in db_url or os.getenv("DB_SERVERLESS", "").lower() in ("1", "true", "yes")):
        use_null = True

    if use_null:
        engine = create_engine(
            db_url,
            poolclass=NullPool,
            connect_args={
                "ssl_context": ssl_context,
                "timeout": 10,
            },
        )
    else:
        pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "0"))
        pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_timeout=pool_timeout,
            max_overflow=max_overflow,
            pool_size=pool_size,
            connect_args={
                "ssl_context": ssl_context,
                "timeout": 10,
            },
        )
else:
    engine = create_engine(DATABASE_URL, echo=False, connect_args={"timeout": 15})

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# Base class for models
Base = declarative_base()

def get_db():
    """Yields a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """Get a safe database session"""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.rollback()
        raise

@contextmanager
def db_session():
    """Context manager for safe database transactions"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
