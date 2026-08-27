# Custom Caves Manifest — Terror Fibercraft 1000x
# Admin-only sculpted terrain toolkit (NOT a player exploit — see 04 rules: banned player terminal-wall exploit)

This manifest gives every cluster map's notable caves with **exact entrance coordinates**
(Lat/Lon), an **entrance-dimension classification** that admins use to pick a wall preset,
and a **sculpt tip** for building desirable raid/defense spots with floating terminal
structures (TributeTerminal / WaterVein / City Terminal / Loadout Mannequin).

Coordinate source: triangulated from ark.fandom.com/wiki/Coordinates, arkids.net,
segmentnext, gamesomg, kosgames, dotesports, destructoid (May–Aug 2026). When a value is
disputed between sources it is flagged `?`. ALWAYS confirm in-game with `getpos` before a
big sculpt. The XY→UE converter lives in `cave-spawn-generator.py convert`.

---
## How to read the "Entrance" column
| Tag | Meaning | Use preset (see spawn-command-cookbook.md) |
| --- | --- | --- |
| `crouch` | Gap requires crouch; no dino fits | `crouch` hole (1×1–1×2 cells) |
| `stego` | Small dino / stego height, blocks big tames | `stego` hole |
| `dino` | Dino-gateway sized (Rex/Spino blocked) | `dino` hole |
| `open` | Wide, flyers/big tames enter | full wall or `behemoth` hole |
| `uw` | Underwater entrance | spawn under water, seal with `dino`/`behemoth` |

Wall presets (cm, 400 = 1 wall unit): crouch 100×200 · stego 400×600 · dino 800×1600 · behemoth 2800×4800.

---
## THE ISLAND
| Cave | Artifact | Entrance (Lat,Lon) | Entrance | Sculpt tip |
| --- | --- | --- | --- | --- |
| Central Cave | Clever | 40.2, 46.6 | `crouch` (narrow, short) | line a crouch-only kill corridor |
| North West Cave | Skylord | 14.1, 13.9 | `crouch` (crouch corridors) | natural; add crouch funnel to artifact |
| Lower South Cave (Hunter) | Hunter | 85.3, 54.2 | `open` (medium dinos) | seal side passages with `dino` walls |
| North East Cave | Devourer | 8.9, 91.3 | `stego` (bear-sized) | block with `dino` to stop Rexes |
| Upper South Cave | Pack | 71.3, 57.2 | `stego` (medium) | `dino` gate as the only entry |
| Lava Cave | Massive | 74.1, 92.2 | `open` (medium) | `behemoth` breach for flyer raids |
| Swamp Cave | Immune | 64.8, 35.1 | `stego` | gas-mask room; `dino` seal |
| Snow Cave | Strong | 26.0, 29.0 | `open` (extreme, big) | `behemoth` entry, inner `crouch` maze |
| Caverns of Lost Faith | Brute | 54.4, 3.9 | `uw` | underwater `dino` seal → dry base |
| Caverns of Lost Hope | Cunning | 45.4, 95.0 | `uw` (extreme) | `behemoth` uw gate + inner maze |
| Tek Cave | Ascension | 43.0, 39.0 | `open` | (endgame; leave vanilla) |

## SCORCHED EARTH
| Cave | Artifact | Entrance (Lat,Lon) | Entrance | Sculpt tip |
| --- | --- | --- | --- | --- |
| Grave of the Tyrants | Crag | 28.2, 29.1 | `crouch` (low ceiling) | leave vanilla; natural dino block |
| The Old Tunnels | Gatekeeper | 58.8, 47.7 | `stego` (low-ceiling entry blocks Rex/Spino) | BEST PvP base shell — `dino` front gate only |
| Ruins of Nosti | Destroyer | 78.4, 76.1 | `open` (broad) | `behemoth` breach, inner `crouch` |
| Oasis Cave | — | 73.9, 40.3 | `uw` (water source) | `dino` uw seal → safe water base |
| Trench Cave | — | 59.1, 16.4 | `open` | `behemoth` entry, note spot |
| Blue Cave (= Crag alt name) | Crag | 28.4, 29.4 | `crouch` | see Grave of Tyrants |

