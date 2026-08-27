#!/usr/bin/env python3
"""
discord_bot.py — Terror Fibercraft 1000x admin Discord bot (ASE / Nitrado CrossPlay).

Because Arkon does NOT support ASE on Nitrado, this bot is our primary Discord
integration. It wraps:
  - NitradoClient   (start/stop/restart/status)
  - ark_rcon        (live admin commands: listplayers, sculpt apply)
  - cave-spawn-generator (build spawnactor batches)

Requires:  pip install discord.py
Config:    scripts/config.example.json -> scripts/config.json (gitignored)

Slash commands:
  /status <server>      Nitrado server status + player count
  /players <server>     live player list via RCON
  /convert <map> <lat> <lon>   lat/lon -> setplayerpos
  /sculpt <preset>      build a wall/box/platform batch (posted to channel)
  /applysculpt <server> send the last batch to the server via RCON
  /restart <server>     Nitrado restart (admin only)
  /donate               post the donation link

Run:  py discord_bot.py
"""
import asyncio
import json
import os
import sys

import discord
from discord import app_commands

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "03_CLUSTER_DESIGN"))

import ark_rcon  # noqa: E402
from nitrado_client import NitradoClient  # noqa: E402

try:
    from cave_spawn_generator import build_commands, blueprint_arg, PRESETS  # type: ignore
except Exception:
    # fallback: import by file name
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cavegen",
        os.path.join(HERE, "..", "03_CLUSTER_DESIGN", "cave-spawn-generator.py"),
    )
    cg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cg)
    build_commands = cg.build_commands
    blueprint_arg = cg.blueprint_arg
    PRESETS = cg.PRESETS

CONFIG_PATH = os.path.join(HERE, "config.json")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


cfg = load_config()
NITRA = NitradoClient(cfg["nitrado_token"])
SERVERS = cfg["servers"]  # {name: {service_id, gameserver_id, rcon_host, rcon_port, rcon_password}}

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

ADMIN_ROLE = cfg.get("admin_role", "Admin")


def is_admin(interaction: discord.Interaction) -> bool:
    return any(r.name == ADMIN_ROLE for r in interaction.user.roles)


# ----- commands -----
@tree.command(name="status", description="Nitrado server status + players")
@app_commands.describe(server="server name from config")
async def status(interaction: discord.Interaction, server: str):
    s = SERVERS.get(server)
    if not s:
        await interaction.response.send_message(f"Unknown server '{server}'.", ephemeral=True)
        return
    try:
        gs = NITRA.gameserver(s["service_id"], s["gameserver_id"])
        status = gs.get("status") or gs.get("state") or "?"
        players = (gs.get("players") or {}).get("online", "?")
        await interaction.response.send_message(
            f"**{server}**: status `{status}`, players `{players}`")
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)


@tree.command(name="players", description="Live player list via RCON")
@app_commands.describe(server="server name from config")
async def players(interaction: discord.Interaction, server: str):
    s = SERVERS.get(server)
    if not s:
        await interaction.response.send_message(f"Unknown server '{server}'.", ephemeral=True)
        return
    try:
        with ark_rcon.RconClient(s["rcon_host"], s["rcon_port"], s["rcon_password"]) as r:
            out = r.send("listplayers")
        await interaction.response.send_message(f"**{server}** players:\n```{out or 'none'}```")
    except Exception as e:
        await interaction.response.send_message(f"RCON error: {e}", ephemeral=True)


@tree.command(name="convert", description="lat/lon -> setplayerpos")
@app_commands.describe(map="map key", lat="latitude", lon="longitude")
async def convert(interaction: discord.Interaction, map: str, lat: float, lon: float):
    # reuse the generator's convert via subprocess-free import
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cg2", os.path.join(HERE, "..", "03_CLUSTER_DESIGN", "cave-spawn-generator.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if map not in m.MAP_TRANSFORMS:
        await interaction.response.send_message(f"Unknown map '{map}'.", ephemeral=True)
        return
    slat, slon, mlat, mlon, approx = m.MAP_TRANSFORMS[map]
    x = (lon - slon) * mlon
    y = (lat - slat) * mlat
    flag = " (APPROX)" if approx else ""
    await interaction.response.send_message(
        f"# {map}{flag}\n`cheat setplayerpos {x:.0f} {y:.0f} 0`")


@tree.command(name="sculpt", description="Build a wall/box/platform batch")
@app_commands.describe(preset="named preset", blueprint="blueprint key")
async def sculpt(interaction: discord.Interaction, preset: str, blueprint: str = "tribute_red"):
    if preset not in PRESETS:
        await interaction.response.send_message(f"Unknown preset '{preset}'.", ephemeral=True)
        return
    p = PRESETS[preset]
    args = argparse_ns(p, blueprint)
    lines, _ = build_commands(args)
    text = "\n".join(lines)
    # stash for apply
    with open(os.path.join(HERE, "last_batch.txt"), "w") as f:
        f.write(text)
    preview = text[:1800]
    await interaction.response.send_message(
        f"**{preset}** batch ({len(lines)} commands). Use `/applysculpt` to push.\n```{preview}```")


@tree.command(name="applysculpt", description="Push last batch to server via RCON (ADMIN)")
@app_commands.describe(server="server name from config")
async def applysculpt(interaction: discord.Interaction, server: str):
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only.", ephemeral=True)
        return
    s = SERVERS.get(server)
    if not s:
        await interaction.response.send_message(f"Unknown server '{server}'.", ephemeral=True)
        return
    path = os.path.join(HERE, "last_batch.txt")
    if not os.path.exists(path):
        await interaction.response.send_message("No batch yet; run /sculpt first.", ephemeral=True)
        return
    with open(path) as f:
        cmds = [l.strip() for l in f if l.strip().startswith("cheat ")]
    try:
        with ark_rcon.RconClient(s["rcon_host"], s["rcon_port"], s["rcon_password"]) as r:
            for c in cmds:
                r.send(c)
        await interaction.response.send_message(f"Applied {len(cmds)} commands to {server}.")
    except Exception as e:
        await interaction.response.send_message(f"RCON error: {e}", ephemeral=True)


@tree.command(name="restart", description="Nitrado restart (ADMIN)")
@app_commands.describe(server="server name from config")
async def restart(interaction: discord.Interaction, server: str):
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only.", ephemeral=True)
        return
    s = SERVERS.get(server)
    if not s:
        await interaction.response.send_message(f"Unknown server '{server}'.", ephemeral=True)
        return
    try:
        NITRA.restart(s["service_id"], s["gameserver_id"])
        await interaction.response.send_message(f"Restart issued for {server}.")
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)


@tree.command(name="donate", description="Post the donation link")
async def donate(interaction: discord.Interaction):
    await interaction.response.send_message(
        cfg.get("donate_message", "Support the cluster: <donation link>"))


def argparse_ns(preset_dict, blueprint):
    import argparse
    ns = argparse.Namespace(
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
    return ns


@bot.event
async def on_ready():
    await tree.sync()
    print(f"TerrorFibercraft bot logged in as {bot.user}")


if __name__ == "__main__":
    bot.run(cfg["discord_token"])
