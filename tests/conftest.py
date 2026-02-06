import pytest
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from brokerage_parser.db import Base
from brokerage_parser.config import settings
from brokerage_parser.api import app
from brokerage_parser.db import get_db

# Test Configuration
# settings.EMAIL_PROVIDER = "console"
# settings.REDIS_URL = "redis://mock"

# Mock Redis only if using mock URL (Optional, or just allow connection error if not present)
# from unittest.mock import MagicMock
# import redis
# is_mock = settings.REDIS_URL == "redis://mock"
# if is_mock:
#    mock_redis = MagicMock()
#    redis.from_url = MagicMock(return_value=mock_redis)

engine = create_engine(settings.DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Creates a fresh sqlalchemy session for each test that operates in a transaction.
    The transaction is rolled back at the end of the test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Optional: Bind this session to the FastAPI app dependency
    # app.dependency_overrides[get_db] = lambda: session

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    from fastapi.testclient import TestClient

    # Override get_db to use our test session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
