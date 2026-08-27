# HUB — TerrorFibercraft-Admin

Master runbook for the Terror Fibercraft 1000x cluster admin console (desktop `.exe`,
forked from ArkNexusX). For the full business/cluster plan see the
`TerrorFibercraft_1000x` docs repo.

## Purpose
One desktop app for cluster admins to: sculpt custom caves/terrain, manage Nitrado
servers, send RCON commands, and run the community Discord bot — pre-loaded with the
Terror Fibercraft setup (Cluster ID `TerrorFibercraft1000x`, gamertag `TerrorFibercraft`,
1000x rates, Xbox+MS-Store ASE).

## Stack
- **Tauri** (Rust core + React webview) → produces the Windows `.exe`.
- **Python sidecar** → admin modules (no in-game automation; API/RCON only).
- **Upstream**: `ArkNexusX` (remote `upstream`). Player-automation crates are retained
  as a generic desktop toolkit but are NOT the supported product.

## Daily admin flow
1. `python sidecar/admin/tf_admin.py doctor` — verify tokens/deps.
2. `caves` — build/apply custom-cave terrain (admin-only; exploit if player-used).
3. `rcon` / `nitrado` — live server control & config push.
4. `discord` — run the community bot (slash commands).

## Cluster definition
`cluster/cluster.json` + `Game.ini` / `GameUserSettings.ini` (real, drop-in Nitrado config).
Maps: 11 (incl. free ASE The Center + Lost Island). Astraeos excluded (ASA-only DLC).

## 2026 facts baked in
- Host MUST be Nitrado for MS-Store ASE clustering.
- Arkon does NOT support ASE on Nitrado → use BattleMetrics + this console.
- RMT of items banned by ARK Code of Conduct → donations only, no pay-to-win.
- Nitrado 2026 ≈ $1/slot; 70-slot ≈ $60–70/mo.

## Phase 2
React admin panels, `admin` Rust modules wrapping the sidecar, signed `.exe` build,
Arena Architect command-export grid, arkbridge UWP helpers.
