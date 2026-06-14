from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_stub_endpoint_returns_501():
    # /chain is an unauthenticated M6 stub — still returns 501.
    res = client.get("/chain/NIFTY")
    assert res.status_code == 501


# /stream is now an auth-gated live feed (M4 Phase 2); behavior is covered in
# tests/test_stream.py.
