"""
Security tests: password hashing, admin seed, authentication on API routes,
SPA path traversal.
"""

import hashlib
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database, dependencies, models
from app.main import app
from app.services import auth_service

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    models.Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        models.Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[database.get_db] = override_get_db
    app.dependency_overrides[dependencies.get_db] = override_get_db
    # No "with": the lifespan (schedulers, Browserless) is not started
    yield TestClient(app)
    app.dependency_overrides.clear()


def _token(user: models.User) -> dict:
    return {"Authorization": f"Bearer {auth_service.create_token(user.id, user.username, user.is_admin)}"}


class TestPasswordHashing:
    def test_bcrypt_hash_and_verify(self):
        h = auth_service.hash_password("s3cret")
        assert h.startswith("$2b$")
        assert auth_service.verify_password("s3cret", h)
        assert not auth_service.verify_password("wrong", h)

    def test_long_password_not_truncated(self):
        h = auth_service.hash_password("a" * 100)
        assert not auth_service.verify_password("a" * 72, h)

    def test_legacy_hash_verified_and_upgraded(self, db):
        salt = "abcd"
        legacy = f"{salt}:{hashlib.sha256(f'{salt}oldpass'.encode()).hexdigest()}"
        db.add(models.User(username="legacy", password_hash=legacy, is_admin=False, is_active=True))
        db.commit()

        assert auth_service.authenticate_user(db, "legacy", "wrong") is None
        user = auth_service.authenticate_user(db, "legacy", "oldpass")
        assert user is not None
        assert user.password_hash.startswith("$2b$")
        assert auth_service.authenticate_user(db, "legacy", "oldpass") is not None


class TestAdminSeed:
    def test_seed_uses_env_password(self, db, monkeypatch):
        monkeypatch.setenv("ADMIN_PASSWORD", "from-env-123")
        assert auth_service.seed_default_admin(db)
        assert auth_service.authenticate_user(db, "admin", "from-env-123") is not None
        assert auth_service.authenticate_user(db, "admin", "admin") is None

    def test_seed_random_password(self, db, monkeypatch):
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        assert auth_service.seed_default_admin(db)
        assert auth_service.authenticate_user(db, "admin", "admin") is None
        assert not auth_service.seed_default_admin(db)


class TestRouteAuthentication:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("get", "/api/items"),
            ("post", "/api/jobs/refresh-all"),
            ("get", "/api/settings"),
            ("get", "/api/notifications/channels"),
            ("get", "/api/search-sites"),
            ("get", "/api/openrouter/models"),
        ],
    )
    def test_requires_token(self, client, method, path):
        assert getattr(client, method)(path).status_code == 401

    def test_debug_login_removed(self, client):
        assert client.get("/api/auth/debug-login").json() == {"message": "Not found"}

    def test_admin_routes_forbidden_for_users(self, client, db):
        user = auth_service.create_user(db, "bob", "pw", is_admin=False)
        headers = _token(user)
        assert client.get("/api/items", headers=headers).status_code == 200
        assert client.get("/api/settings", headers=headers).status_code == 403
        assert client.post("/api/search-sites/reset", headers=headers).status_code == 403
        r = client.post(
            "/api/notifications/channels",
            json={"name": "x", "type": "discord", "configuration": "json://127.0.0.1"},
            headers=headers,
        )
        assert r.status_code == 403

    def test_channel_configuration_hidden_for_users(self, client, db):
        db.add(models.NotificationChannel(name="c", type="discord", configuration='{"webhook_url":"secret"}'))
        db.commit()
        user = auth_service.create_user(db, "bob", "pw", is_admin=False)
        admin = auth_service.create_user(db, "root", "pw", is_admin=True)
        assert client.get("/api/notifications/channels", headers=_token(user)).json()[0]["configuration"] == ""
        assert "secret" in client.get("/api/notifications/channels", headers=_token(admin)).json()[0]["configuration"]

    def test_update_item_rejects_internal_url(self, client, db):
        user = auth_service.create_user(db, "bob", "pw", is_admin=False)
        item = models.Item(url="https://example.com/p", name="p")
        db.add(item)
        db.commit()
        r = client.put(
            f"/api/items/{item.id}",
            json={"url": "http://169.254.169.254/latest/meta-data/", "name": "p"},
            headers=_token(user),
        )
        assert r.status_code == 400


class TestSpaPathTraversal:
    def test_traversal_not_served(self, client, tmp_path, monkeypatch):
        static = tmp_path / "static"
        static.mkdir()
        (static / "index.html").write_text("INDEX")
        (tmp_path / "secret.txt").write_text("SECRET")
        monkeypatch.chdir(tmp_path)
        for path in ["/..%2Fsecret.txt", "/%2E%2E/secret.txt", "/foo/..%2F..%2Fsecret.txt"]:
            assert "SECRET" not in client.get(path).text


class TestLoginRateLimit:
    def test_login_works_and_is_rate_limited(self, client, db):
        auth_service.create_user(db, "carol", "good-pass", is_admin=False)
        ok = client.post("/api/auth/login", json={"username": "carol", "password": "good-pass"})
        assert ok.status_code == 200
        assert "token" in ok.json()
        codes = [
            client.post("/api/auth/login", json={"username": "carol", "password": "bad"}).status_code
            for _ in range(12)
        ]
        assert 429 in codes
