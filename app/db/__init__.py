"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
from loguru import logger

from app.config import Config
from app.models import Base

# Create engine
engine = create_engine(
    Config.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    echo=Config.DEBUG  # Log SQL in debug mode
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Thread-safe session
Session = scoped_session(SessionLocal)


def init_db():
    """Initialize database (create tables if they don't exist)."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info('✅ Database tables created successfully')
    except Exception as error:
        logger.error(f'❌ Database initialization failed: {error}')
        raise


def get_db():
    """
    Get database session (for dependency injection).
    
    Usage in Flask:
        db = next(get_db())
        try:
            # Use db here
            db.commit()
        finally:
            db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session():
    """
    Context manager for database sessions.
    
    Usage:
        with db_session() as db:
            result = db.query(Model).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_db():
    """Close database connections."""
    Session.remove()
    engine.dispose()
    logger.info('Database connections closed')


__all__ = [
    'engine',
    'Session',
    'SessionLocal',
    'init_db',
    'get_db',
    'db_session',
    'close_db'
]
