# Spawn-Command Cookbook — Terror Fibercraft 1000x
# Admin-only custom cave / sculpt recipes (NOT a player exploit — see rules)

Every recipe below is a `cheat spawnactor` batch produced by
`cave-spawn-generator.py`. Commands are ordered left→right, bottom→top so a
single straight run drops a clean wall. Pick a blueprint, stand where the wall
should appear, face the gap, and paste.

Blueprint quick-ref:
  tribute_red / tribute_blue / tribute_green  (Tribute Terminals — confirmed)
  watervein                                  (Water Well shell — confirmed)
  # Fallbacks: City Terminal -> cheat summon primalstructure_cityterminal_bp_c
  #             Loadout Mannequin -> cheat gfi LoadoutDummy 1 0 0

Wall presets (cm, 400 = 1 wall unit):
  crouch 100×200 · stego 400×600 · dino 800×1600 · behemoth 2800×4800

=====================================================================
1) TELEPORT TO A COORD
=====================================================================
  python cave-spawn-generator.py convert --map ragnarok --lat 30.2 --lon 32.8
  -> prints: cheat setplayerpos -225320 -259380 0
  Set Z (altitude) to just above ground, then `cheat fly` down to the seam.

=====================================================================
2) CAVE ENTRANCE WALLS (seal / shape an existing cave mouth)
=====================================================================
# Crouch-only kill corridor  (5 wide × 4 tall, crouch hole in the middle)
  python cave-spawn-generator.py gen --mode wall --cols 5 --rows 4 --hole crouch --blueprint tribute_red

# Stego-height gate  (7×5, stego hole)
  python cave-spawn-generator.py gen --mode wall --cols 7 --rows 5 --hole stego

# Dino-gateway (Rex/Spino blocked, flyer enters)  (9×6, dino hole)
  python cave-spawn-generator.py gen --mode wall --cols 9 --rows 6 --hole dino

# Behemoth breach (flyers + big tames)  (11×7, behemoth hole)
  python cave-spawn-generator.py gen --mode wall --cols 11 --rows 7 --hole behemoth

# Underwater entrance — spawn while swimming, seal with dino hole
  python cave-spawn-generator.py gen --mode wall --cols 9 --rows 6 --hole dino --zstart -400

=====================================================================
3) SEALED BASE SHELL (BOX) — for plateaus, islands, ruins courtyards
=====================================================================
# 9×6 box with a behemoth front gate, floor + ceiling
  python cave-spawn-generator.py gen --mode box --cols 9 --rows 6 --depth 9 \
        --hole behemoth --floor --ceiling --blueprint watervein
# Run each of the 4 labelled walls while facing N / E / S / W.

# Small plateau box (5×4, dino gate, no floor/ceiling) — e.g. Pride Rock
  python cave-spawn-generator.py gen --mode box --cols 5 --rows 4 --depth 5 --hole dino

=====================================================================
4) FLOATING PLATFORM / CEILING — for floating islands & sky bases
=====================================================================
# 8×8 floor grid 4m in front of you
  python cave-spawn-generator.py gen --mode platform --depth 8 --cols 8 --blueprint tribute_blue
# Then add a rail wall at each edge with mode wall (floating-island recipe).

=====================================================================
5) NON-CAVE SCULPT RECIPES (from custom-caves-manifest.md § Sculpt-Ready)
=====================================================================
# canyon-choke  (e.g. Central Canyons 50,50 / Ragnarok Canyon 39.9,45)
#   wall across the mouth + dino gate on the only path
  python cave-spawn-generator.py gen --mode wall --cols 9 --rows 6 --hole dino

# ruins-castle plug  (e.g. Cat Castle 43.5,19.2 / Marble Hills 90,88.1 / Forburg 31.8,65.9)
#   close the 1–2 gaps; tiny opening -> crouch rat hole
  python cave-spawn-generator.py gen --mode wall --cols 3 --rows 3 --hole crouch
  python cave-spawn-generator.py gen --mode wall --cols 5 --rows 4 --hole stego

# cliff-hollow  (e.g. Hidden Lake choke 22.5,69.5 / Frozen Cliffs 31.9,9 / Waterfall 82.1,79.8)
#   back-fill the rock with a wall, leave a stego/dino gap for the base door
  python cave-spawn-generator.py gen --mode wall --cols 7 --rows 5 --hole stego
  python cave-spawn-generator.py gen --mode wall --cols 9 --rows 6 --hole dino

# plateau-island  (e.g. Herbivore Island 83.7,84.4 / Floating Island 41,28 / Massive Plateau 66.8,34.5)
  python cave-spawn-generator.py gen --mode box --cols 9 --rows 6 --depth 9 --hole dino --floor

# floating-island  (Crystal Isles 48.4,75.3 / The Center 41,28)
  python cave-spawn-generator.py gen --mode platform --depth 8 --cols 8
  python cave-spawn-generator.py gen --mode wall --cols 9 --rows 3   # rail, no hole

# uw-pocket  (Fjordur Hidden Grotto 39.9,31.6 / Lost Island Shipwreck)
  python cave-spawn-generator.py gen --mode wall --cols 9 --rows 6 --hole dino --zstart -600

=====================================================================
6) MANUAL ONE-OFF (relative to you: forward / right / up, in cm)
=====================================================================
  cheat spawnactor "Blueprint'/Game/PrimalEarth/Structures/TributeTerminal_Red.TributeTerminal_Red'" 400 0 0
  # 400cm in front, 0 right, 0 up. Negative Y = left, negative Z = down.

=====================================================================
7) CLEANUP
=====================================================================
  cheat DestroyAll <ClassName>        # remove a mis-placed shell type
  admin demolish (crosshair)          # remove individual pieces
  save a screenshot + the exact lat/lon for the cluster "admin base spots" archive.
