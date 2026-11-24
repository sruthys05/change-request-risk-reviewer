import os
import tempfile

os.environ["DB_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

import pytest
from fastapi.testclient import TestClient

import agent
from main import app

ALICE = {"X-User": "alice"}  # engineer
BOB = {"X-User": "bob"}      # approver

GOOD = '{"risk": "high", "reasons": ["Power load"], "recommendation": "Check capacity"}'


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def new_change(client):
    r = client.post("/changes", json={"title": "Add 20 servers", "description": "Rack B"},
                    headers=ALICE)
    return r.json()["id"]


def audit_actions(client):
    return [a["action"] for a in client.get("/audit", headers=ALICE).json()]


def test_engineer_cannot_approve(client, monkeypatch):
    monkeypatch.setattr(agent, "call_llm", lambda p: GOOD)
    cid = new_change(client)
    client.post(f"/changes/{cid}/review", headers=ALICE)
    assert client.post(f"/changes/{cid}/approve", headers=ALICE).status_code == 403


def test_cannot_approve_pending(client):
    cid = new_change(client)
    assert client.post(f"/changes/{cid}/approve", headers=BOB).status_code == 409


def test_happy_path_and_audit(client, monkeypatch):
    monkeypatch.setattr(agent, "call_llm", lambda p: GOOD)
    cid = new_change(client)
    r = client.post(f"/changes/{cid}/review", headers=ALICE).json()
    assert r["status"] == "agent_reviewed"  # service moved it
    assert r["risk_summary"]["risk"] == "high"
    r = client.post(f"/changes/{cid}/approve", headers=BOB).json()
    assert r["status"] == "approved"
    actions = audit_actions(client)
    for a in ["created", "review_done", "approved"]:
        assert a in actions


def test_bad_json_is_logged_and_stays_pending(client, monkeypatch):
    monkeypatch.setattr(agent, "call_llm", lambda p: "not json")
    cid = new_change(client)
    assert client.post(f"/changes/{cid}/review", headers=ALICE).status_code == 502
    assert client.get(f"/changes/{cid}", headers=ALICE).json()["status"] == "pending"
    assert "review_failed" in audit_actions(client)


def test_retry_once_then_succeed(client, monkeypatch):
    answers = iter(["oops", GOOD])
    monkeypatch.setattr(agent, "call_llm", lambda p: next(answers))
    cid = new_change(client)
    assert client.post(f"/changes/{cid}/review", headers=ALICE).status_code == 200


def test_cannot_review_twice(client, monkeypatch):
    monkeypatch.setattr(agent, "call_llm", lambda p: GOOD)
    cid = new_change(client)
    client.post(f"/changes/{cid}/review", headers=ALICE)
    assert client.post(f"/changes/{cid}/review", headers=ALICE).status_code == 409
