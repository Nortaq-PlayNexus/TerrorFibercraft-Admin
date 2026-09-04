import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "admin"))

import config  # noqa: E402


def _write(tmp_path, data: dict):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_resolve_placeholders_simple(monkeypatch):
    monkeypatch.setenv("NITRADO_TOKEN", "abc123")
    assert config.resolve_placeholders("${NITRADO_TOKEN}") == "abc123"


def test_resolve_placeholders_missing_becomes_empty(monkeypatch):
    monkeypatch.delenv("NO_SUCH_VAR_XYZ", raising=False)
    assert config.resolve_placeholders("${NO_SUCH_VAR_XYZ}") == ""


def test_resolve_placeholders_non_string_passthrough():
    assert config.resolve_placeholders(42) == 42
    assert config.resolve_placeholders(None) is None


def test_resolve_tree_recursive(monkeypatch):
    monkeypatch.setenv("RCON_PASSWORD", "pw")
    node = {
        "servers": {"theisland": {"rcon_password": "${RCON_PASSWORD}"}},
        "token": "${NITRADO_TOKEN}",
        "n": 3,
    }
    out = config._resolve_tree(node)
    assert out["servers"]["theisland"]["rcon_password"] == "pw"
    assert out["token"] == ""  # NITRADO_TOKEN unset
    assert out["n"] == 3


def _valid_cfg():
    return {
        "nitrado_token": "n",
        "discord_token": "d",
        "servers": {
            "theisland": {
                "service_id": 1, "gameserver_id": 2,
                "rcon_host": "127.0.0.1", "rcon_port": 27020,
                "rcon_password": "p",
            }
        },
    }


def test_load_config_expands_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NITRADO_TOKEN", "from_env")
    monkeypatch.setenv("DISCORD_TOKEN", "d_env")
    monkeypatch.setenv("RCON_PASSWORD", "r_env")
    cfg = _valid_cfg()
    cfg["nitrado_token"] = "${NITRADO_TOKEN}"
    cfg["discord_token"] = "${DISCORD_TOKEN}"
    cfg["servers"]["theisland"]["rcon_password"] = "${RCON_PASSWORD}"
    path = _write(tmp_path, cfg)
    loaded = config.load_config(path=path)
    assert loaded["nitrado_token"] == "from_env"
    assert loaded["discord_token"] == "d_env"
    assert loaded["servers"]["theisland"]["rcon_password"] == "r_env"
    assert loaded["_unresolved"] == []


def test_load_config_unresolved_reported(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.delenv("NITRADO_TOKEN", raising=False)
    monkeypatch.delenv("RCON_PASSWORD", raising=False)
    cfg = _valid_cfg()
    cfg["nitrado_token"] = "${NITRADO_TOKEN}"  # unresolved -> ""
    cfg.pop("discord_token")
    cfg["servers"]["theisland"]["rcon_password"] = "${RCON_PASSWORD}"  # unresolved -> ""
    path = _write(tmp_path, cfg)
    loaded = config.load_config(path=path)
    unresolved = {field for field, _ in loaded["_unresolved"]}
    assert "nitrado_token" in unresolved
    assert "servers[*].rcon_password" in unresolved


def test_validate_structure_requires_servers():
    import pytest
    try:
        config.validate_structure({})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "servers" in str(e)


def test_load_config_missing_file_falls_back_not_crash(tmp_path):
    # An explicitly-passed path that doesn't exist must NOT crash; it falls back
    # to the on-disk search path config (or empty defaults if none exists).
    loaded = config.load_config(path=os.path.join(str(tmp_path), "nope.json"))
    assert isinstance(loaded, dict)
    assert "_resolved_from" in loaded
    assert "servers" in loaded  # falls back to real config.json (or empty {})
