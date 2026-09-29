# Contributing

BlockMind welcomes focused changes that keep the core independent from Minecraft implementation details.

## Development

1. Use Python 3.11+ and Java 21.
2. Install the core with `python -m pip install -e .`.
3. Run `python -m unittest discover -s tests -v`.
4. From `minecraft-mod/`, run `./gradlew build` (`gradlew.bat build` on Windows).
5. Add tests for behavior changes and update status documentation without claiming untested capabilities.

## Design rules

- Put Minecraft/Yarn types only in the adapter.
- Put Baritone behind `NavigationProvider`; use only its public `baritone.api` surface.
- Use AI for interpretation and higher-level decisions, deterministic code for geometry, transforms, operations, serialization, and validation.
- Observe and verify every mutating action.
- Require an explicit approved area for destructive work.
- Evolve the wire protocol compatibly and update its schemas.
- Keep optional integrations optional and respect their licenses.

## Pull requests

Explain the user-visible outcome, boundary/API changes, safety impact, tests, and any live-Minecraft validation performed. Small end-to-end improvements are preferred over broad disconnected scaffolding.
