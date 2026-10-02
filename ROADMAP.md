# Roadmap / План развития

No stable release exists. Phase gates are evidence-based, not version promises.

## v0.1 — Reliable single-agent Creative builder

- Implemented foundations: negotiated capabilities, bounded transport, priority controls, resumable checkpoints/world reconciliation, deterministic interaction candidates, property verification, bounded local repair and owned temporary access.
- Implemented performance pass: Creative speed policies, raw-plan-independent ordering, position reuse/local movement, bounded tick-aware batches, adaptive component repair/final reconciliation, aggregate metrics and master-volume controls. 64-block LIVE tests measured FAST at 2.06× baseline throughput; full-house acceptance remains incomplete. See [measurements](docs/PERFORMANCE.md).
- Six version-specific artifacts build; see [compatibility evidence](docs/COMPATIBILITY.md). No full runtime-supported version yet.
- Fixed-reference demonstration achieved: the 1,243-cell Enderman passed physical construction world validation and separate saved-world inspection with three views/client exit 0. The original post-build camera failure remains recorded. Next gates are broader stateful/access/stability acceptance; the house remains a separate failed access/cleanup regression that this PASS cannot upgrade.
- Verify directional/stateful placement and navigation/fall guards in-game across each target.
- Improve access planning for obstructed interiors and upper floors; current bounded ramps/platforms are not a general scaffold planner.
- Guarded cleanup now rechecks actual arrival/retreat and game-thread block preconditions,
  own footing/body and immediate danger per breaking tick; confirmed ownership changes
  checkpoint immediately. General scaffold/sole-exit topology remains a separate gate.
- Add a high-level AI provider implementation with schema validation; the `IntentProvider` boundary and deterministic fallback exist.
- Add richer route constraints and Baritone event-based failure reasons.
- Current continuity pass: global WorkZone/dependency scheduling, facade completion,
  atomic fsync checkpoints, region-scan resume, shared phase access and bounded stale
  route recovery. [Scheduler](docs/SCHEDULER.md) remains experimental until full live acceptance.

## v0.2 — Editing and references

- Semantic design diffs for “make the towers taller” and material/entrance/floor edits.
- Multi-image and schematic ingestion with replica and engineer modes.
- Component transforms and partial validation/rebuild.

## v0.3 — Engineering

- Reusable versioned redstone components.
- Circuit/mechanism simulation, build, test, diagnose, repair, and retest loop.
- Farms, sorters, piston doors, storage, and flying-machine primitives.

## v0.4 — Survival Agent

- [Needs/food/health](docs/SURVIVAL.md), inventory/containers/equipment, defensive
  behavior, resource gathering/crafting/logistics and isolated Elytra/navigation extensions.
- Critical threats interrupt/checkpoint builds; fresh safety observation precedes resume.
  Architecture specifications do not imply autonomous Survival currently works.

## v0.5 — BlockMind Swarm

- [Coordinator/task board](docs/SWARM.md), structured worker capabilities/heartbeats,
  dependency graph, shared hazards/project memory, fenced region leases, failure recovery,
  logistics and resource reservations. Workers keep contiguous local work.
- Model tests first, then real cooperative clients on owned/authorized worlds.

## v0.6 — BlockMind Launcher

- Worker lifecycle, acknowledged pause/stop/emergency controls, monitoring/dashboard.
- [ResourceGovernor](docs/RESOURCE_GOVERNOR.md): measured full-process RAM/CPU,
  system/browser reserves, aggregate budget, pressure handling and conservative AUTO capacity.
- 1/2/4/6 are requested caps, not guarantees. Never launch six full clients blindly.

## Later — General architect/engineer framework

- Stable adapter/provider APIs, a verified component ecosystem, multiple navigation backends, and documented integration contracts.
- Advanced multimodal/video reconstruction, reusable learned engineering components,
  larger autonomous projects; authorized stress tests with entity/update/TPS/MSPT aborts.

## Русское резюме

Сначала — надёжный одиночный Creative-строитель и полная живая приёмка. Затем новые
проекты/референсы, инженерия, Survival, Swarm и ресурсно-ограниченный Launcher.
Изображения/видео и большие автономные проекты идут после базовой надёжности.
Архитектурные документы не выдаются за работающие и проверенные игровые функции.
