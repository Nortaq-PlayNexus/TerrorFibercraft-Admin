#!/usr/bin/env python3
"""
api.py — Local HTTP API bridge for the Terror Fibercraft admin console.

FastAPI + uvicorn. Serves the JSON API the frontend (and any LAN admin tool)
talks to. Binds 127.0.0.1 by default; requests never leave the machine unless
you pass --external.

Run:
    python api.py                          # 127.0.0.1:8765
    python api.py --port 8766 --external   # 0.0.0.0 (behind a firewall)
    python api.py --no-scheduler           # disable the maintenance-job loop

Endpoints (all under /api):
    GET  /health            liveness + backend version
    GET  /cluster           cluster.json contents (single source of truth)
    GET  /servers           configured servers, live Nitrado status when a token exists
    GET  /config            sanitized config (secrets stripped)
    POST /rcon/{name}/command   {command}         run one RCON command
    POST /rcon/{name}/broadcast {message}[,minutes] in-game broadcast
    GET  /caves/presets     blueprints / presets / maps / hole sizes
    GET  /caves/demo/{preset}   ASCII grid preview
    POST /caves/generate    build spawnactor command batch (JSON in)
    POST /caves/convert     lat/lon -> setplayerpos
    GET  /jobs              maintenance jobs (scheduled RCON / Nitrado actions)
    POST /jobs              create a job
    POST /jobs/{id}/toggle  enable/disable
    POST /jobs/{id}/run     execute now
    DELETE /jobs/{id}

Mutating endpoints require X-API-Token when config.json sets an ``api_token``.
"""
import argparse
import json
import os
import re
import sys
import threading
import time
import uuid
from argparse import Namespace
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ark_rcon
import cave_spawn_generator as cave
import nitrado_client
from config import load_config

APP_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Config wrapper (never leaks secrets to the API surface)
# ---------------------------------------------------------------------------

_SECRET_KEYS = {"discord_token", "nitrado_token", "rcon_password", "api_token"}


def _config():
    return load_config()


def _sanitized_config(cfg):
    """Config copy with tokens/passwords replaced by booleans/redaction."""
    out = dict(cfg)
    for key in _SECRET_KEYS:
        if key in out:
            out[key] = bool(out.get(key))
    for name, s in out.get("servers", {}).items():
        if isinstance(s, dict) and "rcon_password" in s:
            s = dict(s)
            s["rcon_password"] = bool(s["rcon_password"])
            out["servers"][name] = s
    out.pop("_comment", None)
    return out


