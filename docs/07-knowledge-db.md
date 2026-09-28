# 07 — Knowledge Database

## Purpose

The Knowledge Database (KB) is the encyclopedia of ARK facts NEXUS uses to plan and act: tames, resources, recipes, crafting, breeding, mutations, bosses, maps, and the user's own world data. It is a local SQLite database with a versioned schema, updatable from a bundled dataset and from community/curated packs (doc 09).

## Data Categories

### 1. Encyclopedia (static, curated)
- **Creatures**: base stats, growth rates, taming method (KO/preferred kibble/narcotics), preferred foods, torpor, rarity, habitats, weight capacities, gather capabilities.
- **Resources & Nodes**: node types, tool/dino multipliers, locations per map (weighted coordinates + confidence), respawn timing classes.
- **Crafting**: recipes (item → inputs × amounts), unlock levels/engrams, smithy/fabricator tables.
- **Building**: structure types, dimensions, snap behavior, materials.
- **Bosses / Events**: requirements, rewards, difficulty variants, recommended tames/gear.
- **Maps**: spawn regions, biome tables, supply drop schedules.

### 2. Breeding & Mutation tables
- Base stats per species; mutation chance formulas (per-* settings from server config).
- **Mutation tracker** input table: parent stats, lineage, observed mutations; output: predicted offspring ranges and validation.
- Imprint intervals and maturation durations per species.

### 3. User/World data (dynamic, written at runtime)
- Owned tames, their stats, location, lineage.
- Base locations, storage inventories (polled), supply of resources.
- Node hotspots discovered by agents/scouts.
- Layout templates (tagged UI layouts for Vision).
- Personal economy (what we farm, what we need).

## Schema (core tables)

```sql
creatures(id, class, name, map, category, taming_kind, base_stats_json, ...)
creature_gather(id, creature_id, resource_id, efficiency)
recipes(id, item_id, outputs_json, inputs_json, station, engram_level)
resources(id, class, name, tool_mult_json, dino_mult_json, weight)
node_locations(id, resource_id, map, x, y, z, confidence, source)
mutations(id, species, stat, bonus, chance, notes)
my_tames(id, class, name, stats_json, location, lineage_json, updated_at)
storage_inventory(id, container, item, count, updated_at)
world_events(id, type, payload_json, ts)
layout_templates(id, game, version, template_json, tagged_by, ts)
```

## Access Patterns

### Rule/plan lookup (deterministic)
- `kb.best_dino_for(resource)` → sorted by gather efficiency + availability.
- `kb.recipe_for(item)` → input list; check against inventory.
- `kb.taming_plan(creature)` → food, narcotics, timing estimate.

### Vision-augmented reads
- Node location table + live `VisionQuery` merges: use KB coordinates as priors, live vision as confirmation.
- Breeding: combine KB maturation formula with live HUD maturation % to compute `ready_at`.

### Decision Engine integration
- KB tables feed the cost model (doc 08): resource yields, distances, craft times.
- Knowledge freshness: KB entries carry `confidence` + `last_updated`; stale data lowers decision confidence.

## Bundling & Updates

- **Baseline pack** ships with the app (`assets/kb/` as SQL seed + JSON fixtures).
- **Update channel**: curator-signed packs; marketplace provides them (doc 09).
- Versioning: `kb_version` row; migrations applied on app update.
- Community submissions go through validation (schema + sanity checks) before curation.

## Local authoring (power users)

- A KB Editor (frontend, doc 14) supports adding user species/tables for modded content.
- User entries override baseline with higher priority; all entries keep `source` and `ts`.

## Query API

```rust
impl KnowledgeBase {
    fn query<T: Deserialize>(&self, sql: &str, params: &[Value]) -> Result<Vec<T>>;
    fn creature(&self, class: &str) -> Result<Option<Creature>>;
    fn best_dino_for(&self, resource: &str) -> Result<Vec<Candidate>>;
    fn taming_plan(&self, class: &str) -> Result<TamingPlan>;
    fn recipe(&self, item: &str) -> Result<Option<Recipe>>;
    fn node_hotspots(&self, map: &str, resource: &str) -> Result<Vec<Node>>;
    fn record_my_tame(&self, t: MyTame) -> Result<()>;
    fn maturation_eta(&self, species: &str, percent: f64) -> Result<Duration>;
}
```

## Data Hygiene

- KB writes from agents are guarded by schema + sanity checks (e.g., coordinates must be within map bounds, counts non-negative).
- Periodic compaction; secrets never stored here (see doc 13).
