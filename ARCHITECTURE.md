# Architecture

## Boundaries

### Minecraft Runtime / Fabric Adapter

`minecraft-mod/` is the body and sensor layer. It samples structured state, executes player-like interaction primitives on the client thread, observes their results, and reports them over the protocol. It owns no architectural planning logic.

The adapter deliberately does not use server commands or world-edit APIs. Direct world editing, if introduced for development, must live behind a separate capability that is disabled by default.

### BlockMind Core

`ai-core/` owns intent interpretation, semantic designs, deterministic geometry, build/project state, execution monitoring, validation, controls, and persistence. Its `MinecraftPort` and `NavigationProvider` interfaces make it usable with other clients, research environments, test simulations, or future bots.

The MVP `PromptInterpreter` is deterministic and narrowly recognizes a modern house request. Its interface is the seam for an LLM-backed interpreter; coordinates and geometry stay deterministic.

### Navigation / Execution

Core issues `NavigationGoal` values such as `GO_TO`, `APPROACH`, and `MOVE_TO_BUILD_POSITION`. The Fabric adapter implements the same conceptual boundary in Java. `SafeNavigationProvider` performs a basic target preflight and delegates accepted goals to `BaritoneNavigationProvider`.

Baritone types never cross the provider interface or wire protocol.

## Agent loop

```text
PERCEIVE → UPDATE WORLD → SELECT OBJECTIVE → PLAN
   ▲                                      │
   │                                      ▼
VERIFY ← OBSERVE RESULT ← ACT ← NAVIGATE
   │
   └── mismatch → retry / scaffold / fail for replanning
```

Every mutation is followed by a world observation. A successful API return alone is insufficient.

## Semantic construction

A `Design` contains named `StructureComponent` objects (`foundation`, `floor_1.wall_north`, `roof`, `pool`) and bounding boxes. `ModernHouseGeometry` expands those components into sorted `BuildOperation` values and exact material counts. This allows future edits to target a component instead of treating a build as an anonymous block cloud.

## Safety invariants

- Destructive operations are rejected outside `BuildPlan.approved_area`.
- Stop makes the queued core loop terminal and cancels navigation.
- Fabric emergency stop clears its queue, cancels navigation, and releases movement keys.
- Basic navigation preflight rejects lava, fire, magma, void-level targets, and drops over three blocks.
- The protocol listens on loopback by default and is intentionally unauthenticated; do not expose it to a network.
- Destructive scaffold cleanup is logged.

## Protocol

`protocol/0.1` is newline-delimited JSON with request IDs. It separates structured observations from action requests and results. Unknown optional fields are forward-compatible; a major version mismatch is rejected. See [protocol/README.md](protocol/README.md).

## Persistence and future modules

Project files preserve the request, interpreted design, semantic components, bounds, material counts, operation states, failures, modifications, and validation. Planned reusable libraries should be data/modules below stable interfaces:

```text
components/
  architecture/
  redstone/
  farms/
  storage/
  piston/
  flying_machines/
  logic/
  displays/
```

Survival acquisition will precede building through a resource provider; it does not require changing geometry or project models.
