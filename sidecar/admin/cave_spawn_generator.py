#!/usr/bin/env python3
"""
Terror Fibercraft 1000x — Admin Custom-Cave / Sculpt Generator  (v2)
=============================================================
Generates ordered, line-by-line `cheat spawnactor` commands that drop floating
terminal structures (TributeTerminal / WaterVein / City Terminal / Loadout
Mannequin) to sculpt admin-only terrain: cave walls, sealed base shells,
floating platforms, canyon chokes, cliff-hollow rat holes.

This is ADMIN terrain only. Players using these to box bases or block paths
is a bannable exploit (see 04_CLUSTER_DESIGN/rules-code-of-conduct.md).

spawnactor syntax (relative to the admin who runs it):
  cheat spawnactor "Blueprint'...'" <SpawnDistance> <YOffset> <ZOffset>
  SpawnDistance = cm FORWARD of the player (depth into the wall)
  YOffset      = cm RIGHT of the player (negative = left)
  ZOffset      = cm UP from the player (negative = down)

Because every command is relative to where you stand, a single batch drops a
clean plane in front of you. For a BOX, run each labelled wall while facing
that side. Commands are emitted bottom->top, left->right so a straight run
places a perfect wall.

USAGE
  python cave-spawn-generator.py convert --map ragnarok --lat 30.2 --lon 32.8
  python cave-spawn-generator.py gen --mode wall --cols 7 --rows 5 --hole dino
  python cave-spawn-generator.py gen --preset dino_gate
  python cave-spawn-generator.py gen --mode box --cols 9 --rows 6 --depth 9 \
        --hole behemoth --floor --ceiling --blueprint watervein --json
  python cave-spawn-generator.py batch --file spots.json > walls.txt
  python cave-spawn-generator.py apply --host 1.2.3.4 --port 27020 \
        --password SECRET --file walls.txt
  python cave-spawn-generator.py list
"""

import argparse
import json
import os
import sys

# --------------------------------------------------------------------------
# Blueprint paths (verified on ASE/ASA). The first two are confirmed; the
# others are included for completeness with a gfi/summon fallback noted.
# --------------------------------------------------------------------------
BLUEPRINTS = {
    "tribute_red":   "Blueprint'/Game/PrimalEarth/Structures/TributeTerminal_Red.TributeTerminal_Red'",
    "tribute_blue":  "Blueprint'/Game/PrimalEarth/Structures/TributeTerminal_Blue.TributeTerminal_Blue'",
    "tribute_green": "Blueprint'/Game/PrimalEarth/Structures/TributeTerminal_Green.TributeTerminal_Green'",
    "watervein":     "Blueprint'/Game/ScorchedEarth/Structures/WaterWell/WaterVein_Base_BP.WaterVein_Base_BP'",
    # Fallbacks if the exact Blueprint path differs on your build:
    #   City Terminal : cheat summon primalstructure_cityterminal_bp_c
    #   Loadout Mannequin : cheat gfi LoadoutDummy 1 0 0
    #   Water Well    : cheat gfi WaterWell 1 0 0
    "city_terminal": "Blueprint'/Game/PrimalEarth/Structures/CityTerminal.CityTerminal'",
    "loadout_mannequin": "Blueprint'/Game/PrimalEarth/Structures/LoadoutDummy.LoadoutDummy'",
}

# --------------------------------------------------------------------------
# Entrance / hole presets. Sizes in cm using 400cm = 1 wall unit.
#   crouch  = player-only (1x1-2)      stego  = small dino
#   dino    = dino-gateway sized        behemoth= behemoth-gateway sized
# --------------------------------------------------------------------------
HOLE_PRESETS = {
    "none":    (0, 0),
    "crouch":  (100, 200),
    "stego":   (400, 600),
    "dino":    (800, 1600),
    "behemoth": (2800, 4800),
}

