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
  python cave-spawn-generator.py gen --preset uw_seal --map fjordur --lat 49.4 --lon 14.2
  python cave-spawn-generator.py demo --preset dino_gate       # ASCII wall preview
  python cave-spawn-generator.py batch --file spots.json > walls.txt
  python cave-spawn-generator.py apply --host 1.2.3.4 --port 27020 \
        --password SECRET --file walls.txt
  python cave-spawn-generator.py list
  python cave-spawn-generator.py list --json                    # machine-readable catalog
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
# Coverage mirrors spawn-command-cookbook.md so the cookbook == the CLI:
# holes (bare entrances), gates (full walls), sculpt recipes, and platforms.
PRESETS = {
    # bare entrances (small wall just around the hole)
    "crouch_hole":  dict(mode="wall", cols=5, rows=4, hole="crouch"),
    "stego_hole":   dict(mode="wall", cols=7, rows=5, hole="stego"),
    "dino_hole":    dict(mode="wall", cols=9, rows=6, hole="dino"),
    "behemoth_hole":dict(mode="wall", cols=9, rows=14, hole="behemoth"),
    # full seal walls (legacy aliases kept)
    "crouch_wall":  dict(mode="wall", cols=5, rows=4, hole="crouch"),
    "stego_wall":   dict(mode="wall", cols=7, rows=5, hole="stego"),
    "dino_gate":    dict(mode="wall", cols=9, rows=6, hole="dino"),
    "behemoth_gate":dict(mode="wall", cols=9, rows=14, hole="behemoth"),
    # underwater seals / pockets
    "uw_seal":      dict(mode="wall", cols=9, rows=6, hole="dino", zstart=-400),
    "uw_pocket":    dict(mode="wall", cols=9, rows=6, hole="dino", zstart=-600),
    # sculpt recipes from spawn-command-cookbook.md §5
    "canyon_choke": dict(mode="wall", cols=9, rows=6, hole="dino"),
    "cliff_hollow": dict(mode="wall", cols=9, rows=6, hole="stego"),
    "ruin_plug":    dict(mode="wall", cols=3, rows=3, hole="crouch"),
    "ruin_fill":    dict(mode="wall", cols=5, rows=4, hole="stego"),
    "plateau_box":  dict(mode="box", cols=9, rows=6, depth=9, hole="dino", floor=True),
    "floating_island": dict(mode="platform", depth=8, cols=8),
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
    if args.mode in ("wall", "box") and args.cols <= 0 or args.rows <= 0:
        raise SystemExit("ERROR: cols and rows must be positive integers for wall/box mode")
    if args.mode == "box" and args.depth <= 0:
        raise SystemExit("ERROR: depth must be positive for box mode")
    if args.hole != "none":
        hc, hr = hole_cells(args.hole, sp)
        # A hole may exactly fill a dimension (a full-height/full-width gateway is
        # a legitimate build). Reject only when the hole is strictly LARGER than
        # the grid, which would collapse the surrounding wall into a single point.
        if args.mode in ("wall", "box") and (hc > args.cols or hr > args.rows):
            raise SystemExit(
                f"ERROR: hole '{args.hole}' needs ~{hc}x{hr} cells but "
                f"the {args.mode} grid is {args.cols}x{args.rows}. "
                f"Increase cols/rows or pick a smaller hole.")
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
    # optional pipe: prepend a teleport so the batch drops exactly where you convert
    if args.map is not None:
        if args.lat is None or args.lon is None:
            raise SystemExit("ERROR: --map requires --lat and --lon (pipe mode)")
        if args.map not in MAP_TRANSFORMS:
            raise SystemExit("map must be one of: " + ", ".join(MAP_TRANSFORMS))
        if not (0.0 <= float(args.lat) <= 100.0) or not (0.0 <= float(args.lon) <= 100.0):
            raise SystemExit("ERROR: lat/lon must be valid map coordinates 0..100.")
    lines, meta = build_commands(args)
    if args.json:
        payload = {"meta": meta, "commands": lines}
        if args.map is not None:
            slat, slon, mlat, mlon, approx = MAP_TRANSFORMS[args.map]
            payload["setplayerpos"] = {
                "map": args.map, "lat": args.lat, "lon": args.lon,
                "x": round((args.lon - slon) * mlon),
                "y": round((args.lat - slat) * mlat),
                "approx": bool(approx),
            }
        print(json.dumps(payload, indent=2))
    else:
        if args.map is not None:
            slat, slon, mlat, mlon, approx = MAP_TRANSFORMS[args.map]
            print(f"# {args.map}: Lat {args.lat}, Lon {args.lon}"
                  + ("  # APPROXIMATE" if approx else ""))
            print(f"cheat setplayerpos {(args.lon - slon) * mlon:.0f} "
                  f"{(args.lat - slat) * mlat:.0f} {args.z or 0:.0f}")
            print()
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
    if not (0.0 <= args.lat <= 100.0) or not (0.0 <= args.lon <= 100.0):
        raise SystemExit(
            f"ERROR: lat/lon must be valid map coordinates 0..100, got "
            f"lat={args.lat}, lon={args.lon}.")
    slat, slon, mlat, mlon, approx = MAP_TRANSFORMS[args.map]
    x = (args.lon - slon) * mlon
    y = (args.lat - slat) * mlat
    z = args.z if args.z is not None else 0
    flag = "  # APPROXIMATE — verify with arkids.net for this map" if approx else ""
    print(f"# {args.map}: Lat {args.lat}, Lon {args.lon}{flag}")
    print(f"cheat setplayerpos {x:.0f} {y:.0f} {z:.0f}")


def cmd_list(args):
    if getattr(args, "json", False):
        print(json.dumps({
            "blueprints": sorted(BLUEPRINTS),
            "presets": {k: v for k, v in sorted(PRESETS.items())},
            "maps": {k: {"approx": v[4]} for k, v in sorted(MAP_TRANSFORMS.items())},
        }, indent=2))
        return
    print("BLUEPRINTS:")
    for k in BLUEPRINTS:
        print(f"  {k}")
    print("\nPRESETS:")
    for k, v in PRESETS.items():
        print(f"  {k}: {v}")
    print("\nMAPS (convert):")
    for k, v in MAP_TRANSFORMS.items():
        print(f"  {k} (approx={v[4]})")


def demo_lines(preset):
    """ASCII grid preview of a named preset → list of lines (no printing)."""
    p = PRESETS.get(preset)
    if not p:
        raise SystemExit(f"Unknown preset '{preset}'. Choices: {', '.join(PRESETS)}")
    cols = p.get("cols", 7)
    rows = p.get("rows", 5)
    sp = p.get("spacing", 400)
    depth = p.get("depth")
    hole = p.get("hole", "none")
    hc, hr = hole_cells(hole, sp) if hole != "none" else (0, 0)
    hc0 = (cols - hc) // 2
    hr0 = (rows - hr) // 2
    out = [f"preset '{preset}' — mode {p.get('mode', '?')}"]
    out.append(f"  grid   {cols} cols x {rows} rows @ {sp} cm/cell" +
               (f"; depth {depth} cells" if depth else ""))
    if hole != "none":
        w_cm, h_cm = HOLE_PRESETS[hole]
        out.append(f"  hole   '{hole}' {w_cm}x{h_cm} cm = ~{hc}c x {hr}r, centered")
    out.append("+" + "-" * cols + "+")
    for r in range(rows):
        row = "|"
        for c in range(cols):
            in_hole = hole != "none" and hc0 <= c < hc0 + hc and hr0 <= r < hr0 + hr
            row += "." if in_hole else "#"
        out.append(row + "|")
    out.append("+" + "-" * cols + "+")
    out.append("Legend:  # = placed terminal  . = entrance hole")
    out.append(f"Commands: {cols * rows - hc * hr} spawnactor lines "
               f"(produced by: `gen --preset {preset}`)")
    return out


def cmd_demo(args):
    """ASCII preview of a named preset: grid dimensions + where the hole sits."""
    print("\n".join(demo_lines(args.preset)))


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
    g.add_argument("--map", default=None,
                   help="pipe mode: prepend setplayerpos for this map (needs --lat/--lon)")
    g.add_argument("--lat", type=float, default=None, help="pipe mode latitude")
    g.add_argument("--lon", type=float, default=None, help="pipe mode longitude")
    g.add_argument("--z", type=float, default=0, help="pipe mode altitude (cm)")
    g.set_defaults(func=cmd_gen)

    c = sub.add_parser("convert", help="lat/lon -> setplayerpos")
    c.add_argument("--map", required=True)
    c.add_argument("--lat", type=float, required=True)
    c.add_argument("--lon", type=float, required=True)
    c.add_argument("--z", type=float, default=None, help="altitude (cm); default 0")
    c.set_defaults(func=cmd_convert)

    l = sub.add_parser("list", help="list blueprints, presets, maps")
    l.add_argument("--json", action="store_true", help="emit JSON instead of text")
    l.set_defaults(func=cmd_list)

    d = sub.add_parser("demo", help="ASCII preview of a named preset grid")
    d.add_argument("--preset", required=True, choices=list(PRESETS))
    d.set_defaults(func=cmd_demo)

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
