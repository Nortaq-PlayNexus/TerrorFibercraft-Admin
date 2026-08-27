# TerrorFibercraft-Admin

**Cluster admin console for _Terror Fibercraft 1000x_** — an ARK: Survival Evolved
(ASE) cluster on **Xbox + Microsoft Store (Windows 10/11) CrossPlay only**, hosted on
**Nitrado**, public = PvP, private rented = PvE. Rates 1000x. Donations-only / no pay-to-win.

This is a desktop `.exe` (Tauri: Rust core + React shell + Python sidecar) that gives
cluster admins one place to: sculpt custom caves/terrain, drive Nitrado + RCON, and run
the community Discord bot — all pre-loaded with the Terror Fibercraft setup.

> **Forked from [`ArkNexusX`](https://github.com/Nortaq-PlayNexus/ArkNexusX)** (upstream
> remote retained). The inherited Tauri desktop shell + Python sidecar architecture is the
> reusable foundation. The player-automation engine of the upstream project is retained as a
> generic desktop-toolkit but is **not** the supported product here; this repo's purpose is
> server/cluster administration via official APIs (Nitrado, RCON, Discord) — no in-game
> automation that would violate ARK's EULA or Xbox ToS.

## What's in here (the "best of everything")

| Source | Reused for | Location |
|--------|-----------|----------|
| ArkNexusX | Tauri desktop `.exe` shell + Python sidecar infra | `src-tauri/`, `frontend/`, `sidecar/` |
| TerrorFibercraft_1000x docs | Cluster configs, rates, maps, spawn cookbook | `cluster/` |
| cave-spawn-generator (v2) | Custom-cave / sculpt command builder w/ presets | `sidecar/admin/cave_spawn_generator.py` |
| ark_rcon / nitrado_client / discord_bot | Live server + community control | `sidecar/admin/` |
| Ark Arena Architect | Admin command-export UX patterns (Phase 2 UI) | (design reference) |
| arkbridge | MS-Store/UWP (Xbox Play-Anywhere) handling notes | (design reference) |

## Quick start (Python admin sidecar)

```powershell
cd sidecar/admin
python -m pip install -r requirements.txt
$env:NITRADO_TOKEN="..."; $env:DISCORD_TOKEN="..."; $env:RCON_PASSWORD="..."
python tf_admin.py doctor            # self-check
python tf_admin.py cluster           # print cluster definition
python tf_admin.py caves list        # list cave presets
python tf_admin.py caves gen --preset dino_gate --json
python tf_admin.py rcon --help
python tf_admin.py nitrado --help
python tf_admin.py discord --help
```

## Custom caves (admin-only terrain)

`cave_spawn_generator.py` builds ordered `cheat spawnactor` commands that drop floating
terminal structures to sculpt admin-only terrain (cave walls, sealed shells, platforms,
canyon chokes). **This is ADMIN terrain only** — players using these to box bases or block
paths is a bannable exploit.

```powershell
python tf_admin.py caves gen --preset dino_gate
python tf_admin.py caves gen --mode box --cols 9 --rows 6 --depth 9 --hole behemoth --floor --json
python tf_admin.py caves apply --host 1.2.3.4 --port 27020 --password $env:RCON_PASSWORD --file walls.txt
```

## Repository layout

```
cluster/        Game.ini, GameUserSettings.ini, maps-plan, spawn cookbook, cluster.json
sidecar/admin/  tf_admin.py + cave_spawn_generator.py, ark_rcon.py, nitrado_client.py, discord_bot.py
src-tauri/      Rust desktop core (from ArkNexusX, repurposed)
frontend/       React admin UI (Phase 2: admin panels)
crates/         Rust workspace (inherited from ArkNexusX; automation crates retained as generic toolkit)
docs/           Architecture & runbooks
```

## Roadmap (Phase 2)

1. React admin panels: Cluster Overview, Custom Caves, Nitrado Manager, Discord, Maps, Compliance.
2. Replace player-automation crates with `admin` Rust modules that wrap the sidecar APIs.
3. Build & sign the Windows `.exe` (Tauri `tauri build`).
4. Fold in Arena Architect's command-export grid + arkbridge UWP install helpers.

## License
MIT (inherited). Cluster branding © Terror Fibercraft.
