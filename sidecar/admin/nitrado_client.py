#!/usr/bin/env python3
"""
nitrado_client.py — Thin client for the Nitrado REST API (v1).
Manages ARK ASE CrossPlay servers rented on Nitrado: list, restart, stop/start,
and push Game.ini / GameUserSettings.ini content.

NO third-party deps (uses urllib). Requires a Nitrado API token
(generated in Nitrado account -> "API / Developer").

Endpoints follow Nitrado's documented REST API. If a path returns 404, verify the
exact route at the Nitrado developer portal — they occasionally adjust versioning.
This client is built for the CrossPlay (Xbox/Windows) ASE build specifically.

Env / config: see scripts/config.example.json
"""
import json
import urllib.request
import urllib.parse
import urllib.error

API_BASE = "https://api.nitrado.net"


class NitradoError(Exception):
    pass


class NitradoClient:
    def __init__(self, token: str, base: str = API_BASE):
        self.token = token
        self.base = base

    def _request(self, method: str, path: str, form: dict | None = None) -> dict:
        url = self.base + path
        data = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if form is not None:
            # Nitrado expects application/x-www-form-urlencoded
            data = urllib.parse.urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raise NitradoError(f"HTTP {e.code} on {method} {path}: {e.read().decode('utf-8','replace')}")
        except urllib.error.URLError as e:
            raise NitradoError(f"Network error on {path}: {e}")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    # ---- service discovery ----
    def list_services(self) -> list[dict]:
        r = self._request("GET", "/services")
        # shape: {"status":"success","data":{"services":[...]}}
        return (r.get("data") or {}).get("services") or r.get("services") or []

    def gameserver(self, service_id: int | str, gs_id: int | str) -> dict:
        r = self._request("GET", f"/services/{service_id}/gameservers/{gs_id}")
        return (r.get("data") or {}).get("gameserver") or r

    # ---- lifecycle actions ----
    def restart(self, service_id: int | str, gs_id: int | str, message: str = "Admin restart") -> dict:
        return self._request(
            "POST",
            f"/services/{service_id}/gameservers/{gs_id}/restart",
            {"message": message},
        )

    def stop(self, service_id: int | str, gs_id: int | str) -> dict:
        return self._request("POST", f"/services/{service_id}/gameservers/{gs_id}/stop")

    def start(self, service_id: int | str, gs_id: int | str) -> dict:
        return self._request("POST", f"/services/{service_id}/gameservers/{gs_id}/start")

    # ---- config push ----
    def get_settings(self, service_id: int | str, gs_id: int | str) -> dict:
        return self._request("GET", f"/services/{service_id}/gameservers/{gs_id}/settings")

    def update_config(
        self,
        service_id: int | str,
        gs_id: int | str,
        game_ini: str | None = None,
        gameusersettings_ini: str | None = None,
    ) -> dict:
        """Push config file contents. Field names follow Nitrado's settings schema.
        VERIFY the exact field keys against your Nitrado panel's API before relying on this."""
        form = {}
        if game_ini is not None:
            form["settings[game.ini]"] = game_ini
        if gameusersettings_ini is not None:
            form["settings[gameusersettings.ini]"] = gameusersettings_ini
        if not form:
            raise NitradoError("No config provided to update_config")
        return self._request(
            "POST",
            f"/services/{service_id}/gameservers/{gs_id}/settings",
            form,
        )


if __name__ == "__main__":
    import os
    tok = os.environ.get("NITRADO_TOKEN")
    if not tok:
        print("Set NITRADO_TOKEN to test. Example:")
        print("  NITRADO_TOKEN=xxxx py nitrado_client.py")
    else:
        c = NitradoClient(tok)
        for s in c.list_services():
            print(s.get("id"), s.get("type"), s.get("game"))
