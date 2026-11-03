import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import cache, models, ratelimit  # noqa: F401
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql://shortener:shortener@localhost:5432/shortener_test"

engine = create_engine(TEST_DATABASE_URL)
TestingSession = sessionmaker(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    test_redis = redis.Redis(host="localhost", port=6379, db=1, decode_responses=True)
    test_redis.flushdb()
    monkeypatch.setattr(cache, "redis_client", test_redis)
    monkeypatch.setattr(ratelimit, "redis_client", test_redis)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE clicks, links RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()