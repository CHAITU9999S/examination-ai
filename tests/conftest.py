
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_session():
    """
    Create an isolated in-memory SQLite database for each test.
    """

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )

    db = TestingSessionLocal()

    try:
        yield db

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    """
    Create a FastAPI test client using the isolated test database.

    The client is deliberately not entered as a context manager.
    This prevents the application lifespan from starting the
    background examination scheduler during ordinary API tests.
    """

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    test_client = TestClient(app)

    try:
        yield test_client

    finally:
        app.dependency_overrides.pop(get_db, None)
