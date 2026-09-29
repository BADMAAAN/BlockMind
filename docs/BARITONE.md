# Baritone integration decision

## Findings

The official Baritone project currently publishes Fabric builds for Minecraft 1.21.11 and documents a supported public API under `baritone.api`. Its setup guide maps Minecraft 1.21.11 to Baritone 1.17, and release 1.17.0 provides `baritone-api-fabric-1.17.0.jar`.

Baritone is LGPL-3.0. BlockMind is Apache-2.0 and does not copy, modify, or bundle Baritone. Users install the official API Fabric jar as a separate mod. The adapter discovers it at runtime and calls only public API types reflectively. This preserves a clean optional boundary and avoids shipping a combined binary from this repository.

Primary references:

- [Baritone README and public API policy](https://github.com/cabaletta/baritone/blob/1.21.11/README.md)
- [Baritone setup/version matrix](https://github.com/cabaletta/baritone/blob/1.21.11/SETUP.md)
- [Baritone LGPL-3.0 license](https://github.com/cabaletta/baritone/blob/1.21.11/LICENSE)
- [Baritone v1.17.0 release](https://github.com/cabaletta/baritone/releases/tag/v1.17.0)

## Implemented boundary

Core requests a generic target and safety preference. Fabric's `NavigationProvider` exposes start, poll, cancel, and availability. `SafeNavigationProvider` rejects obvious hazardous targets or chooses a nearby safe target. `BaritoneNavigationProvider` converts the generic target into `GoalBlock`, starts `ICustomGoalProcess`, polls `IBaritoneProcess`/`IPathingBehavior`, and reports success or failure without leaking Baritone objects.

The official 1.17.0 API jar was inspected during development to verify these signatures. The adapter compiles without Baritone on its compile classpath.

## Limitations

This is suitable for an optional MVP backend, but live runtime behavior was not exercised in this pass. Baritone route policy/settings need in-game validation, event-based failure reasons, and stronger BlockMind-specific risk constraints before navigation can be described as comprehensively safe.
