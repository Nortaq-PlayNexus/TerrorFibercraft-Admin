import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "admin"))

from nitrado_client import NitradoClient, NitradoError  # noqa: E402


class _FakeResp:
    def __init__(self, body: dict, status: int = 200):
        self.body = body
        self.status = status
        self.messages = []


class _FakeNitrado(NitradoClient):
    """Test double that intercepts _request and returns canned responses."""

    def __init__(self, routes: dict):
        super().__init__("test-token")
        self.routes = routes
        self.calls = []

    def _request(self, method, path, form=None):
        self.calls.append((method, path, form))
        key = (method, path)
        if key in self.routes:
            return self.routes[key]
        raise NitradoError(f"HTTP 404 on {method} {path}: no test route")


def _services_two():
    return {
        "data": {
            "services": [
                {
                    "id": 10,
                    "type": "game",
                    "game": "arkse",
                    "gameservers": [
                        {
                            "id": 20,
                            "name": "TFC | Island",
                            "status": "started",
                            "ip": "1.2.3.4",
                            "port": 7777,
                            "players": {"online": 3, "max": 70},
                        }
                    ],
                }
            ]
        }
    }


def test_list_servers_flattens_service():
    n = _FakeNitrado({("GET", "/services"): _services_two()})
    servers = n.list_servers()
    assert len(servers) == 1
    s = servers[0]
    assert s.name == "TFC | Island"
    assert s.service_id == 10
    assert s.id == 20
    assert s.status == "started"
    assert s.online is True
    assert s.players_online == 3
    assert s.players_max == 70
    assert s.ip == "1.2.3.4"
    assert s.port == "7777"


def test_server_info_online_false_for_stopped():
    routes = {
        ("GET", "/services"): {
            "data": {"services": [{"id": 1, "gameservers": [{"id": 2, "status": "stopped"}]}]}
        }
    }
    n = _FakeNitrado(routes)
    assert n.list_servers()[0].online is False


def test_update_config_sends_form_fields():
    n = _FakeNitrado({
        ("POST", "/services/1/gameservers/2/settings"): {
            "data": {"settings": {"game.ini": "x"}}
        }
    })
    out = n.update_config(1, 2, game_ini="[Unit]\nx=1",
                          gameusersettings_ini="[ServerSettings]\nMaxPlayers=70")
    assert out.get("game.ini") == "x"
    method, path, form = n.calls[0]
    assert method == "POST"
    assert path.endswith("/settings")
    assert "settings[game.ini]" in form
    assert "settings[gameusersettings.ini]" in form


def test_update_config_requires_some_config():
    import pytest
    n = _FakeNitrado({})
    with pytest.raises(NitradoError, match="No config"):
        n.update_config(1, 2)


def test_backup_restore_path():
    n = _FakeNitrado({
        ("POST", "/services/1/gameservers/2/backups/55/restore"): {"status": "ok"}
    })
    assert n.restore_backup(1, 2, 55)["status"] == "ok"


def test_mod_enable_disable():
    n = _FakeNitrado({
        ("PUT", "/services/1/gameservers/2/mods/900/enabled"): {"status": "ok"},
        ("PUT", "/services/1/gameservers/2/mods/900/disabled"): {"status": "ok"},
    })
    assert n.install_mod(1, 2, 900)["status"] == "ok"
    assert n.uninstall_mod(1, 2, 900)["status"] == "ok"


def test_server_status_helper():
    n = _FakeNitrado({
        ("GET", "/services/10/gameservers/20"):
            {"data": {"gameserver": {"status": "started", "players": {"online": 4}}}}
    })
    info = n.server_status({"service_id": 10, "gameserver_id": 20})
    assert info["status"] == "started"
    assert info["players"] == 4


def test_whitelist_add_sends_target():
    n = _FakeNitrado({
        ("POST", "/services/1/gameservers/2/whitelist"): {"status": "ok"}
    })
    assert n.add_whitelist(1, 2, "76561198000000000", "friend")["status"] == "ok"
    _, _, form = n.calls[0]
    assert form["target"] == "76561198000000000"
    assert form["comment"] == "friend"


def test_http_error_raises_nitrado_error():
    # A route not in the fake map raises NitradoError (simulating 404/400).
    import pytest
    n = _FakeNitrado({})
    with pytest.raises(NitradoError, match="404"):
        n.gameserver(1, 2)
