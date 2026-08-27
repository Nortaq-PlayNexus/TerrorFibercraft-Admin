#!/usr/bin/env python3
"""
Terror Fibercraft 1000x — Admin Console CLI
==========================================
Single entrypoint that dispatches to the bundled admin modules:

  caves    -> custom-cave / sculpt generator (spawnactor command builder)
  rcon     -> RCON client for live server commands
  nitrado  -> Nitrado REST API client (server mgmt, config push)
  discord  -> Discord bot (slash commands for the community)
  cluster  -> print the Terror Fibercraft cluster definition
  doctor   -> environment + dependency self-check

All sub-modules live in this same folder and are dependency-light
(stdlib + a few pip packages). See README.md for the full architecture.

ENV: NITRADO_TOKEN, DISCORD_TOKEN, RCON_PASSWORD are read when not in config.json.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _run(module, args):
    cmd = [sys.executable, os.path.join(HERE, module)] + args
    return subprocess.call(cmd)


def cmd_caves(a): return _run("cave_spawn_generator.py", a)
def cmd_rcon(a):  return _run("ark_rcon.py", a)
def cmd_nitrado(a): return _run("nitrado_client.py", a)
def cmd_discord(a): return _run("discord_bot.py", a)


def cmd_cluster(a):
    path = os.path.join(HERE, "..", "..", "cluster", "cluster.json")
    try:
        with open(path) as f:
            print(json.dumps(json.load(f), indent=2))
    except FileNotFoundError:
        print("cluster/cluster.json not found", file=sys.stderr)
        return 1
    return 0


def cmd_doctor(a):
    ok = True
    print("== Terror Fibercraft Admin — doctor ==")
    for env in ("NITRADO_TOKEN", "DISCORD_TOKEN", "RCON_PASSWORD"):
        print(f"  [{'OK' if os.environ.get(env) else 'MISSING'}] env {env}")
        if not os.environ.get(env):
            ok = False
    try:
        import requests  # noqa
        print("  [OK] python 'requests' available")
    except ImportError:
        print("  [MISSING] python 'requests' (pip install -r requirements.txt)")
        ok = False
    try:
        import discord  # noqa
        print("  [OK] python 'discord.py' available")
    except ImportError:
        print("  [MISSING] python 'discord.py' (pip install -r requirements.txt)")
        ok = False
    print("  RESULT:", "READY" if ok else "NEEDS SETUP")
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(prog="tf_admin", description="Terror Fibercraft 1000x admin console")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("caves", help="custom-cave / sculpt generator").add_argument("args", nargs=argparse.REMAINDER)
    sub.add_parser("rcon", help="RCON client").add_argument("args", nargs=argparse.REMAINDER)
    sub.add_parser("nitrado", help="Nitrado API client").add_argument("args", nargs=argparse.REMAINDER)
    sub.add_parser("discord", help="Discord bot").add_argument("args", nargs=argparse.REMAINDER)
    sub.add_parser("cluster", help="print cluster definition").add_argument("args", nargs=argparse.REMAINDER)
    sub.add_parser("doctor", help="self-check").add_argument("args", nargs=argparse.REMAINDER)

    args = p.parse_args()
    rest = getattr(args, "args", []) or []
    return {
        "caves": cmd_caves, "rcon": cmd_rcon, "nitrado": cmd_nitrado,
        "discord": cmd_discord, "cluster": cmd_cluster, "doctor": cmd_doctor,
    }[args.cmd](rest)


if __name__ == "__main__":
    sys.exit(main())
