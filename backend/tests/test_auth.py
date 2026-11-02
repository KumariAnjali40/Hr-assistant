import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import auth
from app.config import settings

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(**over):
    claims = {
        "sub": "u1", "preferred_username": "alice", "iat": int(time.time()), "exp": int(time.time()) + 300,
        "iss": settings.oidc_issuer, "aud": settings.oidc_audience, "realm_access": {"roles": ["employee"]},
    }
    claims.update(over)
    return jwt.encode(claims, KEY, algorithm="RS256")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(auth._jwks, "get_signing_key_from_jwt", lambda t: SimpleNamespace(key=KEY.public_key()))
    app = FastAPI()

    @app.get("/me")
    async def me(u: auth.User = Depends(auth.current_user)):
        return {"username": u.username, "roles": sorted(u.roles)}

    @app.get("/hr-only")
    async def hr_only(u: auth.User = Depends(auth.require_role("hr"))):
        return {"ok": True}

    return TestClient(app)


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_valid_token(client):
    r = client.get("/me", headers=h(make_token()))
    assert r.status_code == 200 and r.json()["username"] == "alice"


def test_missing_token(client):
    assert client.get("/me").status_code == 401


def test_expired_token(client):
    assert client.get("/me", headers=h(make_token(exp=int(time.time()) - 10))).status_code == 401


def test_wrong_audience(client):
    assert client.get("/me", headers=h(make_token(aud="other-app"))).status_code == 401


def test_wrong_issuer(client):
    assert client.get("/me", headers=h(make_token(iss="http://evil"))).status_code == 401


def test_employee_cannot_hit_hr_endpoint(client):
    assert client.get("/hr-only", headers=h(make_token())).status_code == 403


def test_hr_can(client):
    assert client.get("/hr-only", headers=h(make_token(realm_access={"roles": ["hr"]}))).status_code == 200
