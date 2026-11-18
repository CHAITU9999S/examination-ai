import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# Database connection URL
# PostgreSQL will be used when DATABASE_URL is configured.
# SQLite is provided as a temporary local development fallback.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./examguard_dev.db"
)


# SQLite requires this additional connection argument.
connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


# Create database engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)


# Create database session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)


# Base class for all database models
class Base(DeclarativeBase):
    pass


# Database dependency for API endpoints
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
