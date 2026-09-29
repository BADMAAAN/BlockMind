# BlockMind

[English](README.md) | [Русский](README_RU.md)

> **An open-source autonomous AI agent framework for Minecraft.**
>
> Give BlockMind a goal. It designs, plans, navigates, builds, observes, verifies, and eventually repairs its own work inside Minecraft.

![Status: Early Development](https://img.shields.io/badge/status-early_development-orange)
![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)
![Minecraft: 1.21.11](https://img.shields.io/badge/Minecraft-1.21.11-62b47a)

> [!IMPORTANT]
> BlockMind is **experimental software under active development**. Automated simulation tests pass and the Fabric adapter compiles, but the complete live Minecraft workflow has not yet been verified by a person. There is no stable release and no production-readiness claim.

## What is BlockMind?

BlockMind is intended to become an autonomous Minecraft architect, builder, and engineer. Instead of scripting every movement or supplying every block coordinate, a user describes an objective and the agent turns it into a semantic design, deterministic geometry, an executable plan, and player-like actions inside Minecraft.

The framework separates reasoning from the game runtime. BlockMind Core owns intent, design, planning, project memory, execution monitoring, and validation. A Fabric adapter supplies structured observations and performs actions. Navigation is accessed through a generic provider rather than being coupled to one pathfinding implementation.

The current repository is a narrow first vertical slice. It proves the architecture in simulation and provides an experimental path to Minecraft; it is not yet a general-purpose building agent.

## The idea

```text
Text prompt                    Implemented for one narrow house prompt
Image / schematic / video      Planned — not implemented
              │
              ▼
          Understand
              ▼
            Design
              ▼
             Plan
              ▼
           Navigate
              ▼
             Build
              ▼
            Observe
              ▼
            Verify
              ▼
        Debug / repair          Partial retry logic; general repair is planned
```

AI is best used for understanding goals, resolving ambiguity, and making high-level design decisions. Coordinates, transforms, material counts, serialization, and validation remain deterministic wherever possible.

## Example

Future user request:

> “Build a modern two-story house with a pool.”

Conceptually, BlockMind should:

1. interpret the architectural requirements;
2. create named components such as the foundation, floors, walls, roof, windows, and pool;
3. expand those components into exact geometry and a material list;
4. order the work into an executable build plan;
5. navigate to valid interaction positions and act through the player;
6. observe every mutation instead of assuming success;
7. verify the completed structure and plan repairs for mismatches.

Today, the repository implements and tests this flow in an in-memory simulation for one constrained modern-house prompt. The live Minecraft version is awaiting hands-on verification.

## Why BlockMind?

| Approach | What it primarily does | How BlockMind differs |
|---|---|---|
| Schematic printer | Places a predefined block blueprint | BlockMind is intended to understand an objective and create or adapt a semantic design. |
| WorldEdit-style tool | Mutates the world directly and efficiently | BlockMind normally acts through an embodied player loop: navigate, act, observe, and verify. |
| Scripted bot | Replays fixed rules or actions | BlockMind is designed around planning, world state, project memory, validation, and eventual replanning. |
| LLM chat interface | Produces text or high-level advice | BlockMind connects reasoning to structured Minecraft observations and concrete actions. |

BlockMind is not merely a redstone bot, a schematic generator, or a cheat client. The goal is a reusable, general-purpose framework for autonomous Minecraft agents.

## Current status

Status labels are deliberately conservative. Code that compiles is not described as runtime-verified.

| Capability | Status | Evidence / limitation |
|---|---|---|
| Core architecture and protocol | **Implemented** | Minecraft-independent Python core, versioned NDJSON protocol, and JSON Schemas. |
| Deterministic house geometry | **Implemented** | Semantic components expand to exact block operations and material counts. |
| Build planning and validation | **Implemented** | Plan generation, approved bounds, operation tracking, and block comparison. |
| In-memory end-to-end simulation | **Tested** | Automated acceptance build verifies 1,310 expected blocks. |
| Pause / resume / stop / emergency stop | **Implemented in code** | Automated stop coverage; live in-game controls still require verification. |
| Basic hazard and build-region checks | **Implemented in code** | Obvious target hazards and out-of-bounds destructive actions are rejected; no comprehensive safety guarantee. |
| Fabric adapter | **Compiles** | Minecraft 1.21.11 adapter builds and remaps successfully. |
| Live Core ↔ Minecraft execution | **Experimental — awaiting live verification** | Transport and actions compile; full graphical-world acceptance run not completed. |
| Baritone navigation backend | **Experimental — awaiting live verification** | Optional public-API integration compiles; no real route verified yet. |
| General natural-language building | **Planned** | Current interpreter recognizes one constrained prompt family. |
| Natural-language modifications | **Planned** | Semantic component model exists; diff-based rebuilding does not. |
| Image understanding | **Planned** | Not implemented. |
| Schematic input | **Planned** | Not implemented. |
| Redstone and technical engineering | **Planned** | No verified component library or simulator yet. |
| Video reconstruction | **Planned** | Explicitly outside the current milestone. |
| Survival autonomy | **Planned** | Current MVP target is Creative mode. |
| General self-debugging and repair | **Planned** | Placement retry exists; diagnosis and localized repair planning do not. |

## Architecture

```text
User
 │
 ▼
BlockMind Core
 │  intent · semantic design · deterministic geometry · project memory
 ▼
Planner / World Model / Validator
 │
 ▼
NavigationProvider ───────────────► Baritone (optional backend)
 │
 ▼
Fabric Adapter
 │  observations · player-like actions · action results
 ▼
Minecraft
```

Core does not import Minecraft or Baritone types. The boundary is a local, versioned protocol so other adapters and navigation providers can be added later. Read [ARCHITECTURE.md](ARCHITECTURE.md) for the technical design and [protocol/README.md](protocol/README.md) for the wire format.

## Navigation

BlockMind Core requests goals through `NavigationProvider`, such as going to a position or approaching a build operation. Baritone is an optional Fabric-side backend and is not bundled with BlockMind. A future native or external provider can replace it without changing the Core planning model.

The current safety wrapper can reject obvious hazardous targets, but real route safety and Baritone behavior still need in-game testing. See [docs/BARITONE.md](docs/BARITONE.md).

## Safety and control

The current design includes:

- explicit approved build regions for destructive operations;
- pause, resume, stop, and emergency-stop states;
- queued-work cancellation and movement-key release on emergency stop;
- observation after mutating actions;
- basic lava, fire, hot-surface, void-level, and unsafe-drop awareness;
- structured logs for actions, failures, progress, and scaffold cleanup.

These are implemented safeguards, not a guarantee of safe autonomous operation. Use a disposable Creative test world, keep backups, stay near the agent, and be ready to stop it until live acceptance testing is complete. The local protocol is unauthenticated and must remain bound to loopback.

## Installation

These are **developer/experimental instructions**, not a stable release installation.

Requirements for the verified simulation: Python 3.11+.

```powershell
git clone <your-blockmind-repository-url>
cd BlockMind
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
blockmind "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool." --simulate --origin 0 64 0
```

The simulation writes a detailed project record under `projects/` and exits with a non-zero status if validation fails.

The experimental live path additionally requires Java 21, Minecraft Java Edition 1.21.11, Fabric Loader, Fabric API, the built BlockMind adapter, and optionally Baritone. Follow [docs/SETUP.md](docs/SETUP.md) for pinned versions, build commands, installation, and known caveats.

## Development

```text
ai-core/         Minecraft-independent agent runtime
minecraft-mod/   Fabric observations, actions, and navigation adapter
protocol/        Protocol documentation and JSON Schemas
navigation/      Provider boundary and integration notes
tests/           Simulation, safety, control, and protocol tests
docs/            Setup, Baritone decision, GitHub notes, and future media
examples/        Example acceptance prompt
projects/        Local generated project records (ignored except .gitkeep)
```

Run the Core tests:

```powershell
python -m unittest discover -s tests -v
```

Build the Fabric adapter with Java 21:

```powershell
cd minecraft-mod
.\gradlew.bat build --no-daemon
```

GitHub Actions is configured to run both checks on pushes and pull requests. A workflow badge should be added after the correct GitHub owner/remote is configured and the first workflow run exists; this README does not display an unverified passing badge.

## Roadmap

- **v0.1:** live Creative building, safe navigation, resumable projects, and repair planning;
- **v0.2:** natural-language edits, images, and schematics;
- **v0.3:** redstone and technical-build engineering with simulation;
- **v0.4:** video/reference reconstruction;
- **v0.5:** automated diagnosis, testing, and repair;
- **v0.6:** Survival resource acquisition and stronger environmental reasoning;
- **v1.0:** a stable general autonomous Minecraft architect/engineer framework.

The labels are roadmap targets, not published or stable releases. See [ROADMAP.md](ROADMAP.md).

## Media

Demonstration screenshots and GIFs will be added only after the behavior shown has been verified in a live Minecraft world. Planned demonstrations include autonomous house construction, navigation, redstone engineering, reference reconstruction, and self-debugging. See [docs/assets/README.md](docs/assets/README.md); no fabricated media is included.

## Open source and integration

BlockMind is being designed as a reusable framework rather than a single closed client. Other projects should eventually be able to integrate the Core, protocol, planners, navigation providers, builders, world representation, and validators independently.

The current interfaces are experimental and may change before the first stable release. Start with [ARCHITECTURE.md](ARCHITECTURE.md), [protocol/README.md](protocol/README.md), and [navigation/README.md](navigation/README.md). Suggested GitHub description and topics are recorded in [docs/GITHUB.md](docs/GITHUB.md).

## Final product vision

This section describes the destination, **not the current feature set**.

BlockMind is intended to become an autonomous Minecraft architect, builder, and engineer. A user will provide an objective through natural language and, eventually, images, schematics, or video references. BlockMind should then:

1. understand the objective;
2. observe the Minecraft world;
3. create a semantic design;
4. generate deterministic geometry where appropriate;
5. plan construction and calculate materials;
6. navigate the player safely;
7. perform actions physically inside Minecraft;
8. verify that each action succeeded;
9. adapt when reality differs from the plan;
10. validate the completed project;
11. diagnose failures and repair its own work;
12. remember reusable, verified components.

The long-term goal is not simply “AI that can place blocks.” It is **an AI that can independently engineer things inside Minecraft**—from ordinary architecture to farms, storage, automation, piston mechanisms, flying machines, and other technical builds.

## Contributing

Focused contributions are welcome, especially changes that strengthen the first live vertical slice without overstating its reliability. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

BlockMind source code is available under the [Apache License 2.0](LICENSE). Baritone is an optional, separately installed dependency licensed under LGPL-3.0; it is not copied or bundled here. Fabric components retain their own licenses, and Minecraft remains proprietary software subject to Mojang/Microsoft terms. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Development disclaimer

BlockMind has not reached a stable release. Do not rely on it for valuable worlds, unattended automation, or security-sensitive environments. Live movement, placement, navigation, control, recovery, and the full acceptance build must be personally verified before the project is described as fully functional.