## RAGNAROK
| Cave | Artifact | Entrance (Lat,Lon) | Entrance | Sculpt tip |
| --- | --- | --- | --- | --- |
| Fallen Redwood (3 entr.) | — | 34.2, 79.1 | `open` | pick 1 entry, `dino` the other 2 |
| Jungle Dungeon | Hunter | 18.2, 28.4 | `stego` | `dino` gate as sole entry |
| Carnivorous Caverns | Cunning/Immune | 17.7, 42.4 | `open` | `behemoth` breach, `crouch` inner |
| Monkey Temple Ruin | Strong (ASA moved) | 24.8, 24.7 | `stego` | `dino` temple door |
| Ice Dungeon (2 entr.) | Pack | 31.3, 33.7 | `open` | seal 1, `behemoth` the other |
| Wyvern Trench / Scar | Strong | 69.1, 42.2 | `open` | leave flyer route; `dino` ground gate |
| Life's Labyrinth | Skylord/Clever/Massive/Devious | 51.6, 77.7 | `open` (puzzle) | leave vanilla maze |
| Sunken Ships | Devourer | 47.4, 2.3 | `uw` | `behemoth` uw gate |
| Pirate Cave | — | SW desert (≈20.4,24.0) | `uw` | `dino` uw seal → themed base |
| Glacier Cave | — | 30.3, 32.8 | `open` (buildable) | note base spot |
| Kamaka Cave | — | 22.7, 30.4 | `open` (buildable) | note base spot |
| Forbidden Grotto | — | 26.2, 27.0 | `open` (buildable) | note base spot |
| Kuri Cave | — | 24.1, 27.7 | `open` (buildable) | note base spot |
| Skellet Canyon Cave | — | 20.5, 29.1 | `open` (buildable) | note base spot |
| Metal Cave | — | 35.2, 24.3 | `open` (buildable: no) | leave resource node |

## VALGUERO
| Cave | Artifact | Entrance (Lat,Lon) | Entrance | Sculpt tip |
| --- | --- | --- | --- | --- |
| Spider Cave / The Lair | Strong/Immune/Pack | 74.2, 42.7 | `open` | `dino` front, inner `crouch` web maze |
| Lost Temple | Brute/Devourer | 46.8, 87.3 | `stego` (narrow) | `dino` door, secret-passage block |
| Crag (exclusive) | Crag | 34.2, 51.4 | `stego` (lava) | `dino` lava-room gate |
| Destroyer (disputed ?) | Destroyer | 81.2, 88.1 | `open` | verify; `behemoth` |
| Gatekeeper (Aberration trench) | Gatekeeper | 32.3, 92.4 | `open` (no fly) | `dino` trench entry, glow-pet room |
| Cunning (Snow) | Cunning | 15.4, 27.3 | `open` (cold) | `behemoth` breach |
| Skylord (disputed ?) | Skylord | 08.5, 81.3 | `open` | verify; `behemoth` |
| The Abyss (underground ocean) | — | central | `uw` | `dino` uw seal → hidden base |

## ABERRATION  (all underground — no sky; use Charge Light + Hazard Suit)
| Cave | Artifact | Entrance (Lat,Lon) | Entrance | Sculpt tip |
| --- | --- | --- | --- | --- |
| Old Railway Cave | Depths | 48.3, 27.2 (art 51.2,23.8) | `stego` (cliffs) | zip-line entry; `dino` rock gate |
| Hidden Grotto | Shadows | 55.2, 65.9 | `uw` (vertical shaft) | `dino` uw seal at shaft top |
| Elemental Vault (Red Zone) | Stalker | 81.0, 47.0 (art 91.7,51.3) | `open` (rad) | Hazard Suit room; `behemoth` |
| Surface entrance NW | — | 22.9, 23.2 | `open` | note fast-travel pillar |
| Surface entrance NE Green | — | 32.0, 71.3 | `open` | note |
| Surface entrance NE Blue | — | 46.9, 89.1 | `open` | note |
| Surface entrance SW Green | — | 64.7, 33.1 | `open` | note |
| Surface entrance SW Red | — | 88.5, 30.7 | `open` | note |

## EXTINCTION  (no classic caves — the Sanctuary City + domes ARE the buildable terrain)
| Location | Use | Coords | Entrance | Sculpt tip |
| --- | --- | --- | --- | --- |
| Sanctuary City (Great City) | spawn / base | 52.0, 48.1 | `open` | tapered towers; `dino` street gates |
| Desert Titan Cave | Desert Titan | 97.2, 90.2 | `open` | `behemoth` terminal gate |
| Forest Titan Cave | Forest Titan | 15.9, 50.5 | `open` | `behemoth` terminal gate |
| Ice Titan Cave | Ice Titan | verify in-game ? | `open` | `behemoth` terminal gate |
| The Trench | resource | UE 159805 16895 -44178 | `open` | `dino` side seals |
| City potential bases | base | see faq.thepackgaming Extinction | `open` | stacked balcony walls |

