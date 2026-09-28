# 03 — NexusScript VM

## Purpose

NexusScript is the scripting language of ARK NEXUS X. It lets power users, agents, and marketplace scripts express automation as imperative programs with access to vision, inventory, OCR, and decision utilities — all inside a sandboxed, capability-limited bytecode VM written in Rust.

## Language Design (v1 surface)

```nexus
# Farmer.nexus  — example
import ark.*
import vision.*

name "Metal Run"

config {
  max_runs: 5,
  timeout_s: 3600,
  require: ["pick", "metal_location"],
}

run(mount, location) {
  mount_ride(mount)
  navigate_to(location)          # built-in pathfinding/waypoint nav
  repeat max_runs {
    let node = vision.find_nearest("metal_node")
    break unless node
    approach(node, dist: 2.0)
    attack(hold_ms: 400)
    wait_for_hud("weight", < 80%)          # vision/OCR condition
    harvest_ground()
    wait(500ms)
  }
  return_to_base()
  deposit_all("storage")
  log("done: runs=", max_runs)
}
```

### Core constructs
- `run(params) { ... }` — entry; params bound by caller (agent, scheduler, user).
- Statements: `let`, `if/else`, `repeat N { }`, `while cond`, `break`, `return`, `wait`, `log`.
- **Built-in namespaces**:
  - `ark.*` — tames, crafting, inventory, buildings, waypoints.
  - `vision.*` — `find()`, `wait_for()`, `read_text()`, `is_on_screen()`, `find_dino(class)`.
  - `input.*` — `key/click/move/axis` (always routed through Input Engine).
  - `macro.*` — call and compose recorded macros.
  - `state.*` — read the blackboard (doc 05) and telemetry.
  - `decide.*` — bounded LLM/rule queries via the Decision Engine (doc 08).
- Types: `i64`, `f64`, `bool`, `str`, `vec`, `map`, `nil`. No pointers/unsafe.

## Compiler & VM

1. **Lex/parse** → AST (tree-sitter grammar mirrors the Rust parser for IDE support).
2. **Type check** (optional strict mode) → annotate.
3. **Compile** → flat instruction list.
4. **Execute** on a stack-based VM with an explicit `StackFrame` per call.

### Sandboxing
- **Capability grants** declared in a manifest (or `config { require: [...] }`): `network`, `file:read`, `file:write`, `input`, `screen`, `process`, `device`. Unlisted capability → compile/runtime error.
- **Resource limits**: max instructions, max wall-clock, max memory, max `repeat` iterations, call depth cap. All enforced inside the VM loop (no reliance on OS timeouts).
- **No FFI, no reflection, no dynamic dispatch to host** beyond the whitelisted builtins. Host functions receive `&mut VmContext` scoped by capability.
- **Determinism flag**: with `deterministic: true`, `rand`/LLM calls are rejected so replays are reproducible.

## Host ↔ VM Bridge

Builtins are implemented as Rust fns with a stable ID:

```rust
struct Builtin {
    id: u32,
    min_arity: usize, max_arity: usize,
    cap: Capability,
    f: fn(&mut VmContext, &[Value]) -> Result<Value, VmError>,
}
```

`VmContext` provides: Input Engine handle, Vision API, Blackboard, telemetry sink, and a deadline clock. Every builtin call logs its args/result (sanitized) to telemetry.

## Tooling

- **CLI**: `nexus run script.nexus`, `nexus check script.nexus`, `nexus fmt`, `nexus repl`.
- **Editor support**: tree-sitter grammar → VS Code extension with hover docs, inline telemetry (shows "this line ran 3.2s ago with these values").
- **Compilation targets**: both "source" (portable) and "bytecode blob" (signed, distributed via marketplace).

## Versioning & Migration

- Language version in the bytecode header (`NVME<major>.<minor>`).
- Backwards-incompatible builtin changes bump major; `nexus check` warns on deprecated symbols.
- Marketplace scripts pin the language version they were built against.

## Safety Model

Three nested trust boundaries:
1. **User scripts** — full grants they explicitly confirm.
2. **Marketplace scripts** — manifest-granted, sandboxed, no silent privilege escalation; reviewed hashes (doc 09).
3. **Agent-generated scripts** — generated code is always re-validated by `nexus check` with the agent's grant set before execution; high-risk operations require confirmation when not in Autonomous mode.

## Relationship to Other Docs

- Sends input via **Input Engine** (01), can invoke **Macros** (02).
- Reads **Vision** (04) and **Blackboard** (05).
- Uses **Decision Engine** (08) for `decide.*` queries.
- Scripts ship through **Marketplace** (09), are tuned by **Self-Improvement** (10), and run under **Scheduler** (06).
