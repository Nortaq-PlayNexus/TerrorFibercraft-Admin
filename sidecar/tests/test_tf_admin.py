import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "admin"))

import tf_admin  # noqa: E402


def _valid_cfg():
    return {
        "nitrado_token": "${NITRADO_TOKEN}",
        "servers": {"island": {
            "service_id": 1, "gameserver_id": 2,
            "rcon_host": "127.0.0.1", "rcon_port": 27020,
            "rcon_password": "${RCON_PASSWORD}",
        }},
    }


def test_load_config_resolves_env_placeholders(tmp_path, monkeypatch):
    monkeypatch.setenv("NITRADO_TOKEN", "tok123")
    monkeypatch.setenv("RCON_PASSWORD", "hunter2")
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps(_valid_cfg()))
    cfg = tf_admin.load_config(str(cfg_file))
    assert cfg["nitrado_token"] == "tok123"
    assert cfg["servers"]["island"]["rcon_password"] == "hunter2"


def test_load_config_invalid_structure_returns_error(tmp_path, monkeypatch):
    # shared loader validates structure; wire the error through without raising
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"discord_token": "${DISCORD_TOKEN}"}))
    cfg = tf_admin.load_config(str(cfg_file))
    assert "_config_error" in cfg


def test_load_config_invalid_json_returns_error(tmp_path):
    f = tmp_path / "config.json"
    f.write_text("{ this is not valid json")
    cfg = tf_admin.load_config(str(f))
    assert "_config_error" in cfg


def test_load_config_missing_path_falls_back_to_search(tmp_path):
    # config.py ignores a nonexistent explicit path and falls back to the
    # repo's config.json/config.example.json (which always exist in this repo).
    cfg = tf_admin.load_config(str(tmp_path / "nope.json"))
    assert "_config_error" not in cfg


def test_bootstrap_writes_config_from_example(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NITRADO_TOKEN", "tok789")
    monkeypatch.setattr(tf_admin, "HERE", str(tmp_path))
    (tmp_path / "config.example.json").write_text(json.dumps({
        "nitrado_token": "${NITRADO_TOKEN}",
        "discord_token": "${DISCORD_TOKEN}",
        "admin_role": "Admin",
    }))
    dst = tmp_path / "config.json"
    rc = tf_admin.cmd_bootstrap([], json_out=True)
    out = json.loads(capsys.readouterr().out)
    assert rc == 2  # DISCORD_TOKEN unresolved
    assert out["resolved"] == ["NITRADO_TOKEN"]
    assert out["missing"] == ["DISCORD_TOKEN"]
    written = json.loads(dst.read_text())
    assert written["nitrado_token"] == "tok789"
    assert written["discord_token"] == "${DISCORD_TOKEN}"


def test_bootstrap_refuses_overwrite_without_force(tmp_path, capsys):
    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(tf_admin, "HERE", str(tmp_path))
    (tmp_path / "config.example.json").write_text("{}")
    (tmp_path / "config.json").write_text("{}")
    rc = tf_admin.cmd_bootstrap([], json_out=False)
    assert rc == 1
    assert "exists" in capsys.readouterr().err
    monkeypatch.undo()


def test_bootstrap_force_overwrites(tmp_path, monkeypatch):
    monkeypatch.setattr(tf_admin, "HERE", str(tmp_path))
    (tmp_path / "config.example.json").write_text(json.dumps({"a": 1}))
    (tmp_path / "config.json").write_text(json.dumps({"old": True}))
    rc = tf_admin.cmd_bootstrap(["--force"], json_out=True)
    assert rc == 0
    assert json.loads((tmp_path / "config.json").read_text()) == {"a": 1}


def test_doctor_json_shape(capsys):
    rc = tf_admin.cmd_doctor([], json_out=True)
    data = json.loads(capsys.readouterr().out)
    assert "checks" in data and all("name" in c and "ok" in c for c in data["checks"])
    assert rc in (0, 1)


def test_cluster_prints_json(capsys):
    rc = tf_admin.cmd_cluster([], json_out=False)
    out = capsys.readouterr().out
    assert rc == 0
    parsed = json.loads(out)
    assert parsed.get("name") or parsed.get("cluster")