# Named shortcuts: --preset NAME expands to these gen options.
PRESETS = {
    "crouch_wall":  dict(mode="wall", cols=5, rows=4, hole="crouch"),
    "stego_wall":   dict(mode="wall", cols=7, rows=5, hole="stego"),
    "dino_gate":    dict(mode="wall", cols=9, rows=6, hole="dino"),
    "behemoth_gate":dict(mode="wall", cols=11, rows=7, hole="behemoth"),
    "plateau_box":  dict(mode="box", cols=9, rows=6, depth=9, hole="dino", floor=True),
    "ruin_plug":    dict(mode="wall", cols=3, rows=3, hole="crouch"),
    "platform":     dict(mode="platform", depth=8, cols=8),
}

# --------------------------------------------------------------------------
# XY(lat,lon) -> UE coordinates (SetPlayerPos X Y Z) per ark.fandom transform.
# (shift_lat, shift_lon, mult_lat, mult_lon, approx?)
# --------------------------------------------------------------------------
MAP_TRANSFORMS = {
    "island":      (50, 50, 8000, 8000, False),
    "scorched":    (50, 50, 8000, 8000, False),
    "center":      (30.34, 55.10, 9584, 9600, False),
    "ragnarok":    (50, 50, 13100, 13100, False),
    "aberration":  (50, 50, 8000, 8000, False),
    "extinction":  (50, 50, 8000, 8000, False),
    "valguero":    (50, 50, 8160, 8160, False),
    "genesis1":    (50, 50, 10500, 10500, False),
    "crystalisles":(48.5, 48.5, 8500, 8500, True),
    "genesis2":    (49.655, 49.655, 14500, 14500, True),
    "lostisland":  (51.634, 49.02, 15300, 15300, False),
    "fjordur":     (50, 50, 8000, 8000, True),
    "astraeos":    (50, 50, 15000, 15000, True),  # ASA-only map; coords reference only
}


def blueprint_arg(name):
    if name in BLUEPRINTS:
        return BLUEPRINTS[name]
    if name.startswith("Blueprint'"):
        return name
    raise SystemExit(f"Unknown blueprint '{name}'. Choices: {', '.join(BLUEPRINTS)}")


def hole_cells(preset, spacing):
    w, h = HOLE_PRESETS[preset]
    if w <= 0 or h <= 0:
        return (0, 0, 0, 0)
    cols = max(1, round(w / spacing))
    rows = max(1, round(h / spacing))
    return (cols, rows)


def emit_wall(bp, cols, rows, spacing, forward, z_start, hole, label):
    out = []
    if label:
        out.append(f"# === {label} (stand so this wall is in FRONT of you) ===")
    hc, hr = hole_cells(hole, spacing) if hole != "none" else (0, 0)
    hc0 = (cols - hc) // 2
    hr0 = (rows - hr) // 2
    for r in range(rows):
        for c in range(cols):
            if hole != "none" and (hc0 <= c < hc0 + hc) and (hr0 <= r < hr0 + hr):
                continue
            y = (c - (cols - 1) / 2.0) * spacing
            z = z_start + r * spacing
            out.append(f'cheat spawnactor "{bp}" {forward} {y:.0f} {z:.0f}')
    out.append("")
    return out


def emit_platform(bp, depth, cols, spacing, forward, z, label):
    out = []
    if label:
        out.append(f"# === {label} (flat grid in front of you) ===")
    for dr in range(depth):
        for c in range(cols):
            y = (c - (cols - 1) / 2.0) * spacing
            d = forward + dr * spacing
            out.append(f'cheat spawnactor "{bp}" {d:.0f} {y:.0f} {z:.0f}')
    out.append("")
    return out


