import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "admin"))

import pytest
from fastapi.testclient import TestClient

import api


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("NITRADO_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.delenv("RCON_PASSWORD", raising=False)
    monkeypatch.setattr(api, "JOBS_DIR", tmp_path / "data")
    monkeypatch.setattr(api, "JOBS_PATH", tmp_path / "data" / "jobs.json")
    with TestClient(api.app) as c:
        yield c


# ------------------------------------------------------------- cron helpers


def test_cron_matches_simple():
    dt = datetime(2026, 8, 31, 4, 0)
    assert api.cron_matches("0 4 * * *", dt)
    assert not api.cron_matches("15 4 * * *", dt)
    assert not api.cron_matches("0 5 * * *", dt)


def test_cron_matches_steps_ranges():
    dt = datetime(2026, 8, 31, 14, 30)
    assert api.cron_matches("*/30 * * * *", dt)          # 30 % 30 == 0
    assert not api.cron_matches("*/10 * * * *", dt)      # 30 % 10 == 0 -> would match
    assert api.cron_matches("5-40/5 * * * *", dt)        # 30 in range, step 5
    assert api.cron_matches("30 * * * *", dt)
    assert not api.cron_matches("10 * * * *", dt)


def test_cron_next_finds_next_hour():
    expr = "0 * * * *"
    nxt = api.cron_next(expr, datetime(2026, 8, 31, 14, 45))
    assert nxt == datetime(2026, 8, 31, 15, 0)


def test_cron_next_multi_field():
    nxt = api.cron_next("30 2 * * *", datetime(2026, 8, 31, 14, 0))
    assert nxt == datetime(2026, 9, 1, 2, 30)


def test_cron_next_bad_spec_raises():
    with pytest.raises(ValueError):
        api.cron_next("not cron", datetime.now())


# ------------------------------------------------------------- endpoint shapes


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "version" in body


def test_cluster(client):
    r = client.get("/api/cluster")
    assert r.status_code == 200
    body = r.json()
    assert "name" in body and "maps" in body


def test_config_is_sanitized(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert "nitrado_token" not in body
    assert "rcon_password" not in body
    assert isinstance(body["servers"], list) and body["servers"]
    assert "unresolved" in body


def test_servers_overview(client):
    r = client.get("/api/servers")
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "config" or body["backend"] == "nitrado"
    assert body["nitrado_error"] is None
    assert body["servers"] and all("rcon" in s for s in body["servers"])


def test_caves_presets(client):
    r = client.get("/api/caves/presets")
    assert r.status_code == 200
    body = r.json()
    assert "blueprints" in body and "presets" in body
    assert "dino_gate" in body["presets"]
    assert "maps" in body and "ragnarok" in body["maps"]


def test_caves_demo(client):
    r = client.get("/api/caves/demo/dino_gate")
    assert r.status_code == 200
    lines = r.json()["lines"]
    assert any("grid" in ln for ln in lines)
    r = client.get("/api/caves/demo/nope")
    assert r.status_code == 400


def test_caves_convert(client):
    r = client.post("/api/caves/convert",
                    json={"map": "ragnarok", "lat": 30.2, "lon": 32.8})
    assert r.status_code == 200
    body = r.json()
    assert body["command"].startswith("cheat setplayerpos")
    assert body["approx"] is False
    r = client.post("/api/caves/convert", json={"map": "ragnarok", "lat": 500, "lon": 0})
    assert r.status_code == 400


def test_caves_generate_preset(client):
    r = client.post("/api/caves/generate", json={"preset": "dino_gate"})
    assert r.status_code == 200
    body = r.json()
    assert body["commands"] and body["commands"][0].startswith(
        "cheat spawnactor")
    assert body["meta"]["hole"] == "dino"
    assert body["setplayerpos"] is None


def test_caves_generate_pipe(client):
    r = client.post("/api/caves/generate", json={
        "preset": "uw_seal", "map": "fjordur", "lat": 49.4, "lon": 14.2})
    assert r.status_code == 200
    body = r.json()
    assert body["setplayerpos"]["command"].startswith("cheat setplayerpos")
    assert all("spawnactor" in c for c in body["commands"] if c.startswith("cheat"))


def test_caves_generate_validation(client):
    r = client.post("/api/caves/generate", json={"preset": "nope"})
    assert r.status_code == 400
    r = client.post("/api/caves/generate", json={"mode": "wall", "cols": 4, "rows": 4, "hole": "behemoth"})
    assert r.status_code == 400  # hole larger than grid


# ---------------------------------------------------------------- jobs CRUD


def test_jobs_crud(client):
    r = client.post("/api/jobs", json={
        "name": "Nightly Save", "cron": "0 4 * * *", "action": "saveworld_all"})
    assert r.status_code == 200
    job = r.json()
    assert job["id"] and job["next_run"]
    jid = job["id"]

    r = client.get("/api/jobs")
    assert r.status_code == 200 and any(j["id"] == jid for j in r.json())

    r = client.post(f"/api/jobs/{jid}/toggle")
    assert r.status_code == 200 and r.json()["enabled"] is False

    r = client.delete(f"/api/jobs/{jid}")
    assert r.status_code == 200
    r = client.delete(f"/api/jobs/{jid}")
    assert r.status_code == 404


def test_jobs_validation(client):
    r = client.post("/api/jobs", json={
        "name": "x", "cron": "0 4 * * *", "action": "restart"})  # requires server
    assert r.status_code == 400
    r = client.post("/api/jobs", json={
        "name": "x", "cron": "0 4 * * *", "action": "broadcast", "server": "theisland"})
    assert r.status_code == 400  # broadcast requires message
    r = client.post("/api/jobs", json={
        "name": "x", "cron": "not cron", "action": "saveworld", "server": "theisland"})
    assert r.status_code == 400  # bad cron
    r = client.post("/api/jobs", json={
        "name": "x", "cron": "0 4 * * *", "action": "nope"})
    assert r.status_code == 400  # unknown action


def test_jobs_run_unknown(client):
    r = client.post("/api/jobs/does-not-exist/run")
    assert r.status_code == 404