from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from brokerage_parser.config import settings

# Database Setup
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.SQLALCHEMY_POOL_SIZE,
    max_overflow=settings.SQLALCHEMY_MAX_OVERFLOW,
    pool_timeout=settings.SQLALCHEMY_POOL_TIMEOUT,
    pool_recycle=settings.SQLALCHEMY_POOL_RECYCLE,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    # TODO: Multi-tenancy Session Injection will happen here
    try:
        yield db
    finally:
        db.close()