def build_commands(args):
    """Return (lines, meta) for a single gen invocation."""
    bp = blueprint_arg(args.blueprint)
    sp = args.spacing
    lines = []
    meta = dict(mode=args.mode, blueprint=args.blueprint, spacing=sp)
    if args.mode == "wall":
        lines += emit_wall(bp, args.cols, args.rows, sp, args.forward,
                           args.zstart, args.hole, "WALL")
        meta.update(cols=args.cols, rows=args.rows, hole=args.hole)
    elif args.mode in ("floor", "platform"):
        lines += emit_platform(bp, args.depth, args.cols, sp, args.forward,
                               args.zstart, "PLATFORM/FLOOR")
        meta.update(depth=args.depth, cols=args.cols)
    elif args.mode == "box":
        lines.append("# BOX SHELL — run each wall while facing that side.")
        lines.append("# 1) Face NORTH, run wall N. 2) Face EAST, run wall E.")
        lines.append("# 3) Face SOUTH, run wall S. 4) Face WEST, run wall W.")
        for side in ("NORTH (in front)", "EAST (in front)", "SOUTH (in front)", "WEST (in front)"):
            lines += emit_wall(bp, args.cols, args.rows, sp, args.forward,
                               args.zstart, args.hole, f"BOX WALL — {side}")
        if args.floor:
            lines += emit_platform(bp, args.depth, args.cols, sp, args.forward,
                                    args.zstart, "BOX FLOOR (under you)")
        if args.ceiling:
            lines += emit_platform(bp, args.depth, args.cols, sp, args.forward,
                                    args.zstart + args.rows * sp, "BOX CEILING")
        meta.update(cols=args.cols, rows=args.rows, hole=args.hole,
                    depth=args.depth, floor=args.floor, ceiling=args.ceiling)
    else:
        raise SystemExit("mode must be wall|floor|platform|box")
    return lines, meta


def cmd_gen(args):
    if args.preset:
        p = PRESETS[args.preset]
        for k, v in p.items():
            setattr(args, k, v)
    if not args.mode:
        raise SystemExit("ERROR: --mode is required (or use --preset NAME)")
    lines, meta = build_commands(args)
    if args.json:
        print(json.dumps({"meta": meta, "commands": lines}, indent=2))
    else:
        text = "\n".join(lines)
        if args.out:
            with open(args.out, "w") as f:
                f.write(text + "\n")
            print(f"Wrote {len(lines)} lines to {args.out}")
        else:
            print(text)


def cmd_convert(args):
    if args.map not in MAP_TRANSFORMS:
        raise SystemExit("map must be one of: " + ", ".join(MAP_TRANSFORMS))
    slat, slon, mlat, mlon, approx = MAP_TRANSFORMS[args.map]
    x = (args.lon - slon) * mlon
    y = (args.lat - slat) * mlat
    z = args.z if args.z is not None else 0
    flag = "  # APPROXIMATE — verify with arkids.net for this map" if approx else ""
    print(f"# {args.map}: Lat {args.lat}, Lon {args.lon}{flag}")
    print(f"cheat setplayerpos {x:.0f} {y:.0f} {z:.0f}")


def cmd_list(args):
    print("BLUEPRINTS:")
    for k in BLUEPRINTS:
        print(f"  {k}")
    print("\nPRESETS:")
    for k, v in PRESETS.items():
        print(f"  {k}: {v}")
    print("\nMAPS (convert):")
    for k, v in MAP_TRANSFORMS.items():
        print(f"  {k} (approx={v[4]})")


def cmd_batch(args):
    with open(args.file) as f:
        spots = json.load(f)
    if isinstance(spots, dict):
        spots = [spots]
    for i, spot in enumerate(spots):
        m = spot.get("map")
        lat = spot.get("lat")
        lon = spot.get("lon")
        if m and lat is not None and lon is not None:
            slat, slon, mlat, mlon, approx = MAP_TRANSFORMS[m]
            x = (lon - slon) * mlon
            y = (lat - slat) * mlat
            print(f"# --- Spot {i+1}: {spot.get('name', m)} ({lat},{lon}) ---")
            print(f"cheat setplayerpos {x:.0f} {y:.0f} 0")
        # build the wall/platform/box for this spot
        sub = argparse.Namespace(
            blueprint=spot.get("blueprint", "tribute_red"),
            mode=spot.get("mode", "wall"),
            cols=spot.get("cols", 7), rows=spot.get("rows", 5),
            depth=spot.get("depth", 7), spacing=spot.get("spacing", 400),
            forward=spot.get("forward", 400), zstart=spot.get("zstart", 0),
            hole=spot.get("hole", "none"),
            floor=spot.get("floor", False), ceiling=spot.get("ceiling", False),
        )
        lines, _ = build_commands(sub)
        print("\n".join(lines))