def _cluster_json():
    cfg = _config()
    for cand in (
        os.environ.get("TFC_CLUSTER", ""),
        str(Path(cfg.get("_resolved_from", "")).parent.parent.parent / "cluster" / "cluster.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "cluster", "cluster.json"),
    ):
        if cand and os.path.exists(cand):
            with open(cand, encoding="utf-8") as f:
                return json.load(f)
    raise HTTPException(500, "cluster.json not found")


# ---------------------------------------------------------------------------
# Nitrado (best-effort; cached so the UI never blocks on a dead token)
# ---------------------------------------------------------------------------

_STATUS_CACHE = {"ts": 0.0, "data": None, "error": None}
_STATUS_TTL = 30.0


def _nitrado_client():
    token = os.environ.get("NITRADO_TOKEN") or _config().get("nitrado_token")
    return nitrado_client.NitradoClient(token) if token else None


def _server_overview():
    cfg = _config()
    servers = cfg.get("servers", {})
    entries = []
    for name, s in servers.items():
        entries.append({
            "name": name,
            "service_id": s.get("service_id"),
            "gameserver_id": s.get("gameserver_id"),
            "rcon": {
                "host": s.get("rcon_host", ""),
                "port": s.get("rcon_port"),
                "configured": bool(s.get("rcon_password")),
            },
        })
    now = time.time()
    live = None
    error = None
    client = _nitrado_client()
    if client is not None:
        if now - _STATUS_CACHE["ts"] > _STATUS_TTL:
            try:
                info = {f"{s.service_id}:{s.id}": s for s in client.list_servers()}
                _STATUS_CACHE.update(ts=now, data=info, error=None)
            except nitrado_client.NitradoError as e:
                _STATUS_CACHE.update(ts=now, data=None, error=str(e))
        live, error = _STATUS_CACHE["data"], _STATUS_CACHE["error"]
    return {
        "servers": entries,
        "live": live if live else None,
        "nitrado_error": error,
        "backend": "nitrado" if client is not None else "config",
    }


# ---------------------------------------------------------------------------
# Caves generator namespace adapter (argparse Namespace -> JSON is clumsy)
# ---------------------------------------------------------------------------

def _gen_args(payload):
    args = Namespace(
        blueprint=payload.get("blueprint", "tribute_red"),
        mode=payload.get("mode"),
        cols=payload.get("cols", 7),
        rows=payload.get("rows", 5),
        depth=payload.get("depth", 7),
        spacing=payload.get("spacing", 400),
        forward=payload.get("forward", 400),
        zstart=payload.get("zstart", 0),
        hole=payload.get("hole", "none"),
        floor=bool(payload.get("floor", False)),
        ceiling=bool(payload.get("ceiling", False)),
        preset=payload.get("preset"),
        json=False,
        out=None,
        map=payload.get("map"),
        lat=payload.get("lat"),
        lon=payload.get("lon"),
        z=payload.get("z", 0),
    )
    if args.preset:
        if args.preset not in cave.PRESETS:
            raise HTTPException(400, f"Unknown preset '{args.preset}'")
        for k, v in cave.PRESETS[args.preset].items():
            setattr(args, k, v)
        args.preset = payload.get("preset")
    return args


# ---------------------------------------------------------------------------
# Maintenance jobs scheduler (cron -> RCON / Nitrado actions)
# ---------------------------------------------------------------------------

JOBS_DIR = Path(os.environ.get("TFC_API_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))) / "data"
JOBS_PATH = JOBS_DIR / "jobs.json"
_JOBS_LOCK = threading.Lock()

ACTIONS = ("broadcast", "broadcast_all", "saveworld", "saveworld_all", "restart")
_server_nitrado = {"_checked": False, "client": None}


def _nitrado_cached():
    if not _server_nitrado["_checked"]:
        _server_nitrado["client"] = _nitrado_client()
        _server_nitrado["_checked"] = True
    return _server_nitrado["client"]


def _cron_field_matches(expr, value):
    if expr in ("*", ""):
        return True
    for part in expr.split(","):
        part = part.strip()
        if part in ("*", ""):
            return True
        step = None
        m = re.match(r"^(\d+)-(\d+)(?:/(\d+))?$", part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            step = int(m.group(3)) if m.group(3) else 1
            if lo <= value <= hi and (value - lo) % step == 0:
                return True
            continue
        m = re.match(r"^(\d+)/(\d+)$", part)
        if m:
            start, step = int(m.group(1)), int(m.group(2))
            if value >= start and (value - start) % step == 0:
                return True
            continue
        m = re.match(r"^(\d+)$", part)
        if m and int(m.group(1)) == value:
            return True
    return False


def cron_matches(expr, dt):
    """5-field cron match: minute hour day-of-month month day-of-week."""
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"cron must have 5 fields, got {len(fields)}")
    return (
        _cron_field_matches(fields[0], dt.minute)
        and _cron_field_matches(fields[1], dt.hour)
        and _cron_field_matches(fields[2], dt.day)
        and _cron_field_matches(fields[3], dt.month)
        and _cron_field_matches(fields[4], dt.isoweekday())
    )


def cron_next(expr, after, max_steps=3660):
    """Next datetime matching `expr` strictly after `after`, or None."""
    probe = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(max_steps):
        if cron_matches(expr, probe):
            return probe
        probe += timedelta(minutes=1)
    return None


def _load_jobs():
    with _JOBS_LOCK:
        if not JOBS_PATH.exists():
            return []
        try:
            with open(JOBS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []


def _save_jobs(jobs):
    with _JOBS_LOCK:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        with open(JOBS_PATH, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)


def _rcon_for(server_name):
    s = _config().get("servers", {}).get(server_name)
    if not s:
        return None
    host, port = s.get("rcon_host", ""), s.get("rcon_port")
    pw = s.get("rcon_password")
    if not host or not port or not pw:
        return None
    return ark_rcon.RconClient(host, int(port), pw,
                               max_retries=2, retry_base_delay=0.3,
                               retry_max_delay=1.5)


def _run_job(job):
    """Execute a job's action; returns (ok, detail)."""
    action = job.get("action")
    try:
        if action in ("broadcast", "saveworld", "restart"):
            conn = _rcon_for(job.get("server"))
            if conn is None:
                raise RuntimeError(f"server '{job.get('server')}' not RCON-configurable")
            with conn:
                if action == "broadcast":
                    return (True, conn.broadcast(job.get("message", "")))
                if action == "saveworld":
                    return (True, conn.send("saveworld"))
                # restart: warn players first, then Nitrado (if token exists)
                conn.broadcast("Restart in 60 seconds.")
                client = _nitrado_cached()
                s = _config()["servers"][job["server"]]
                if client is None:
                    raise RuntimeError("NITRADO_TOKEN not configured for restart job")
                client.restart(s["service_id"], s["gameserver_id"], "Scheduled admin restart")
                return (True, "restart issued")
        if action in ("broadcast_all", "saveworld_all"):
            cfg = _config()
            results = []
            for name in cfg.get("servers", {}):
                conn = _rcon_for(name)
                if conn is None:
                    results.append(f"{name}: skipped (rcon unset)")
                    continue
                with conn:
                    if action == "broadcast_all":
                        conn.broadcast(job.get("message", ""))
                        results.append(f"{name}: broadcast")
                    else:
                        conn.send("saveworld")
                        results.append(f"{name}: saved")
            return (True, "; ".join(results))
        raise RuntimeError(f"unknown action '{action}'")
    except Exception as e:
        return (False, str(e))


def _finalise_job(job, ok, detail):
    job["last_run"] = datetime.now().isoformat(timespec="seconds")
    job["last_status"] = "ok" if ok else "error"
    job["last_error"] = None if ok else detail
    nxt = cron_next(job.get("cron", "* * * * *"), datetime.now())
    job["next_run"] = nxt.isoformat(timespec="seconds") if nxt else None


def _exec_job_thread(job):
    def work():
        ok, detail = _run_job(job)
        jobs = _load_jobs()
        for j in jobs:
            if j.get("id") == job.get("id"):
                _finalise_job(j, ok, detail)
                break
        _save_jobs(jobs)

    threading.Thread(target=work, daemon=True).start()


def _scheduler_loop(stop_event):
    last_seen = {}
    while not stop_event.is_set():
        try:
            jobs = _load_jobs()
            now = datetime.now()
            for job in jobs:
                if not job.get("enabled"):
                    continue
                job_id = job.get("id")
                key = (job_id, str(job.get("next_run")))
                due = False
                if job.get("next_run"):
                    try:
                        due = datetime.fromisoformat(job["next_run"]) <= now
                    except ValueError:
                        due = True
                if due and last_seen.get(key, False) is False:
                    last_seen[key] = True
                    _exec_job_thread(job)
                elif not due:
                    last_seen.pop(key, None)
        except Exception:
            pass
        time.sleep(10)


_stop_event = threading.Event()
_scheduler_thread = None


def _start_scheduler():
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop,
                                         args=(_stop_event,), daemon=True)
    _scheduler_thread.start()


def _stop_scheduler():
    _stop_event.set()


# ---------------------------------------------------------------------------
# Payload models
# ---------------------------------------------------------------------------

class CommandBody(BaseModel):
    command: str = Field(..., min_length=1)


class BroadcastBody(BaseModel):
    message: str = Field(..., min_length=1)
    minutes: int | None = None


class ConvertBody(BaseModel):
    map: str
    lat: float
    lon: float
    z: float | None = None


class JobBody(BaseModel):
    name: str
    cron: str
    action: str
    server: str | None = None
    message: str | None = None
    enabled: bool = True


# ---------------------------------------------------------------------------
# Auth (only when config.json defines api_token)
# ---------------------------------------------------------------------------

def require_admin(x_api_token: str | None = Header(default=None)):
    token = _config().get("api_token")
    if token and x_api_token != token:
        raise HTTPException(401, "invalid or missing X-API-Token")


@asynccontextmanager
async def lifespan(_app):
    _start_scheduler()
    yield
    _stop_scheduler()


app = FastAPI(
    title="Terror Fibercraft Admin API",
    version=APP_VERSION,
    description="Admin console bridge: Nitrado, RCON, cave generator, jobs.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- health
@app.get("/api/health")
def health():
    return {
        "ok": True,
        "version": APP_VERSION,
        "time": datetime.now().isoformat(timespec="seconds"),
        "nitrado_token": _nitrado_client() is not None,
        "jobs_enabled": True,
    }


# ---------------------------------------------------------------- cluster
@app.get("/api/cluster")
def cluster_info():
    return _cluster_json()


# ---------------------------------------------------------------- servers
@app.get("/api/servers")
def servers():
    return _server_overview()


# ---------------------------------------------------------------- config
@app.get("/api/config")
def config_info():
    cfg = _config()
    return {
        "servers": sorted(cfg.get("servers", {})),
        "admin_role": cfg.get("admin_role"),
        "donate_message": cfg.get("donate_message"),
        "unresolved": [f"{field} ({var})" for field, var in cfg.get("_unresolved", [])],
        "resolved_from": cfg.get("_resolved_from"),
        "api_token_set": bool(cfg.get("api_token")),
    }


# ---------------------------------------------------------------- rcon
@app.post("/api/rcon/{name}/command", dependencies=[Depends(require_admin)])
def rcon_command(name: str, body: CommandBody):
    conn = _rcon_for(name)
    if conn is None:
        raise HTTPException(422, f"server '{name}' has no RCON config")
    try:
        with conn:
            return {"ok": True, "response": conn.send(body.command)}
    except ark_rcon.RconError as e:
        raise HTTPException(502, f"RCON failed: {e}")


@app.post("/api/rcon/{name}/broadcast", dependencies=[Depends(require_admin)])
def rcon_broadcast(name: str, body: BroadcastBody):
    conn = _rcon_for(name)
    if conn is None:
        raise HTTPException(422, f"server '{name}' has no RCON config")
    try:
        with conn:
            return {"ok": True, "response": conn.broadcast(body.message)}
    except ark_rcon.RconError as e:
        raise HTTPException(502, f"RCON failed: {e}")


# ---------------------------------------------------------------- caves
@app.get("/api/caves/presets")
def caves_presets():
    return {
        "blueprints": {k: v for k, v in sorted(cave.BLUEPRINTS.items())},
        "presets": {k: v for k, v in sorted(cave.PRESETS.items())},
        "maps": {k: {"approx": v[4]} for k, v in sorted(cave.MAP_TRANSFORMS.items())},
        "hole_presets": dict(cave.HOLE_PRESETS),
        "modes": ["wall", "floor", "platform", "box"],
    }


@app.get("/api/caves/demo/{preset}")
def caves_demo(preset: str):
    try:
        return {"preset": preset, "lines": cave.demo_lines(preset)}
    except SystemExit as e:
        raise HTTPException(400, str(e))


@app.post("/api/caves/convert")
def caves_convert(body: ConvertBody):
    if body.map not in cave.MAP_TRANSFORMS:
        raise HTTPException(400, f"map must be one of: {', '.join(cave.MAP_TRANSFORMS)}")
    if not (0.0 <= body.lat <= 100.0) or not (0.0 <= body.lon <= 100.0):
        raise HTTPException(400, "lat/lon must be 0..100")
    slat, slon, mlat, mlon, approx = cave.MAP_TRANSFORMS[body.map]
    x = (body.lon - slon) * mlon
    y = (body.lat - slat) * mlat
    z = body.z if body.z is not None else 0
    return {
        "map": body.map,
        "lat": body.lat,
        "lon": body.lon,
        "x": round(x),
        "y": round(y),
        "z": z,
        "approx": bool(approx),
        "command": f"cheat setplayerpos {x:.0f} {y:.0f} {z:.0f}",
    }


@app.post("/api/caves/generate", dependencies=[Depends(require_admin)])
def caves_generate(body: dict = Body(...)):
    args = _gen_args(body)
    try:
        pipe = args.map is not None
        if pipe:
            if args.lat is None or args.lon is None:
                raise HTTPException(400, "--map requires lat and lon")
            if args.map not in cave.MAP_TRANSFORMS:
                raise SystemExit("map must be one of: " + ", ".join(cave.MAP_TRANSFORMS))
            if not (0.0 <= float(args.lat) <= 100.0) or not (0.0 <= float(args.lon) <= 100.0):
                raise SystemExit("ERROR: lat/lon must be valid map coordinates 0..100.")
        lines, meta = cave.build_commands(args)
        payload = {"meta": meta, "commands": lines}
        if pipe:
            slat, slon, mlat, mlon, approx = cave.MAP_TRANSFORMS[args.map]
            payload["setplayerpos"] = {
                "map": args.map, "lat": args.lat, "lon": args.lon,
                "x": round((args.lon - slon) * mlon),
                "y": round((args.lat - slat) * mlat),
                "z": round(float(args.z)),
                "approx": bool(approx),
                "command": f"cheat setplayerpos {(args.lon - slon) * mlon:.0f} "
                           f"{(args.lat - slat) * mlat:.0f} {float(args.z):.0f}",
            }
        else:
            payload["setplayerpos"] = None
        return payload
    except SystemExit as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------- jobs
@app.get("/api/jobs")
def jobs_list():
    return _load_jobs()


@app.post("/api/jobs", dependencies=[Depends(require_admin)])
def jobs_create(body: JobBody):
    if body.action not in ACTIONS:
        raise HTTPException(400, f"action must be one of: {', '.join(ACTIONS)}")
    try:
        cron_next(body.cron, datetime.now())
    except ValueError as e:
        raise HTTPException(400, f"bad cron: {e}")
    if body.action in ("broadcast", "saveworld", "restart") and not body.server:
        raise HTTPException(400, f"action '{body.action}' requires a server")
    if body.action in ("broadcast", "broadcast_all") and not body.message:
        raise HTTPException(400, "broadcast actions require a message")
    job = {
        "id": uuid.uuid4().hex[:12],
        "name": body.name,
        "cron": body.cron,
        "action": body.action,
        "server": body.server,
        "message": body.message,
        "enabled": body.enabled,
        "created": datetime.now().isoformat(timespec="seconds"),
        "last_run": None,
        "last_status": None,
        "last_error": None,
        "next_run": cron_next(body.cron, datetime.now()).isoformat(timespec="seconds")
        if body.enabled else None,
    }
    jobs = _load_jobs()
    jobs.append(job)
    _save_jobs(jobs)
    return job


@app.post("/api/jobs/{job_id}/toggle", dependencies=[Depends(require_admin)])
def jobs_toggle(job_id: str):
    jobs = _load_jobs()
    for job in jobs:
        if job.get("id") == job_id:
            job["enabled"] = not job["enabled"]
            job["next_run"] = (cron_next(job.get("cron", "* * * * *"), datetime.now())
                               .isoformat(timespec="seconds") if job["enabled"] else None)
            _save_jobs(jobs)
            return job
    raise HTTPException(404, "job not found")


@app.post("/api/jobs/{job_id}/run", dependencies=[Depends(require_admin)])
def jobs_run(job_id: str):
    jobs = _load_jobs()
    for job in jobs:
        if job.get("id") == job_id:
            cfg = _config()
            if job.get("server") and job["server"] not in cfg.get("servers", {}):
                raise HTTPException(422, f"server '{job['server']}' not in config")
            _exec_job_thread(job, run_now=True)
            return {"ok": True, "job": job}
    raise HTTPException(404, "job not found")


@app.delete("/api/jobs/{job_id}", dependencies=[Depends(require_admin)])
def jobs_delete(job_id: str):
    jobs = _load_jobs()
    kept = [j for j in jobs if j.get("id") != job_id]
    if len(kept) == len(jobs):
        raise HTTPException(404, "job not found")
    _save_jobs(kept)
    return {"ok": True}


# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Terror Fibercraft admin API bridge")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--external", action="store_true", help="bind 0.0.0.0")
    args = p.parse_args()
    if args.external:
        args.host = "0.0.0.0"
    print(f"Terror Fibercraft admin API on http://{args.host}:{args.port}",
          file=sys.stderr)
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()