# 09 — Marketplace & Plugins

## Purpose

The Marketplace distributes and manages automation packages — NexusScripts, macros, agents, vision layout templates, and knowledge packs — to and from the community. Plugins are sandboxed units of extensibility with declared capabilities, versioning, and signature validation.

## Package Model

```json
{
  "manifest": {
    "id": "com.nexusx.farmer-metal-rush",
    "name": "Metal Rush Farmer",
    "version": "1.2.0",
    "lang": { "nexus": "1" },
    "author": "someUser",
    "capabilities": ["input", "screen", "kb:read"],
    "assets": ["scripts/farm.nexus", "macros/deposit.macro.json", "templates/hud.json"],
    "deps": [ { "id": "com.nexusx.toolbox", "version": ">=1.0" } ],
    "license": "MIT",
    "signature": "base64...",
    "hash": "sha256...",
    "doc_url": "https://...",
    "screenshots": []
  }
}
```

## Capabilities

- Enumerated, coarse-grain grants: `input`, `screen`, `network`, `file:read`, `file:write`, `process`, `device`, `kb:read`, `kb:write`, `telemetry`.
- Capabilities are declared in the manifest and **enforced at runtime** by the sandbox (doc 03) and Input/Vision layers (docs 01/04).
- A package **cannot** grant itself a capability the installer hasn't approved. The install dialog shows the full capability list with a "why" explanation.
- `kb:write` and `network` are high-risk; default to disabled for unvetted packages.

## Validation & Trust

- **Signing**: packages signed by Nexus Key; community packages signed by authors holding a registered key. Client verifies signature chain.
- **Review tiers**:
  - `official` (Nexus-signed, CI-tested).
  - `curated` (community, manually reviewed + hash-pinned).
  - `community` (signed author, sandboxed, high-risk caps default-off).
  - `local` (user-authored, full trust to the user).
- **Static analysis**: `nexus check` runs on install — lint, capability-vs-code scan, resource-limit conformance, liveness check (no unbounded loops).
- **Reputation**: votes, usage counts, failure reports (from telemetry) affect discovery ranking but never override safety.

## Install & Sandboxing

1. Download → verify signature + hash → verify dep graph.
2. Static analysis → capability report shown to user → confirm.
3. Extracted into `~/.nexusx/packages/<id>/<version>/` (per-version, immutable).
4. Runtime resolution: NexusScript VM (03) applies the package's capability set; macros run via Macro Engine (02) with package-level rate limits; agents run under Agent Framework (05) with the package's grant scope.
5. **Update**: check `deps` compat, run `nexus check` on new version, keep old version rollback-able.

## Publishing (user-side)

- Packager CLI: `nexusx publish build/` → validates, signs (if key registered), uploads to hub.
- **Hub API** (Rust server, optional self-host): search, download, votes, counters, moderation.
- Community shares via signed `.nexusx` bundles (one file) when not using the hub.

## Update & Security Concerns

- **Supply-chain**: deps are pinned; `deps` resolution is exact-version or caret per policy; hash-pinned lockfile stored.
- **Revocation**: a signed revoke list is shipped with updates; malicious packages are blocked client-side.
- **No silent auto-update** of community packages; notify + diff preview.
- **Data isolation**: packages cannot read each other's persisted data except through explicit `kb` or `file` grants they share.

## Plugin Host (extensibility beyond scripts)

- Rust plugins via a stable ABI (`nexusx_plugin::Plugin`) with callbacks: `on_tick`, `on_event(Event)`, `on_frame_hint()`, `on_install/on_uninstall`.
- Compiled plugins get the same capability enforcement; they are dlopen'd with a capability-limited init.
- Plugin lifecycle is managed by the Desktop Shell (doc 13); crashes are contained to a worker subprocess.

## API Surface

```rust
impl Marketplace {
    fn search(&self, q: &str, filter: Filter) -> Result<Vec<PackageSummary>>;
    fn install(&self, id: &str, version: Option<Version>) -> Result<InstallHandle>;
    fn uninstall(&self, id: &str) -> Result<()>;
    fn list(&self) -> Vec<InstalledPackage>;
    fn update_all(&self, policy: UpdatePolicy) -> Result<UpdateReport>;
    fn revoke(&self, ids: &[String]) -> Result<()>;   // applied from revoke list
    fn local_build(&self, dir: PathBuf) -> Result<Package>; // for packager CLI
}
```

## Related Docs

- Scripts executed by **NexusScript VM** (03); input gated by **Input Engine** (01).
- Agent packages run under **Agent Framework** (05); telemetry feeds ranking + **Self-Improvement** (10).
- Knowledge packs write into **Knowledge DB** (07); templates used by **Vision Pipeline** (04).
