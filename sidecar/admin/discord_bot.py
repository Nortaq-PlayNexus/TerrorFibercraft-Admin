#!/usr/bin/env python3
"""
discord_bot.py — Terror Fibercraft 1000x admin Discord bot (ASE / Nitrado CrossPlay).

Because Arkon does NOT support ASE on Nitrado, this bot is our primary Discord
integration. It wraps:
  - NitradoClient   (start/stop/restart/status)
  - ark_rcon        (live admin commands: listplayers, sculpt apply)
  - cave-spawn-generator (build spawnactor batches)

Run:  py discord_bot.py                 (reads config.json; env overrides tokens)

Architecture / hardening:
  * commands grouped into cogs (Ops / Sculpt / Support) — easy to extend
  * every human/mutating action is written to a JSONL audit log (logs/audit.jsonl)
  * admin gating by role ID(s) OR role name(s) from config
  * retry-safe Discord replies (429 backoff) instead of one-shot send_message
  * env overrides: DISCORD_TOKEN / NITRADO_TOKEN win over config.json; ${VAR}
    placeholders are resolved from the environment

Config: config.example.json -> config.json (gitignored). Sample fields:
  discord_token, nitrado_token, admin_role ("Admin"), admin_role_ids [123,...],
  donate_message, servers { "theisland": {service_id, gameserver_id, rcon_host,
  rcon_port, rcon_password | ${RCON_PASSWORD}} }
"""
import asyncio
import datetime
import functools
import json
import os
import sys
import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ark_rcon  # noqa: E402
from nitrado_client import NitradoClient  # noqa: E402

try:
    from cave_spawn_generator import build_commands, PRESETS  # type: ignore
except Exception:  # pragma: no cover - fallback import path
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cavegen", os.path.join(HERE, "cave_spawn_generator.py"))
    cg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cg)
    build_commands = cg.build_commands
    PRESETS = cg.PRESETS

CONFIG_PATH = os.path.join(HERE, "config.json")
DEFAULT_AUDIT_PATH = os.path.join(HERE, "logs", "audit.jsonl")
DEFAULT_BATCH_PATH = os.path.join(HERE, "logs", "last_batch.txt")


# --------------------------------------------------------------------- config
# Delegates to the shared config.load_config (the single source of truth:
# env override > ${EXPANSION} > file literal). Never raises.
def load_config(path: str | None = None) -> dict:
    from config import load_config as _shared
    try:
        return _shared(path=path)
    except Exception as e:
        return {"_config_error": str(e)}


# ------------------------------------------------------------------- audit log
class AuditLog:
    """Append-only JSONL audit trail for every bot command."""

    def __init__(self, path: str = DEFAULT_AUDIT_PATH):
        self.path = path
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    def record(self, interaction, command: str, options: dict, ok: bool,
               ms: float, error: str | None = None):
        entry = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds"),
            "command": command,
            "user": {"id": str(interaction.user.id), "name": str(interaction.user)},
            "guild": str(interaction.guild_id) if interaction.guild_id else None,
            "channel": str(interaction.channel_id) if interaction.channel_id else None,
            "options": {k: str(v)[:500] for k, v in options.items()},
            "ok": bool(ok),
            "ms": int(ms * 1000),
        }
        if error:
            entry["error"] = str(error)[:1000]
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def tail(self, n: int = 20) -> list[dict]:
        entries = []
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-n:]


