import os
import tempfile
import uuid

# Settings are read at import time, so the environment must be prepared before importing the app.
_tmp = tempfile.mkdtemp()
os.environ.update(
    DATABASE_URL=f"sqlite:///{_tmp}/test.db", SECRET_KEY="t" * 40, SEED_DEMO_USER="false",
    GROQ_API_KEY="", SERVE_FRONTEND="false", ENVIRONMENT="development",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.deps import get_ai  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402

from .fakes import FakeAI  # noqa: E402


auth_router.register_limiter.max_events = 10_000  # tests create many users from one address


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # entering the context runs the lifespan, which creates tables and seeds questions
        yield c


@pytest.fixture()
def auth(client):
    """Headers for a freshly registered user, so tests never share quiz history."""
    email = f"{uuid.uuid4().hex[:10]}@example.com"
    response = client.post("/api/auth/register", json={"name": "Test User", "email": email, "password": "Passw0rdOK"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def fake_ai():
    def install(**kwargs):
        ai = FakeAI(**kwargs)
        app.dependency_overrides[get_ai] = lambda: ai
        return ai

    yield install
    app.dependency_overrides.pop(get_ai, None)