## CRYSTAL ISLES  (18 artifacts — pick caves per event)
| Cave | Artifact | Entrance (Lat,Lon) | Entrance | Sculpt tip |
| --- | --- | --- | --- | --- |
| Snow Biome Cave (2 entr.) | Strong | 31.1, 50.1 | `open` | seal 1, `behemoth` other |
| Waterfall Cave (2 entr.) | — | 32.0, 48.8 | `stego` | `dino` back entry |
| Floating Cave | — | 42.1, 74.8 | `open` | note sky-base |
| Beehive Cave (3 entr.) | — | 31.0, 31.2 | `open` | `dino` 2 of 3 |
| Mountain Side Cave (2 entr.) | — | 53.4, 33.6 | `stego` | `dino` gate |
| Spider Cave (2 entr.) | — | 33.1, 29.9 | `open` | web maze; `crouch` inner |
| Clever Cave (2 entr.) | Clever | 58.5, 33.2 | `open` | `behemoth` breach |
| Wyvern Cave | — | 75.7, 41.0 | `open` | leave wyvern route |
| Web Cave (2 entr.) | — | 33.9, 26.9 | `open` | `dino` 1 entry |
| Stalker Cave (2 entr.) | Stalker | 12.9, 25.1 | `uw` | `dino` uw seal |
| Depths Cave | Depths | 39.5, 15.1 | `uw` (via Beehive) | `behemoth` uw gate |

## FJORDUR
| Cave | Artifact | Entrance (Lat,Lon) | Entrance | Sculpt tip |
| --- | --- | --- | --- | --- |
| Devourer | Devourer | 3.5, 3.5 | `uw` (icy) | `dino` uw seal |
| Brute | Brute | 49.4, 14.2 | `stego` (gas) | `dino` gate |
| Massive | Massive | 71.7, 1.1 | `uw` (tunnel) | `behemoth` uw gate |
| Strong / Skylord | Strong/Skylord | 8.8, 24.5 | `open` (mountain) | `behemoth` breach |
| Hunter | Hunter | 3.2, 32.6 | `open` | `dino` gate |
| Pack / Clever | Pack/Clever | 21.2, 57.4 | `open` (lava) | `behemoth`, inner `crouch` |
| Shadows | Shadows | 10.0, 84.4 | `open` (waterfall) | `behemoth` |
| Stalker | Stalker | 56.9, 84.9 | `open` (Ravagers) | `dino` gate |
| Cunning | Cunning | 77.0, 65.5 | `uw` (half flood) | `behemoth` uw gate |
| Immune | Immune | 91.0, 78.0 | `open` (lava) | `behemoth` |
| Helm's Deep | — | 31.4, 65.2 | `open` | note base (pearls/crystals) |
| Glow Cave | — | 0.5, 88.5 | `open` (waterfall) | note base |
| Waterfall Cave | — | 61.9, 80.4 | `open` (2 entr, water) | `dino` 1 entry |
| Chitin Cave | — | 78.1, 29.0 | `open` (cozy) | note base |
| Large Bridge Cave | — | 9.9, 62.6 | `open` (big) | note base |

---
# SCULPT-READY NATURAL FEATURES (non-cave base spots)
The idea: many in-game locations are **not caves** but are natural dead-ends,
hollows, plateaus, slot canyons, floating islands, ruins or cliff cracks where a
*handful* of terminal walls turns an already-defensible nook into a sealed base.
Same rule as above — these are ADMIN terrain shells, not a player exploit.

## Feature-type tags (which preset to use)
| Tag | Natural shape | Shell recipe (see spawn-command-cookbook.md) |
| --- | --- | --- |
| `cliff-hollow` | Rock overhang / crack / waterfall behind-rock | back-fill with `wall`, leave a `stego`/`dino` gap |
| `canyon-choke` | Slot canyon / single land bridge | `wall` across mouth + `dino`/`behemoth` gate |
| `plateau-island` | Flat top, open air on all sides | `box` (4 walls; optional `--floor`/`--ceiling`) |
| `ruins-castle` | Ready-made walls with 1–2 gaps | `wall` to plug the gaps (often a `crouch`/`stego` rat hole) |
| `floating-island` | Sky platform | `platform` floor + `wall` rail at edges |
| `uw-pocket` | Submerged nook / grotto | `wall` spawned underwater, `dino`/`behemoth` gate |

> For every feature below: `python cave-spawn-generator.py convert --map <map> --lat L --lon O`
> to teleport, then build while facing the gap. `?` = confirm with arkids.net/locations.

