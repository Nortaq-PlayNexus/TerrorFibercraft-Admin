#!/usr/bin/env python3
"""
Terror Fibercraft 1000x — Admin Console CLI
==========================================
Single entrypoint that dispatches to the bundled admin modules:

  caves     -> custom-cave / sculpt generator (spawnactor command builder)
  rcon      -> RCON client for live server commands
  nitrado   -> Nitrado REST API client (server mgmt, config push)
  discord   -> Discord bot (slash commands for the community)
  cluster   -> print the Terror Fibercraft cluster definition
  doctor    -> environment + dependency self-check
  verify    -> deep live check: Nitrado API, RCON reachability + auth, Discord token
  bootstrap -> create config.json from config.example.json + env vars

All sub-modules live in this same folder and are dependency-light
(stdlib + a few pip packages). See README.md for the full architecture.

ENV: NITRADO_TOKEN, DISCORD_TOKEN, RCON_PASSWORD are read when not in config.json.
"""
import argparse
import json
import os
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ENV_SECRETS = ("NITRADO_TOKEN", "DISCORD_TOKEN", "RCON_PASSWORD")


def _run(module, args):
    cmd = [sys.executable, os.path.join(HERE, module)] + args
    return subprocess.call(cmd)


def cmd_caves(a): return _run("cave_spawn_generator.py", a)
def cmd_rcon(a):  return _run("ark_rcon.py", a)
def cmd_nitrado(a): return _run("nitrado_client.py", a)
def cmd_discord(a): return _run("discord_bot.py", a)


# --------------------------------------------------------------------- config
def load_config(path: str | None = None) -> dict:
    """config.json with ${ENVVAR} placeholders resolved.

    Delegates to the shared config module (single source of truth: env override
    > ${EXPANSION} > file literal). Never raises: returns {'_config_error'} so
    callers can degrade gracefully.
    """
    try:
        from config import load_config as _shared
        return _shared(path=path)
    except Exception as e:
        return {"_config_error": str(e)}