# -------------------------------------------------------------------- helpers
def audit(name: str):
    """Wrap a cog command to log success/failure to the audit trail."""
    def deco(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            opts = {**{f"arg{i}": a for i, a in enumerate(args)}, **kwargs}
            started = time.monotonic()
            try:
                result = await func(self, interaction, *args, **kwargs)
                self.audit.record(interaction, name, opts, ok=True,
                                  ms=time.monotonic() - started)
                return result
            except Exception as e:
                self.audit.record(interaction, name, opts, ok=False,
                                  ms=time.monotonic() - started, error=str(e))
                raise
        return wrapper
    return deco


def is_admin(interaction: discord.Interaction, cfg: dict) -> bool:
    role_ids = set()
    for _id in cfg.get("admin_role_ids") or []:
        try:
            role_ids.add(int(_id))
        except (TypeError, ValueError):
            continue
    role_names = {str(cfg.get("admin_role", "Admin"))}
    for r in interaction.user.roles:
        if r.id in role_ids or r.name in role_names:
            return True
    return False


async def reply(interaction: discord.Interaction, content: str,
                ephemeral: bool = False, retries: int = 3):
    """Send a reply with retry + backoff, supporting follow-up messages."""
    for attempt in range(retries):
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(content, ephemeral=ephemeral)
            return
        except discord.HTTPException as e:
            if e.status == 429 and attempt < retries - 1:
                await asyncio.sleep(2 ** attempt + 1)
                continue
            raise


def get_server(cfg: dict, name: str):
    s = (cfg.get("servers") or {}).get(name)
    if s is None:
        return None, f"Unknown server '{name}'. Known: {', '.join((cfg.get('servers') or {}))}"
    return s, None


# ------------------------------------------------------------------------ cogs
class OpsCog(commands.Cog):
    """Server operations: status, players, restart."""

    def __init__(self, bot, cfg: dict, nitra: NitradoClient, audit: AuditLog):
        self.bot = bot
        self.cfg = cfg
        self.nitra = nitra
        self.audit = audit

    @app_commands.command(name="status", description="Nitrado server status + players")
    @app_commands.describe(server="server name from config")
    @audit("status")
    async def status(self, interaction: discord.Interaction, server: str):
        s, err = get_server(self.cfg, server)
        if err:
            return await reply(interaction, err, ephemeral=True)
        try:
            gs = self.nitra.gameserver(s["service_id"], s["gameserver_id"])
        except Exception as e:
            return await reply(interaction, f"Nitrado error: {e}", ephemeral=True)
        status = gs.get("status") or gs.get("state") or "?"
        ip = gs.get("ip") or "?"
        port = gs.get("port") or "?"
        online = status in ("started", "online", "running", "starting")
        await reply(interaction,
                    f"**{server}** · `{status}` · {ip}:{port} · "
                    f"{'🟢 up' if online else '🔴 down'}")

    @app_commands.command(name="players", description="Live player list via RCON")
    @app_commands.describe(server="server name from config")
    @audit("players")
    async def players(self, interaction: discord.Interaction, server: str):
        s, err = get_server(self.cfg, server)
        if err:
            return await reply(interaction, err, ephemeral=True)
        try:
            with ark_rcon.RconClient(s["rcon_host"], int(s["rcon_port"]),
                                     s["rcon_password"]) as r:
                out = r.send("listplayers")
        except Exception as e:
            return await reply(interaction, f"RCON error: {e}", ephemeral=True)
        body = out.strip() or "none"
        await reply(interaction, f"**{server}** players:\n```{body}```")

    @app_commands.command(name="restart", description="Nitrado restart (ADMIN)")
    @app_commands.describe(server="server name from config")
    @audit("restart")
    async def restart(self, interaction: discord.Interaction, server: str):
        if not is_admin(interaction, self.cfg):
            return await reply(interaction, "Admin only.", ephemeral=True)
        s, err = get_server(self.cfg, server)
        if err:
            return await reply(interaction, err, ephemeral=True)
        try:
            self.nitra.restart(s["service_id"], s["gameserver_id"])
        except Exception as e:
            return await reply(interaction, f"Nitrado error: {e}", ephemeral=True)
        await reply(interaction, f"Restart issued for {server}. "
                                 f"It will be back within a minute or two.")

    @app_commands.command(name="audit", description="Show recent admin actions (ADMIN)")
    @app_commands.describe(n="how many recent entries to show (default 20)")
    @audit("audit")
    async def audit_cmd(self, interaction: discord.Interaction, n: int = 20):
        if not is_admin(interaction, self.cfg):
            return await reply(interaction, "Admin only.", ephemeral=True)
        entries = self.audit.tail(max(1, min(n, 100)))
        if not entries:
            return await reply(interaction, "No audit entries yet.", ephemeral=True)
        lines = [f"[{e['ts']}] /{e['command']} by {e['user']['name']} "
                 f"{'✅' if e['ok'] else '❌'}" for e in entries]
        await reply(interaction, "```\n" + "\n".join(lines) + "```", ephemeral=True)


class SculptCog(commands.Cog):
    """Custom-cave sculpting: convert coordinates, build batches, apply via RCON."""

    def __init__(self, bot, cfg: dict, nitra: NitradoClient, audit: AuditLog):
        self.bot = bot
        self.cfg = cfg
        self.nitra = nitra
        self.audit = audit

    @staticmethod
    def _convert(map_: str, lat: float, lon: float):
        from cave_spawn_generator import MAP_TRANSFORMS
        if map_ not in MAP_TRANSFORMS:
            return None, f"Unknown map '{map_}'. Known: {', '.join(MAP_TRANSFORMS)}"
        if not (0.0 <= lat <= 100.0) or not (0.0 <= lon <= 100.0):
            return None, "lat/lon must be map coordinates 0..100."
        slat, slon, mlat, mlon, approx = MAP_TRANSFORMS[map_]
        x = (lon - slon) * mlon
        y = (lat - slat) * mlat
        flag = " (APPROXIMATE — verify in-game)" if approx else ""
        return f"`cheat setplayerpos {x:.0f} {y:.0f} 0`", flag

    @app_commands.command(name="convert", description="lat/lon -> setplayerpos")
    @app_commands.describe(map="map key", lat="latitude (0..100)", lon="longitude (0..100)")
    @audit("convert")
    async def convert(self, interaction: discord.Interaction, map: str, lat: float, lon: float):
        cmd, flag = self._convert(map, lat, lon)
        if cmd is None:
            return await reply(interaction, flag, ephemeral=True)
        await reply(interaction, f"# {map}{flag}\n{cmd}")

    @app_commands.command(name="sculpt", description="Build a wall/box/platform batch")
    @app_commands.describe(preset="named preset", blueprint="blueprint key")
    @audit("sculpt")
    async def sculpt(self, interaction: discord.Interaction, preset: str,
                     blueprint: str = "tribute_red"):
        if preset not in PRESETS:
            return await reply(interaction,
                               f"Unknown preset '{preset}'. Known: {', '.join(PRESETS)}",
                               ephemeral=True)
        p = PRESETS[preset]
        ns = argparse_ns(p, blueprint)
        try:
            lines, _ = build_commands(ns)
        except SystemExit as e:
            return await reply(interaction, str(e), ephemeral=True)
        text = "\n".join(lines)
        Path(DEFAULT_BATCH_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(DEFAULT_BATCH_PATH, "w", encoding="utf-8") as f:
            f.write(text)
        preview = text[:1800]
        await reply(interaction,
                    f"**{preset}** batch ({len(lines)} commands). "
                    f"Use `/applysculpt` to push.\n```{preview}```")

    @app_commands.command(name="applysculpt", description="Push last batch to server (ADMIN)")
    @app_commands.describe(server="server name from config")
    @audit("applysculpt")
    async def applysculpt(self, interaction: discord.Interaction, server: str):
        if not is_admin(interaction, self.cfg):
            return await reply(interaction, "Admin only.", ephemeral=True)
        s, err = get_server(self.cfg, server)
        if err:
            return await reply(interaction, err, ephemeral=True)
        if not os.path.exists(DEFAULT_BATCH_PATH):
            return await reply(interaction, "No batch yet; run /sculpt first.", ephemeral=True)
        with open(DEFAULT_BATCH_PATH, encoding="utf-8") as f:
            cmds = [l.strip() for l in f if l.strip().startswith("cheat ")]
        if not cmds:
            return await reply(interaction, "Batch is empty.", ephemeral=True)
        nc = cmds
        try:
            with ark_rcon.RconClient(s["rcon_host"], int(s["rcon_port"]),
                                     s["rcon_password"]) as r:
                # rate-limit 20cmds/sec so we don't spam the source engine
                r.send_many(nc, interval=0.05)
        except Exception as e:
            return await reply(interaction, f"RCON error: {e}", ephemeral=True)
        await reply(interaction, f"Applied {len(nc)} commands to {server}.")


class SupportCog(commands.Cog):
    """Community / non-admin commands."""

    def __init__(self, bot, cfg: dict):
        self.bot = bot
        self.cfg = cfg

    @app_commands.command(name="donate", description="Post the donation link")
    @audit("donate")
    async def donate(self, interaction: discord.Interaction):
        await reply(interaction,
                    self.cfg.get("donate_message", "Support the cluster: <donation link>"))


def argparse_ns(preset_dict, blueprint):
    import argparse
    return argparse.Namespace(
        blueprint=blueprint,
        mode=preset_dict.get("mode", "wall"),
        cols=preset_dict.get("cols", 7),
        rows=preset_dict.get("rows", 5),
        depth=preset_dict.get("depth", 7),
        spacing=preset_dict.get("spacing", 400),
        forward=preset_dict.get("forward", 400),
        zstart=preset_dict.get("zstart", 0),
        hole=preset_dict.get("hole", "none"),
        floor=preset_dict.get("floor", False),
        ceiling=preset_dict.get("ceiling", False),
    )


# --------------------------------------------------------------------- factory
def create_bot(cfg: dict) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="/", intents=intents)
    audit_log = AuditLog(cfg.get("audit_log_path", DEFAULT_AUDIT_PATH))
    nitra = NitradoClient(cfg.get("nitrado_token") or "")

    async def add_cogs():
        await bot.tree.add_cog(OpsCog(bot, cfg, nitra, audit_log))
        await bot.tree.add_cog(SculptCog(bot, cfg, nitra, audit_log))
        await bot.tree.add_cog(SupportCog(bot, cfg))

    @bot.event
    async def on_ready():
        await add_cogs()
        await bot.tree.sync()
        print(f"TerrorFibercraft bot online as {bot.user} — "
              f"{len(bot.guilds)} guild(s), cogs synced")

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error):
        msg = getattr(error, "original", error)
        try:
            await reply(interaction, f"Command error: {msg}", ephemeral=True)
        except Exception:
            pass

    return bot


# ------------------------------------------------------------------------- CLI
def main():
    cfg = load_config()
    if cfg.get("_config_error"):
        print(f"config error: {cfg['_config_error']}", file=sys.stderr)
        return 1
    if not cfg.get("discord_token"):
        print("Missing DISCORD_TOKEN (env or config.json).", file=sys.stderr)
        return 1
    if not cfg.get("nitrado_token"):
        print("Missing NITRADO_TOKEN (env or config.json).", file=sys.stderr)
        return 1
    bot = create_bot(cfg)
    bot.run(cfg["discord_token"])


if __name__ == "__main__":
    sys.exit(main())