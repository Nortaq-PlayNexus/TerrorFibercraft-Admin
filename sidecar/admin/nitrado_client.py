#!/usr/bin/env python3
"""
nitrado_client.py — Client for the Nitrado REST API (v1).

Manages ARK ASE CrossPlay servers rented on Nitrado: list services, per-server
status, lifecycle (restart/stop/start), config get/push, backups, mods,
whitelist and logs. No third-party deps (uses urllib).

Endpoints loosely follow Nitrado's documented REST API (api.nitrado.net/v1 ...).
Paths are validated defensively: Nitrado occasionally shifts versioning, so if a
route returns 404/400 the error is surfaced with the server's message so you can
verify the exact route in the Nitrado developer portal.

Auth: Bearer token from env NITRADO_TOKEN, or config via config.load_config().

Endpoints used:
  GET  /services
  GET  /services/{service_id}/gameservers/{gs_id}
  POST /services/{service_id}/gameservers/{gs_id}/restart   (form: message)
  POST /services/{service_id}/gameservers/{gs_id}/stop
  POST /services/{service_id}/gameservers/{gs_id}/start
  GET  /services/{service_id}/gameservers/{gs_id}/settings
  POST /services/{service_id}/gameservers/{gs_id}/settings   (form: settings[game.ini], settings[gameusersettings.ini], ...)
  GET  /services/{service_id}/gameservers/{gs_id}/backups
  POST /services/{service_id}/gameservers/{gs_id}/backups/{backup_id}/restore
  GET  /services/{service_id}/gameservers/{gs_id}/logs
  GET  /services/{service_id}/gameservers/{gs_id}/mods
  GET  /services/{service_id}/gameservers/{gs_id}/mods/{mod_id}/status  (enabled/disabled/installed)
  PUT  /services/{service_id}/gameservers/{gs_id}/mods/{mod_id}/enabled  (install)
  PUT  /services/{service_id}/gameservers/{gs_id}/mods/{mod_id}/disabled (uninstall)
  GET  /services/{service_id}/gameservers/{gs_id}/whitelist
  POST /services/{service_id}/gameservers/{gs_id}/whitelist

Precise backup/mod/whitelist response shapes vary by game type; every method
returns the parsed JSON body so you can read the live shape once in production.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

API_BASE = "https://api.nitrado.net"
RETRYABLE = {429, 500, 502, 503, 504}


def _as_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class NitradoError(Exception):
    """Raised for HTTP / network / malformed-response errors from Nitrado."""


@dataclass
class ServerInfo:
    """A flattened, human-friendly view of a Nitrado gameserver for CLI/UI use."""

    service_id: int = 0
    id: int = 0
    name: str = ""
    game: str = ""
    status: str = "unknown"
    ip: str = ""
    port: str = ""
    players_online: int = 0
    players_max: int = 0
    raw: dict = field(default_factory=dict)

    @property
    def online(self) -> bool:
        return self.status in ("started", "online", "running", "starting")


class NitradoClient:
    def __init__(self, token: str, base: str = API_BASE, timeout: int = 30,
                 max_retries: int = 3, retry_base: float = 1.0,
                 retry_max: float = 8.0):
        self.token = token
        self.base = base
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_base = retry_base
        self.retry_max = retry_max

    # ------------------------------------------------------------------ HTTP
    def _request(self, method: str, path: str, form: dict | None = None,
                 _attempt: int = 0) -> dict:
        url = self.base + path
        data = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if form is not None:
            data = urllib.parse.urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code in RETRYABLE and _attempt < self.max_retries:
                retry_after = _as_float(e.headers.get("Retry-After"))
                delay = retry_after or min(self.retry_base * (2 ** _attempt), self.retry_max)
                time.sleep(delay)
                return self._request(method, path, form, _attempt + 1)
            raise NitradoError(f"HTTP {e.code} on {method} {path}: {detail}")
        except urllib.error.URLError as e:
            if _attempt < self.max_retries:
                time.sleep(min(self.retry_base * (2 ** _attempt), self.retry_max))
                return self._request(method, path, form, _attempt + 1)
            raise NitradoError(f"Network error on {path}: {e}")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    def _service(self, server: dict) -> tuple[int, int]:
        return int(server["service_id"]), int(server["gameserver_id"])

    # ------------------------------------------------------- service discovery
    def list_services(self) -> list[dict]:
        r = self._request("GET", "/services")
        return (r.get("data") or {}).get("services") or r.get("services") or []

    def list_servers(self, use_cache: bool = True) -> list[ServerInfo]:
        """Return a flattened :class:`ServerInfo` for every Nitrado gameserver.

        ``use_cache`` is accepted for API compatibility (a future callers may
        pass to avoid repeated fetches); this simple client always fetches.
        """
        out: list[ServerInfo] = []
        for service in self.list_services():
            sid = service.get("id")
            for gs in (service.get("gameservers") or []):
                info = ServerInfo(service_id=int(sid or 0))
                p = gs.get("players") or {}
                info.id = int(gs.get("id") or gs.get("gameserver_id") or 0)
                info.name = gs.get("name") or gs.get("comment") or f"gs-{info.id}"
                info.game = service.get("game") or gs.get("game") or ""
                info.status = gs.get("status") or gs.get("state") or "unknown"
                info.ip = gs.get("ip") or ""
                info.port = str(gs.get("port") or gs.get("query_port") or "")
                info.players_online = int(p.get("online") or gs.get("players_online") or 0)
                info.players_max = int(p.get("max") or gs.get("max_players") or 0)
                info.raw = gs
                out.append(info)
        return out

    def gameserver(self, service_id: int | str, gs_id: int | str) -> dict:
        r = self._request("GET", f"/services/{service_id}/gameservers/{gs_id}")
        return (r.get("data") or {}).get("gameserver") or r

    # ----------------------------------------------------------- lifecycle
    def restart(self, service_id, gs_id, message: str = "Admin restart") -> dict:
        return self._request(
            "POST", f"/services/{service_id}/gameservers/{gs_id}/restart",
            {"message": message},
        )

    def stop(self, service_id, gs_id) -> dict:
        return self._request("POST", f"/services/{service_id}/gameservers/{gs_id}/stop")

    def start(self, service_id, gs_id) -> dict:
        return self._request("POST", f"/services/{service_id}/gameservers/{gs_id}/start")

    # ------------------------------------------------------------- settings
    def get_settings(self, service_id, gs_id) -> dict:
        return self._request(
            "GET", f"/services/{service_id}/gameservers/{gs_id}/settings"
        )

    def update_config(
        self,
        service_id,
        gs_id,
        game_ini: str | None = None,
        gameusersettings_ini: str | None = None,
    ) -> dict:
        """Push config file contents as form fields.

        Field keys follow Nitrado's settings schema: settings[game.ini] and
        settings[gameusersettings.ini]. If Nitrado rejects these, check the
        exact field names in the Nitrado API docs for the ASE CrossPlay build.
        """
        form = {}
        if game_ini is not None:
            form["settings[game.ini]"] = game_ini
        if gameusersettings_ini is not None:
            form["settings[gameusersettings.ini]"] = gameusersettings_ini
        if not form:
            raise NitradoError("No config provided to update_config")
        r = self._request(
            "POST", f"/services/{service_id}/gameservers/{gs_id}/settings", form
        )
        # Nitrado returns {'data': {'settings': {...}}} on success; normalise.
        return (r.get("data") or {}).get("settings") or r

    # ------------------------------------------------------------- backups
    def list_backups(self, service_id, gs_id) -> list[dict]:
        r = self._request(
            "GET", f"/services/{service_id}/gameservers/{gs_id}/backups"
        )
        return (r.get("data") or {}).get("backups") or r.get("backups") or []

    def restore_backup(self, service_id, gs_id, backup_id) -> dict:
        return self._request(
            "POST",
            f"/services/{service_id}/gameservers/{gs_id}/backups/{backup_id}/restore",
        )

    # ---------------------------------------------------------------- mods
    def list_mods(self, service_id, gs_id) -> list[dict]:
        r = self._request(
            "GET", f"/services/{service_id}/gameservers/{gs_id}/mods"
        )
        return (r.get("data") or {}).get("mods") or r.get("mods") or []

    def install_mod(self, service_id, gs_id, mod_id) -> dict:
        return self._request(
            "PUT", f"/services/{service_id}/gameservers/{gs_id}/mods/{mod_id}/enabled"
        )

    def uninstall_mod(self, service_id, gs_id, mod_id) -> dict:
        return self._request(
            "PUT", f"/services/{service_id}/gameservers/{gs_id}/mods/{mod_id}/disabled"
        )

    # --------------------------------------------------------- whitelist
    def list_whitelist(self, service_id, gs_id) -> list[dict]:
        r = self._request(
            "GET", f"/services/{service_id}/gameservers/{gs_id}/whitelist"
        )
        return (r.get("data") or {}).get("whitelist") or r.get("whitelist") or []

    def add_whitelist(self, service_id, gs_id, target: str, comment: str = "") -> dict:
        form = {"target": target}
        if comment:
            form["comment"] = comment
        return self._request(
            "POST", f"/services/{service_id}/gameservers/{gs_id}/whitelist", form
        )

    # --------------------------------------------------------------- logs
    def get_logs(self, service_id, gs_id, limit: int = 50, offset: int = 0) -> dict:
        qs = urllib.parse.urlencode({"limit": limit, "offset": offset})
        return self._request(
            "GET",
            f"/services/{service_id}/gameservers/{gs_id}/logs?{qs}",
        )

    # ------------------------------------------------- server-status helper
    def server_status(self, server: dict) -> dict:
        """Convenience: fetch a gameserver by the config 'servers' entry shape."""
        sid, gid = self._service(server)
        gs = self.gameserver(sid, gid)
        return {
            "service_id": sid,
            "gameserver_id": gid,
            "status": gs.get("status") or gs.get("state") or "unknown",
            "players": (gs.get("players") or {}).get("online") or gs.get("players_online") or 0,
            "raw": gs,
        }

    def wait_for_status(self, service_id: int | str, gs_id: int | str,
                        targets: str | list[str],
                        timeout: float = 600.0, poll: float = 15.0) -> ServerInfo:
        """Poll until the gameserver reaches one of `targets` or `timeout` passes.

        Useful for restart/start workflows (issue restart, then wait for
        'started'). Raises NitradoError with the last seen state on timeout.
        """
        if isinstance(targets, str):
            targets = [targets]
        deadline = time.time() + timeout
        last: ServerInfo | None = None
        while time.time() < deadline:
            gs = self.gameserver(service_id, gs_id)
            last = ServerInfo(
                service_id=int(service_id),
                id=int(gs_id),
                status=gs.get("status") or gs.get("state") or "unknown",
                ip=gs.get("ip") or "",
                port=str(gs.get("port") or ""),
            )
            if last.status in targets:
                return last
            time.sleep(poll)
        raise NitradoError(
            f"timed out after {timeout:.0f}s waiting for {targets}; "
            f"last saw '{last.status if last else '?'}'")


def _from_env_or_config():
    """Return (client, cfg) resolving the token via env first, then config."""
    from config import load_config

    cfg = load_config()
    token = os.environ.get("NITRADO_TOKEN") or cfg.get("nitrado_token")
    if not token:
        raise NitradoError(
            "NITRADO_TOKEN not set (env) nor present in config.json"
        )
    return NitradoClient(token), cfg


if __name__ == "__main__":
    import sys

    tok = os.environ.get("NITRADO_TOKEN")
    if not tok:
        # Fall back to config file (also expands ${NITRADO_TOKEN} from env).
        try:
            client, _ = _from_env_or_config()
        except NitradoError as e:
            print(f"ERR: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        client = NitradoClient(tok)
    try:
        services = client.list_services()
        if not services:
            print("No services returned. Verify token + API scope.")
        for s in services:
            print(s.get("id"), s.get("type"), s.get("game"))
    except NitradoError as e:
        print(f"ERR: {e}", file=sys.stderr)
        sys.exit(1)
