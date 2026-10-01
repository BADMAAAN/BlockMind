# Roadmap

## v0.1 — Creative autonomous building

- Implemented foundations: negotiated capabilities, bounded transport, priority controls, resumable checkpoints/world reconciliation, deterministic interaction candidates, property verification, bounded local repair and owned temporary access.
- Implemented performance pass: Creative speed policies, raw-plan-independent ordering, position reuse/local movement, bounded tick-aware batches, adaptive component repair/final reconciliation, aggregate metrics and master-volume controls. 64-block LIVE tests measured FAST at 2.06× baseline throughput; full-house acceptance remains incomplete. See [measurements](docs/PERFORMANCE.md).
- Six version-specific artifacts build; see [compatibility evidence](docs/COMPATIBILITY.md). No full runtime-supported version yet.
- Blocking milestone: finish and record the acceptance house using real player actions in a disposable Creative world, including controlled recovery, scaffold cleanup and final validation.
- Verify directional/stateful placement and navigation/fall guards in-game across each target.
- Improve access planning for obstructed interiors and upper floors; current bounded ramps/platforms are not a general scaffold planner.
- Add a high-level AI provider implementation with schema validation; the `IntentProvider` boundary and deterministic fallback exist.
- Add richer route constraints and Baritone event-based failure reasons.

## v0.2 — Editing and references

- Semantic design diffs for “make the towers taller” and material/entrance/floor edits.
- Multi-image and schematic ingestion with replica and engineer modes.
- Component transforms and partial validation/rebuild.

## v0.3 — Engineering

- Reusable versioned redstone components.
- Circuit/mechanism simulation, build, test, diagnose, repair, and retest loop.
- Farms, sorters, piston doors, storage, and flying-machine primitives.

## v0.4 — Video/reference reconstruction

- Temporal reference understanding after still-image reconstruction is reliable.

## v0.5 — Automated QA and repair

- Root-cause classification, localized repair plans, regression validation, and component confidence.

## v0.6 — Survival

- Resource location, acquisition, crafting, transport, food/equipment policies, and threat-aware planning.

## v1.0 — General architect/engineer framework

- Stable adapter/provider APIs, a verified component ecosystem, multiple navigation backends, and documented integration contracts.
