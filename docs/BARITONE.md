# Baritone integration decision

## Findings

Official release metadata checked 2026-10-01 supplies API Fabric artifacts for every configured target. Exact pairs: 1.20.1 → 1.10.5; 1.20.4 → 1.10.7; 1.20.6 → 1.10.8; 1.21.1 → 1.11.3; 1.21.11 → 1.17.0; 26.3 → 1.20.0. See [COMPATIBILITY.md](COMPATIBILITY.md) and [official releases](https://github.com/cabaletta/baritone/releases). Do not substitute another Minecraft target's jar.

Baritone is LGPL-3.0. BlockMind is Apache-2.0 and does not copy, modify, or bundle Baritone. Users install the official API Fabric jar as a separate mod. The adapter discovers it at runtime and calls only public API types reflectively. This preserves a clean optional boundary and avoids shipping a combined binary from this repository.

Primary references:

- [Baritone README and public API policy](https://github.com/cabaletta/baritone/blob/1.21.11/README.md)
- [Baritone setup/version matrix](https://github.com/cabaletta/baritone/blob/1.21.11/SETUP.md)
- [Baritone LGPL-3.0 license](https://github.com/cabaletta/baritone/blob/1.21.11/LICENSE)
- [Baritone v1.17.0 release](https://github.com/cabaletta/baritone/releases/tag/v1.17.0)

## Implemented boundary

Core requests a generic target and safety preference. Fabric's `NavigationProvider` exposes start, poll, cancel, and availability. `SafeNavigationProvider` rejects unsafe targets and checks immediate motion while polling; it never silently substitutes another destination. `BaritoneNavigationProvider` lazily discovers the public API only once a world is ready, creates `GoalBlock`, starts `ICustomGoalProcess`, polls `IBaritoneProcess`/`IPathingBehavior`, and reports success/failure without leaking Baritone objects.

The official 1.17.0 API jar was inspected to verify these signatures. The adapter compiles without Baritone on its compile classpath. During an owned route it disables terrain breaking/placing, parkour and sprinting and limits dry falls to three blocks. Previous settings are restored on completion, failure or cancellation. Run without competing manual Baritone jobs: the public primary instance is shared.

## Limitations

Actual test attempts and their results are recorded in [LIVE_TESTING.md](LIVE_TESTING.md). Building the adapter or finding a matching upstream jar is not proof of a successful route. Baritone policy/settings still need per-target in-game validation, event-based failure reasons and stronger risk constraints. Nether native-pathfinder functionality is outside this Creative Overworld milestone.
