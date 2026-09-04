#!/usr/bin/env python3
"""
config.py — Shared configuration loader for the Terror Fibercraft admin console.

Resolves secrets with an order of precedence:
  1. Environment variables (NITRADO_TOKEN, DISCORD_TOKEN, RCON_PASSWORD, ...)
  2. `${ENV_VAR}` placeholders expanded inside config.json / config.example.json
  3. Raw literal values in the config file (fallback)

`${ENV_VAR}` placeholders in any string field are expanded to the environment
value when the variable is set. Unresolved placeholders (variable unset) are
replaced with an empty string, and the field is flagged so consumers can warn.

This is THE single place config is loaded: tf_admin.py, discord_bot.py,
nitrado_client.py and the monitor all import :func:`load_config` so server keys
and the cluster metadata are consistent across the app.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEARCH_PATHS = (
    os.environ.get("TFC_CONFIG", ""),
    os.path.join(HERE, "config.json"),
    os.path.join(HERE, "config.example.json"),
)
# The search path a user should land on first; used only for reporting.
PRIMARY_PATH = os.path.join(HERE, "config.json")

# Maps top-level secret fields to their environment variable names.
ENV_FIELDS = {
    "discord_token": "DISCORD_TOKEN",
    "nitrado_token": "NITRADO_TOKEN",
    "rcon_password": "RCON_PASSWORD",
}

_PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)\}")


def resolve_placeholders(value, env=None):
    """Expand ``${VAR}`` in a string using env vars. Missing vars become ''."""
    if not isinstance(value, str):
        return value
    env = env if env is not None else os.environ

    def _sub(m):
        return env.get(m.group(1), "")

    return _PLACEHOLDER.sub(_sub, value)


def _resolve_tree(node, env=None):
    """Recursively expand ${VAR} placeholders across a JSON-like structure."""
    if isinstance(node, dict):
        return {k: _resolve_tree(v, env) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve_tree(v, env) for v in node]
    return resolve_placeholders(node, env)


def validate_structure(cfg):
    """Ensure minimal required keys exist; raise with a clear message if not."""
    errs = []
    if not isinstance(cfg, dict):
        raise ValueError("config root must be a JSON object")
    if "servers" not in cfg or not isinstance(cfg["servers"], dict):
        errs.append("missing 'servers' object")
    elif not cfg["servers"]:
        errs.append("'servers' is empty (add at least one <name>: {...})")
    else:
        for name, s in cfg["servers"].items():
            for k in ("service_id", "gameserver_id"):
                if k not in s or s[k] in (None, ""):
                    errs.append(f"servers['{name}'] missing non-empty '{k}'")
            for k in ("rcon_host", "rcon_port", "rcon_password"):
                if k not in s:
                    errs.append(f"servers['{name}'] missing '{k}'")
    if errs:
        raise ValueError("config validation failed:\n  - " + "\n  - ".join(errs))
    return cfg


def _read_file(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_config(path=None, env=None):
    """Load + resolve + validate config.

    Returns a dict with:
      * every field from the file (placeholders resolved)
      * ``resolved_from`` — the path that was actually loaded
      * ``unresolved`` — list of ``(field, env_var)`` for secrets that could
        not be satisfied by env or the file (empty-string values)
    """
    env = env if env is not None else os.environ

    # 1. Secret env vars override file values outright (env > file).
    overrides = {}
    for field, var in ENV_FIELDS.items():
        if env.get(var):
            overrides[field] = env[var]

    # 2. Find and parse the first available config file. An explicitly passed
    #    path that doesn't exist is ignored (falls through to the search paths).
    if path:
        path = path if os.path.exists(path) else None
    path = path or next((p for p in SEARCH_PATHS if p and os.path.exists(p)), None)
    if path is None:
        path = PRIMARY_PATH
        cfg = {}
    else:
        cfg = _read_file(path)

    # 3. Expand ${VAR} placeholders recursively for whatever came from the file.
    cfg = _resolve_tree(cfg, env)

    # 4. Apply direct env overrides after expansion (highest precedence).
    cfg.update(overrides)

    # 5. Scaffold optional top-level defaults so consumers needn't guard.
    cfg.setdefault("admin_role", "Cluster Admin")
    cfg.setdefault("donate_message", "Support the cluster.")
    cfg.setdefault("cluster", {})
    cfg.setdefault("servers", {})

    # 6. Detect secrets that remained empty / unresolved.
    unresolved = []
    for field, var in ENV_FIELDS.items():
        if not cfg.get(field):
            # rcon_password can live per-server, so only flag the global one
            # when it's entirely absent everywhere; keep it simple otherwise.
            unresolved.append((field, var))

    # Per-server rcon_password resolution happens per-server in callers; here we
    # just surface a global note when nothing is configured anywhere.
    rcon_any = any(
        s.get("rcon_password") for s in cfg.get("servers", {}).values()
    )
    if not rcon_any:
        unresolved.append(("servers[*].rcon_password", "RCON_PASSWORD"))

    validate_structure(cfg)
    cfg["_resolved_from"] = path
    cfg["_unresolved"] = unresolved
    return cfg


def pretty_doctor(cfg):
    """Render a human-readable doctor summary for a resolved config."""
    lines = ["== Terror Fibercraft Admin — config =="]
    lines.append(f"  config file : {cfg.get('_resolved_from')}")
    for field, var in ENV_FIELDS.items():
        val = cfg.get(field)
        state = "OK (env)" if os.environ.get(var) else ("OK (file)" if val else "MISSING")
        lines.append(f"  [{state}] {field}")
    if not any(s.get("rcon_password") for s in cfg.get("servers", {}).values()):
        lines.append("  [MISSING] rcon_password (per-server)")
    for field, var in cfg.get("_unresolved", []):
        lines.append(f"  [MISSING] {field} (set env {var} or fill config file)")
    return lines


if __name__ == "__main__":
    cfg = load_config()
    print("\n".join(pretty_doctor(cfg)))
    sys.exit(0 if not cfg["_unresolved"] else 1)
