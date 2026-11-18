
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool


# ==========================================
# DATABASE CONFIGURATION
# ==========================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./examguard_dev.db"
)


# Normalize PostgreSQL URLs for Psycopg 3.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql+psycopg://",
        1
    )

elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )


# ==========================================
# DATABASE ENGINE
# ==========================================

connect_args = {}

engine_options = {
    "pool_pre_ping": True,
}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False
    }

    engine_options["connect_args"] = connect_args

else:
    # Avoid keeping persistent connections in serverless
    # PostgreSQL environments when configured this way.
    if os.getenv("DB_USE_NULL_POOL", "False").lower() == "true":
        engine_options["poolclass"] = NullPool


engine = create_engine(
    DATABASE_URL,
    **engine_options
)


# ==========================================
# DATABASE SESSION FACTORY
# ==========================================

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)


# ==========================================
# SQLALCHEMY BASE
# ==========================================

class Base(DeclarativeBase):
    pass


# ==========================================
# DATABASE DEPENDENCY
# ==========================================

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
