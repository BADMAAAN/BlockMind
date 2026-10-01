# Architecture

## Boundaries

### Minecraft Runtime / Fabric Adapter

`minecraft-mod/` is the body and sensor layer. It samples structured state, executes player-like interaction primitives on the client thread, observes their results, and reports them over the protocol. It owns no architectural planning logic.

The adapter deliberately does not use server commands or world-edit APIs. Direct world editing, if introduced for development, must live behind a separate capability that is disabled by default.

### BlockMind Core

`ai-core/` owns intent interpretation, semantic designs, deterministic geometry, build/project state, execution monitoring, validation, controls, and persistence. Its `MinecraftPort` and `NavigationProvider` interfaces make it usable with other clients, research environments, test simulations, or future bots.

The MVP `PromptInterpreter` is deterministic and narrowly recognizes a modern house request. `IntentProvider` is an injected interface for local, cloud or deterministic interpreters; no cloud SDK or API key is required. Geometry stays deterministic. Vision, schematic/video inputs, and replica/engineer modes remain future modules.

### Navigation / Execution

Core issues `NavigationGoal` values such as `GO_TO`, `APPROACH`, and `MOVE_TO_BUILD_POSITION`. The Fabric adapter implements the same conceptual boundary in Java. `SafeNavigationProvider` performs target and live-motion checks. A local provider handles flat one/two-block adjustments, falling back to `BaritoneNavigationProvider` for elevation, obstacles and longer routes. Already-reached goals and reusable interaction positions do not create new paths; stale complete paths are not cached across world mutations.

Baritone types never cross the provider interface or wire protocol. Shared Java `GameAccess` normalizes positions, observations, interaction and movement release. Version-specific bindings implement it; see [the exact compatibility matrix](docs/COMPATIBILITY.md). This preserves the existing architecture rather than duplicating the entire mod per patch.

## Agent loop

```text
PERCEIVE → UPDATE WORLD → SELECT OBJECTIVE → PLAN
   ▲                                      │
   │                                      ▼
VERIFY ← OBSERVE RESULT ← ACT ← NAVIGATE
   │
   └── mismatch → reposition / bounded retry / scaffold / local clear / fail
```

Verification is adaptive: SAFE, Survival, stateful, destructive, temporary and retry operations retain immediate block/property checks. Compatible simple Creative cubes use bounded, tick-progressive batches in NORMAL/FAST/MAX. `issued` is provisional, not observed success. Component/layer checkpoints return compact mismatches; strict local repairs are revalidated before completion. An authoritative full-region final scan can trigger one bounded strict repair pass (up to 256 mismatched operations) and another scan. Extra unowned blocks are reported, never blindly deleted. A successful API return alone is insufficient.

Candidate positions are generated deterministically and filtered by local observation bounds, ground support, collision, reach, sampled visibility and hazards. The adapter additionally checks actual raycast, placement context and player collision. Stateful block prediction uses Minecraft's own placement-state method, not a generic facing guess. Java property-matcher tests are not in-game placement tests.

## Semantic construction

A `Design` contains named `StructureComponent` objects (`foundation`, `floor_1.wall_north`, `roof`, `pool`) and bounding boxes. `ModernHouseGeometry` expands those components into sorted `BuildOperation` values and exact material counts. This allows future edits to target a component instead of treating a build as an anonymous block cloud.

`BuildPlanOptimizer` derives an execution ordering without changing raw geometry. Simple runs use component-local layer/serpentine sweeps and reachable clusters. Explicit dependencies and sensitive operations are barriers. Independent supported cubes use far-to-near ordering to avoid closing the placement ray. Repeated placement positions and active material slots are reused. Shared access platforms may survive until phase cleanup, while per-target supporting scaffolds are removed when no longer needed.

`ExecutionConfig` persists speed, batch/reach, navigation and audio policy in the project. Minecraft's master volume is saved and temporarily muted through game APIs, then restored on finish, stop, disconnect or world loss unless permanent mute was explicitly selected. Network I/O never changes volume or game state. `PerformanceMetrics` aggregates phase timers/counters plus adapter rotation, selection, inspection, placement and navigation timings. See [PERFORMANCE.md](docs/PERFORMANCE.md) for scope, overlap and measured evidence.

## Safety invariants

- Place, break and interact operations are rejected outside the approved region; temporary mutations use a separately tracked temporary region.
- Stop makes the queued core loop terminal and cancels navigation.
- Fabric emergency stop clears its queue and the remaining batch, cancels navigation, and releases movement keys. A client tick cannot be interrupted halfway through a synchronous call; at most the current 1/2/4-action slice or already-sent packets can have taken effect.
- Target and immediate predicted-movement checks reject lava, fire, magma, water routes without a drowning policy, low health, void-level targets, suffocation and drops over three blocks. These checks complement the navigation backend; they do not prove absolute safety.
- The protocol listens on loopback by default and is intentionally unauthenticated; do not expose it to a network.
- Destructive scaffold cleanup is logged.

## Protocol

Protocol `0.1.0` is newline-delimited JSON with stable request IDs and negotiated adapter metadata/capabilities. Exact protocol mismatch is rejected. Priority controls bypass normal action serialization. Bounded network queues run on background threads; all game state access and queue consumption happen on the client tick thread. Disconnect cancels pending work, releases movement, invalidates approvals and requires new handshake/reconciliation. There is no automatic mutation replay. See [protocol/README.md](protocol/README.md).

## Persistence and future modules

Project files preserve request, semantic design, expected block properties, bounds, material counts, operation states/retries, dimension, initial-region baseline, owned temporary blocks, failures and validation. Atomic checkpoints are written before attempts and after completed operations. Resume loads the project and rereads expected world states instead of trusting completed flags. Pre-existing conflicts are not automatically destroyed. Temporary cleanup verifies owned block IDs; general terrain repair and crash-proof exactly-once mutations are not claimed. Planned reusable libraries should be data/modules below stable interfaces:

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