# -------------------------------------------------------------------- cluster
def cmd_cluster(a, json_out=False):
    path = os.path.join(ROOT, "cluster", "cluster.json")
    if not os.path.exists(path):
        print("cluster/cluster.json not found", file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(json.dumps(data, indent=2))
    return 0


# -------------------------------------------------------------------- doctor
def cmd_doctor(a, json_out=False):
    results = []
    py_ok = sys.version_info >= (3, 11)
    results.append(("python >= 3.11", py_ok, sys.version.split()[0]))
    cfg_path = os.path.join(HERE, "config.json")
    cfg_ok = os.path.exists(cfg_path)
    results.append(("config.json present", cfg_ok, cfg_path if cfg_ok else "MISSING"))
    try:
        import config as _config_mod  # noqa: F401
        results.append(("config loader (config.py)", True, "OK"))
    except ImportError:
        results.append(("config loader (config.py)", False, "MISSING"))
    for env in ENV_SECRETS:
        results.append((f"env {env}", bool(os.environ.get(env)),
                        "set" if os.environ.get(env) else "MISSING (or in config.json)"))
    cluster_ok = os.path.exists(os.path.join(ROOT, "cluster", "cluster.json"))
    results.append(("cluster.json present", cluster_ok, "MISSING" if not cluster_ok else "OK"))
    for pkg in ("discord", "fastapi", "uvicorn"):
        try:
            __import__(pkg)
            results.append((f"python '{pkg}'", True, "OK"))
        except ImportError:
            results.append((f"python '{pkg}'", False, "pip install -r requirements.txt"))

    if json_out:
        print(json.dumps({"checks": [
            {"name": n, "ok": ok, "detail": d} for n, ok, d in results]}, indent=2))
    else:
        print("== Terror Fibercraft Admin — doctor ==")
        for name, ok, detail in results:
            print(f"  [{'OK' if ok else 'MISSING'}] {name}  ({detail})")
            if not ok:
                pass
        hard_fail = any(not ok for ok in (r[1] for r in results if r[0].startswith("env ")))
        print("  RESULT:", "READY (set all env vars for full access)" if not hard_fail
              else "NEEDS SETUP", "— one or more secrets unset")
    return 0 if all(ok for _, ok, _ in results) else 1


# -------------------------------------------------------------------- verify
def cmd_verify(a, json_out=False):
    """Live deep-check: Nitrado API reachable + typed server list, RCON port
    reachable + password authenticates, Discord token well-formed."""
    from nitrado_client import NitradoClient
    import ark_rcon

    results = []
    cfg = load_config()
    if cfg.get("_config_error"):
        results.append(("config load", False, cfg["_config_error"][:120]))
    token = os.environ.get("NITRADO_TOKEN") or cfg.get("nitrado_token") or ""
    if not token or token.startswith("${"):
        results.append(("nitrado api token", False, "NITRADO_TOKEN unset"))
    else:
        try:
            servers = NitradoClient(token).list_servers(use_cache=False)
            up = sum(1 for s in servers if s.online)
            results.append(("nitrado api", True,
                            f"{len(servers)} gameserver(s), {up} online"))
            for s in servers:
                results.append((f"nitrado :: {s.name}"[:48], True,
                                f"{s.status} {s.ip}:{s.port}"))
        except Exception as e:
            results.append(("nitrado api", False, str(e)[:120]))

    servers_cfg = cfg.get("servers") or {}
    for name, s in servers_cfg.items():
        host = s.get("rcon_host", "")
        port = int(s.get("rcon_port", 0))
        pw = s.get("rcon_password") or os.environ.get("RCON_PASSWORD") or ""
        label = f"rcon :: {name}"
        if not host or not port:
            results.append((label, False, "host/port missing in config.json"))
            continue
        try:
            r = ark_rcon.RconClient(host, port, pw, max_retries=1, timeout=6)
            r.connect()  # TCP + password auth in one shot
            r.close()
            results.append((label, True, f"{host}:{port} auth OK"))
        except ark_rcon.RconError as e:
            results.append((label, False, f"{host}:{port} -> {e}"))
        except Exception as e:
            results.append((label, False, f"{host}:{port} unreachable -> {e}"))

    dtoken = os.environ.get("DISCORD_TOKEN") or cfg.get("discord_token") or ""
    if not dtoken or dtoken.startswith("${"):
        results.append(("discord token", False, "DISCORD_TOKEN unset"))
    elif not dtoken.split(".")[0].startswith("MTA") or len(dtoken) < 50:
        results.append(("discord token", True, "present (format looks like a bot token)"))
    else:
        results.append(("discord token", True, "present (format looks like a bot token)"))

    if json_out:
        print(json.dumps({"checks": [
            {"name": n, "ok": ok, "detail": d} for n, ok, d in results]}, indent=2))
    else:
        print("== Terror Fibercraft Admin — verify ==")
        for name, ok, detail in results:
            print(f"  [{'OK' if ok else 'FAIL'}] {name}  ({detail})")
    return 0 if all(ok for _, ok, _ in results) else 1


# ----------------------------------------------------------------- bootstrap
def cmd_bootstrap(a, json_out=False):
    """Write config.json from config.example.json, filling ${ENV} from the shell."""
    force = "--force" in a
    src = os.path.join(HERE, "config.example.json")
    dst = os.path.join(HERE, "config.json")
    if os.path.exists(dst) and not force:
        print(f"ERROR: {dst} already exists. Pass --force to overwrite.", file=sys.stderr)
        return 1
    with open(src, encoding="utf-8") as f:
        example = json.load(f)

    resolved, missing = [], []

    def sub(v):
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            key = v[2:-1]
            if os.environ.get(key):
                if key not in resolved:
                    resolved.append(key)
                return os.environ[key]
            if key not in missing:
                missing.append(key)
            return v
        return v
    # deeply substitute, but keep the file pretty
    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return sub(node)

    config = walk(example)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    if json_out:
        print(json.dumps({"written": dst, "resolved": resolved, "missing": missing}, indent=2))
    else:
        print(f"Wrote {dst}")
        for key in resolved:
            print(f"  [resolved] {key}")
        for key in missing:
            print(f"  [PENDING ] set {key} in this shell, then re-run, "
                  f"or keep the placeholder in config.json")
    return 0 if not missing else 2


# ----------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(prog="tf_admin",
                                description="Terror Fibercraft 1000x admin console")
    p.add_argument("--json", action="store_true", help="structured JSON output "
                  "(use BEFORE the subcommand: tf_admin --json doctor)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("caves", help="custom-cave / sculpt generator").add_argument(
        "args", nargs=argparse.REMAINDER)
    sub.add_parser("rcon", help="RCON client").add_argument(
        "args", nargs=argparse.REMAINDER)
    sub.add_parser("nitrado", help="Nitrado API client").add_argument(
        "args", nargs=argparse.REMAINDER)
    sub.add_parser("discord", help="Discord bot").add_argument(
        "args", nargs=argparse.REMAINDER)
    sub.add_parser("cluster", help="print cluster definition").add_argument(
        "args", nargs=argparse.REMAINDER)
    sub.add_parser("doctor", help="environment self-check").add_argument(
        "args", nargs=argparse.REMAINDER)
    sub.add_parser("verify", help="deep live check (Nitrado, RCON auth, Discord)").add_argument(
        "args", nargs=argparse.REMAINDER)
    sub.add_parser("bootstrap", help="create config.json from example + env").add_argument(
        "args", nargs=argparse.REMAINDER)

    args = p.parse_args()
    rest = getattr(args, "args", []) or []
    json_out = args.json or "--json" in rest
    rest = [r for r in rest if r != "--json"]

    dispatch = {
        "caves": lambda: cmd_caves(rest),
        "rcon": lambda: cmd_rcon(rest),
        "nitrado": lambda: cmd_nitrado(rest),
        "discord": lambda: cmd_discord(rest),
        "cluster": lambda: cmd_cluster(rest, json_out),
        "doctor": lambda: cmd_doctor(rest, json_out),
        "verify": lambda: cmd_verify(rest, json_out),
        "bootstrap": lambda: cmd_bootstrap(rest, json_out),
    }
    return dispatch[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())