def cmd_apply(args):
    # import the RCON client from ../scripts
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "scripts"))
    import ark_rcon
    cmds = []
    src = args.file if args.file else "-"
    if src == "-":
        cmds = [l.rstrip("\n") for l in sys.stdin]
    else:
        with open(src) as f:
            cmds = [l.rstrip("\n") for l in f]
    cmds = [c for c in cmds if c.strip().startswith("cheat ")]
    if not cmds:
        raise SystemExit("No 'cheat' commands found to apply.")
    with ark_rcon.RconClient(args.host, args.port, args.password) as r:
        for c in cmds:
            try:
                r.send(c)
            except ark_rcon.RconError as e:
                print(f"ERR: {c[:60]}... -> {e}", file=sys.stderr)
    print(f"Applied {len(cmds)} commands to {args.host}:{args.port}")


def build_parser():
    p = argparse.ArgumentParser(description="Terror Fibercraft 1000x admin sculpt generator (v2)")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen", help="generate spawnactor commands")
    g.add_argument("--blueprint", default="tribute_red",
                   help="key from BLUEPRINTS or a raw Blueprint'...' path")
    g.add_argument("--mode", default=None, choices=["wall", "floor", "platform", "box"])
    g.add_argument("--cols", type=int, default=7, help="width (cells)")
    g.add_argument("--rows", type=int, default=5, help="height (cells, wall/box)")
    g.add_argument("--depth", type=int, default=7, help="forward depth (cells, floor/box)")
    g.add_argument("--spacing", type=int, default=400, help="cm per cell (400 = 1 wall)")
    g.add_argument("--forward", type=int, default=400, help="cm in front of player")
    g.add_argument("--zstart", type=int, default=0, help="base Z offset (cm)")
    g.add_argument("--hole", default="none",
                   choices=["none", "crouch", "stego", "dino", "behemoth"])
    g.add_argument("--floor", action="store_true", help="(box) also build floor")
    g.add_argument("--ceiling", action="store_true", help="(box) also build ceiling")
    g.add_argument("--preset", default=None, choices=list(PRESETS),
                   help="named shortcut; overrides cols/rows/mode/hole")
    g.add_argument("--json", action="store_true", help="emit JSON instead of text")
    g.add_argument("--out", default=None, help="write to file instead of stdout")
    g.set_defaults(func=cmd_gen)

    c = sub.add_parser("convert", help="lat/lon -> setplayerpos")
    c.add_argument("--map", required=True)
    c.add_argument("--lat", type=float, required=True)
    c.add_argument("--lon", type=float, required=True)
    c.add_argument("--z", type=float, default=None, help="altitude (cm); default 0")
    c.set_defaults(func=cmd_convert)

    l = sub.add_parser("list", help="list blueprints, presets, maps")
    l.set_defaults(func=cmd_list)

    b = sub.add_parser("batch", help="generate many spots from a JSON file")
    b.add_argument("--file", required=True, help="JSON: dict or list of spot objects")
    b.set_defaults(func=cmd_batch)

    a = sub.add_parser("apply", help="send commands to a server via RCON")
    a.add_argument("--host", required=True)
    a.add_argument("--port", type=int, required=True)
    a.add_argument("--password", required=True)
    a.add_argument("--file", default=None, help="file of commands (default stdin)")
    a.set_defaults(func=cmd_apply)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