## THE ISLAND
| Feature | Coords (Lat,Lon) | Type | Shell recipe |
| --- | --- | --- | --- |
| Hidden Lake (single choke) | 22.5, 69.5 (choke 70,40 / 17.9,72.5) | `canyon-choke` | `wall` + `dino` gate on the land bridge |
| Herbivore Island | 83.7, 84.4 (85,85) | `plateau-island` | `box` 9×6, seal the beach landing with `dino` |
| Frozen Cliffs (thin cliff to ocean) | 31.9, 9.0 | `cliff-hollow` | `wall` across the land side, `crouch` rat hole |
| Pride Rock | 47.3, 77.8 | `plateau-island` | `box` small (5×4) |
| Redwood Plateau | 50, 50 | `plateau-island` | `box` 7×5 |
| Two Pillars (waterfall) | 42.6, 64.9 | `cliff-hollow` | `wall` behind falls, `stego` gap |

## THE CENTER
| Feature | Coords | Type | Shell recipe |
| --- | --- | --- | --- |
| Floating Island | 41, 28 | `floating-island` | `platform` 8×8 + `wall` rail |
| Castle Frostbite (ice ruins) | ice spires ~? | `ruins-castle` | plug gaps with `wall` |
| Island Oasis | 71, 52 | `plateau-island` | `box` |
| Ruins Retreat | 49, 51 | `ruins-castle` | plug gaps |
| Tropical Plateau | 30, 78 | `plateau-island` | `box` |
| Lava Island | 10, 74 | `plateau-island` | `box` + `behemoth` |

## SCORCHED EARTH
| Feature | Coords | Type | Shell recipe |
| --- | --- | --- | --- |
| Central Canyons (slot canyon) | 50, 50 | `canyon-choke` | `wall` + `dino` gate at mouth |
| Rocky Temple (cliffside) | 80.9, 40.8 | `ruins-castle` | plug the 1–2 openings |
| Flat Clifftop | 66, 61.2 | `plateau-island` | `box` |
| Mountaintop | 70.4, 27.5 | `plateau-island` | `box` |
| Green Obelisk basin | 30, 75 | `canyon-choke` | `wall` ring |

## RAGNAROK
| Feature | Coords | Type | Shell recipe |
| --- | --- | --- | --- |
| Herbivore Island | 8.7, 96.7 | `plateau-island` | `box`, `dino` landing |
| Ragnarok Canyon (cliffs/bridges) | 39.9, 45 | `canyon-choke` | `wall` + rat holes (95.5,39.9)(40.4,48.3)(38.9,45.4) |
| Ragnarok Falls (caves behind falls) | 41.2, 49 | `cliff-hollow` | `wall` behind falls, `stego` |
| Cat Castle (ready fortress) | 43.5, 19.2 | `ruins-castle` | plug gaps with `wall` |
| Fossil by the Lake | 20.9, 32.3 | `cliff-hollow` | `wall` under the rock, `dino` |
| Ruins on the Lake | 27.7, 28.8 | `ruins-castle` | plug |
| Castle on the Bridge | 43.5, 86.5 | `ruins-castle` | plug |
| Cliffside plateau (1 walkway) | 41.2, 28.9 | `plateau-island` | `box` |

## VALGUERO
| Feature | Coords | Type | Shell recipe |
| --- | --- | --- | --- |
| Marble Hills (castle + drawbridge) | 90, 88.1 | `ruins-castle` | plug drawbridge with `wall`/`dino` |
| Waterfall | 82.1, 79.8 | `cliff-hollow` | `wall` behind falls |
| Castle (small opening) | 79.4, 66.2 | `ruins-castle` | `crouch` rat hole |
| Redwood Forest Castle | 61.7, 11.0 | `ruins-castle` | plug |
| Green Obelisk jungle temple | 46.5, 86.9 | `ruins-castle` | plug |
| Jungle Castle (tunnel) | 37.5, 90.4 (tunnel 37.0,90.9) | `ruins-castle` | `crouch` tunnel |
| White Cliff Ruins | 83.6, 88.8 | `ruins-castle` | plug |
| Mountain Cliffs | 97.3, 84.3 | `cliff-hollow` | `wall` |
| Deinonychus cliffs | 92,89 / 67,92 | `cliff-hollow` | `wall` + `stego` |

