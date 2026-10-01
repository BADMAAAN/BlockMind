# Navigation

Navigation has equivalent generic boundaries in Core (`blockmind.navigation.NavigationProvider`) and the Fabric adapter (`dev.blockmind.minecraft.navigation.NavigationProvider`). Goals describe intent and targets, never keys or Baritone-specific types.

Current providers:

- `SafeSimulatedNavigationProvider`: deterministic end-to-end tests.
- `RemoteNavigationProvider`: Core-side generic TCP goals, negotiated capability gate and priority cancellation.
- `SafeNavigationProvider(LocalNavigationProvider(BaritoneNavigationProvider))`: flat one/two-block local adjustments with public-API Baritone fallback for travel/elevation/obstacles.

Reachable pending simple placements share their current position rather than issuing another goal. Exact already-reached goals are skipped. Position/material caches are rechecked against observations; full paths are not reused blindly after world changes. Navigation counters distinguish local goals, Baritone starts and active wall time. [Performance evidence](../docs/PERFORMANCE.md).

The live provider requires an exact safe coordinate, enforces a deadline and checks immediate motion/fall hazards. It does not teleport, silently substitute another destination, or implement follow/explore yet. See [Baritone policy](../docs/BARITONE.md) and [live evidence](../docs/LIVE_TESTING.md).

Planned providers:

- `NativeNavigationProvider` for research/custom movement.
- `ExternalNavigationProvider` for another process or client.
