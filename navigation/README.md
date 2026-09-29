# Navigation

Navigation has equivalent generic boundaries in Core (`blockmind.navigation.NavigationProvider`) and the Fabric adapter (`dev.blockmind.minecraft.navigation.NavigationProvider`). Goals describe intent and targets, never keys or Baritone-specific types.

Current providers:

- `SafeSimulatedNavigationProvider`: deterministic end-to-end tests.
- `SafeNavigationProvider(BaritoneNavigationProvider)`: optional Fabric runtime path.

Planned providers:

- `NativeNavigationProvider` for research/custom movement.
- `ExternalNavigationProvider` for another process or client.