## ABERRATION (blue/red zone hollows, no real caves)
| Feature | Coords | Type | Shell recipe |
| --- | --- | --- | --- |
| Waterfall Cliff | 42.0, 51.3 | `cliff-hollow` | `wall`, `dino` |
| Rock Ledge | 26.2, 48.8 | `cliff-hollow` | `wall` + `stego` |
| Mechanical ridge | 14.4, 41.4 | `cliff-hollow` | `wall` |
| Hidden hollow #1 | 50.7, 33.6 | `cliff-hollow` | `wall` + `crouch` |
| Hidden crack #2 | 57.3, 54.3 | `cliff-hollow` | `wall` + `crouch` |
| Hidden tower #4 | 24.2, 46.8 | `cliff-hollow` | `wall` + `stego` |

## EXTINCTION (ruined city = ready walls)
| Feature | Coords | Type | Shell recipe |
| --- | --- | --- | --- |
| Sanctuary City tower (bald eagle) | 52.0, 48.1 | `ruins-castle` | plug window with `wall` |
| Large tower top | 57.5, 58.4 | `plateau-island` | `box` on top |
| City ruins (general) | central | `ruins-castle` | plug gaps per building |

## CRYSTAL ISLES
| Feature | Coords | Type | Shell recipe |
| --- | --- | --- | --- |
| Floating Islands | 48.4, 75.3 / 48.8, 74.8 | `floating-island` | `platform` + rail |
| Massive Plateau | 66.8, 34.5 | `plateau-island` | `box` |
| Desert Plateau | 70.4, 45.8 | `plateau-island` | `box` |
| Cherry Blossom Pond hollow | 39.8, 60.6 | `cliff-hollow` | `wall` + `dino` |
| Volcano Falls obsidian | 51.3, 59.3 | `cliff-hollow` | `wall` |

## FJORDUR
| Feature | Coords | Type | Shell recipe |
| --- | --- | --- | --- |
| Forburg / Helm's Deep stronghold | 31.8, 65.9 | `ruins-castle` | plug gaps |
| Skarstind Village Mine (tiny entrance) | 71.4, 4.5 | `canyon-choke` | `wall` + `crouch` rat hole |
| Frozen Fortress (Rex-blocked entrance) | ~? | `ruins-castle` | plug with `dino` |
| Shimmering Halls | 12.2, 62.7 | `ruins-castle` | plug |
| Hidden Grotto (uw) | 39.9, 31.6 / 35,31 | `uw-pocket` | `wall` uw + `dino` |
| Snowglobe cliffside | 20.6, 8.7 | `cliff-hollow` | `wall` |
| Castle (choke + secret cave) | 31.0, 56.9 | `ruins-castle` | plug choke |
| Vanaheim waterfalls/overhangs | Vanaheim | `cliff-hollow` | `wall` + `stego` |

## REFERENCE-ONLY MAPS (not in the free cluster — toolkit coverage)
| Map | Notable sculpt-ready features |
| --- | --- |
| Lost Island | Abandoned Fort 42.6,55.1 (ruins plug); Waterfall Cave; Redwood Cliff; Lava Cave; Jungle Crouch; Shipwreck (uw-pocket) |
| Genesis Part 1 | Plateau 20,58.4; Bog/Volcanic lava-walled pockets (cliff-hollow); Best-base cave 25.9,26.0 |
| Genesis Part 2 | Eden ring cliffs (cliff-hollow); Sanctuary-style ruined platforms |
| Astraeos | **ASA-ONLY (paid DLC, $14.99) — does NOT exist on ASE.** Kept as ASA reference only; do not sculpt on the ASE cluster. (ASA coords: Bonfire Ridge 80.9,78.6; Forgotten Temple 69.9,9.6; Hall of Fame 5.7,65.7; Embercrest 10.3,77.1; Pyranthos desert Feb 2026.) |

---
## Workflow (per sculpt)
1. Pick the cave + desired defense from the table above.
2. Teleport to entrance: `python cave-spawn-generator.py convert --map <map> --lat L --lon O`
   → paste the printed `cheat setplayerpos ...` (set Z altitude to ~above ground, then `cheat fly` down).
3. Face the wall plane you want to build.
4. Generate the wall/floor/box with `python cave-spawn-generator.py gen ...` (see spawn-command-cookbook.md).
5. Paste the printed `cheat spawnactor ...` lines one-by-one (they are ordered left→right, bottom→top so a straight run drops a clean wall).
6. Demolish any floating overlap with `cheat DestroyAll` / admin demolish; save a blueprint photo.

> Rule reminder: these shells are ADMIN terrain only. Players using spawn/terminal walls to box
> bases or block paths is a bannable exploit per 04_CLUSTER_DESIGN/rules-code-of-conduct.md.
