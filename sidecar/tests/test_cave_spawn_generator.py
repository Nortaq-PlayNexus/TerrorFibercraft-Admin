import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "admin"))

from cave_spawn_generator import (  # noqa: E402
    HOLE_PRESETS,
    PRESETS,
    build_commands,
    cmd_convert,
    cmd_gen,
    cmd_list,
    blueprint_arg,
)

import pytest  # noqa: E402


def ns(**kw):
    base = dict(blueprint="tribute_red", mode="wall", cols=7, rows=5,
                depth=7, spacing=400, forward=400, zstart=0, hole="none",
                floor=False, ceiling=False)
    base.update(kw)
    return argparse.Namespace(**base)


def test_hole_preset_sizes():
    assert HOLE_PRESETS["crouch"] == (100, 200)
    assert HOLE_PRESETS["dino"] == (800, 1600)
    assert HOLE_PRESETS["behemoth"] == (2800, 4800)


def test_preset_catalog_covers_cookbook():
    for name in ("crouch_hole", "stego_hole", "dino_hole", "behemoth_hole",
                 "uw_seal", "uw_pocket", "canyon_choke", "cliff_hollow",
                 "ruin_plug", "ruin_fill", "plateau_box", "floating_island"):
        assert name in PRESETS, f"missing cookbook preset {name}"


def test_wall_emits_full_rectangle_no_hole():
    lines, meta = build_commands(ns(cols=3, rows=2))
    cmds = [l for l in lines if l.startswith("cheat spawnactor")]
    assert len(cmds) == 3 * 2


def test_dino_hole_removes_centered_cells():
    # dino hole = 800x1600cm @400 = 2 cols x 4 rows on a 9x6 wall -> 18 cmd lines
    lines, meta = build_commands(ns(cols=9, rows=6, hole="dino"))
    cmds = [l for l in lines if l.startswith("cheat spawnactor")]
    assert len(cmds) == 9 * 6 - 2 * 4


def test_wall_preset_counts():
    for name in ("crouch_hole", "stego_hole", "dino_hole", "behemoth_hole",
                 "canyon_choke", "cliff_hollow", "uw_seal", "uw_pocket"):
        p = PRESETS[name]
        a = ns(**{k: v for k, v in p.items() if k in (
            "cols", "rows", "spacing", "forward", "zstart", "floor", "ceiling")})
        a.mode = "wall"
        a.hole = p["hole"]
        lines, _ = build_commands(a)
        cmds = [l for l in lines if l.startswith("cheat spawnactor")]
        w, h = HOLE_PRESETS[p["hole"]]
        hc = max(1, round(w / 400))
        hr = max(1, round(h / 400))
        assert len(cmds) == p["cols"] * p["rows"] - hc * hr, name


def test_box_mode_builds_without_error():
    lines, meta = build_commands(ns(mode="box", cols=5, rows=4, depth=5,
                                    hole="dino", floor=True, ceiling=True))
    assert meta["mode"] == "box"
    assert len([l for l in lines if l.startswith("cheat spawnactor")]) > 0


def test_oversized_hole_rejected():
    with pytest.raises(SystemExit, match="hole"):
        build_commands(ns(cols=2, rows=2, hole="behemoth"))


def test_bad_mode_rejected():
    with pytest.raises(SystemExit):
        build_commands(ns(mode="diagonal"))


def test_convert_island_center_is_origin(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["gen", "convert", "--map", "island",
                                     "--lat", "50", "--lon", "50"])
    cmd_convert(argparse.Namespace(map="island", lat=50.0, lon=50.0, z=0))
    out = capsys.readouterr().out
    assert "cheat setplayerpos 0 0 0" in out


def test_convert_rejects_out_of_bounds():
    with pytest.raises(SystemExit, match="0..100"):
        cmd_convert(argparse.Namespace(map="island", lat=150.0, lon=50.0, z=0))
    with pytest.raises(SystemExit, match="0..100"):
        cmd_convert(argparse.Namespace(map="island", lat=50.0, lon=-5.0, z=0))


def test_convert_unknown_map_rejected():
    with pytest.raises(SystemExit, match="map must be one of"):
        cmd_convert(argparse.Namespace(map="nowhere", lat=50.0, lon=50.0, z=0))


def test_pipe_mode_gen_prepends_teleport(capsys):
    a = argparse.Namespace(preset=None, mode="wall", cols=3, rows=2,
                           blue="tribute_red", blueprint="tribute_red", depth=7,
                           spacing=400, forward=400, zstart=0, hole="none",
                           floor=False, ceiling=False, json=False, out=None,
                           map="island", lat=50.0, lon=50.0, z=0.0)
    cmd_gen(a)
    out = capsys.readouterr().out
    assert "cheat setplayerpos 0 0 0" in out


def test_gen_json_emits_meta(capsys):
    a = argparse.Namespace(preset="dino_hole", mode=None, cols=9, rows=6,
                           blue="tribute_red", blueprint="tribute_red", depth=7,
                           spacing=400, forward=400, zstart=0, hole="none",
                           floor=False, ceiling=False, json=True, out=None,
                           map=None, lat=None, lon=None, z=0.0)
    cmd_gen(a)
    payload = json.loads(capsys.readouterr().out)
    assert payload["meta"]["hole"] == "dino"
    assert payload["meta"]["cols"] == 9
    assert any(c.startswith("cheat spawnactor") for c in payload["commands"])


def test_list_json_is_machine_readable(capsys):
    cmd_list(argparse.Namespace(json=True))
    data = json.loads(capsys.readouterr().out)
    assert "blueprints" in data and "presets" in data and "maps" in data


def test_blueprint_arg_accepts_raw_path():
    assert blueprint_arg("Blueprint'/Test/X.X'") == "Blueprint'/Test/X.X'"


def test_blueprint_arg_rejects_unknown():
    with pytest.raises(SystemExit):
        blueprint_arg("nope")