import os
import sys

# Make `app` importable when running pytest from the backend root.
sys.path.insert(0, os.path.dirname(__file__))

# Configure a throwaway SQLite database + test secrets BEFORE the app is imported.
os.environ.setdefault("DATABASE_URL", "sqlite:///./_pytest.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-32b!")
os.environ.setdefault("REAL_MONEY_ENABLED", "false")

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    from app.db.base import Base
    from app.db.session import engine
    import app.main  # noqa: F401  ensures all models are registered
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    try:
        os.remove("./_pytest.db")
    except OSError:
        pass


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def register_and_login(client, email, username, password="password123"):
    client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "password": password, "is_18_plus": True,
    })
    tok = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()
    return tok["access_token"]
