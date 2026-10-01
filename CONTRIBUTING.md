# Contributing

BlockMind welcomes focused changes that keep the core independent from Minecraft implementation details.

## Development

1. Use Python 3.11+ and JDK 25 for builds; game Java differs by [target](docs/COMPATIBILITY.md).
2. Install the core with `python -m pip install -e '.[test]'`.
3. Run `python -m unittest discover -s tests -v`.
4. Run `python scripts/build_adapters.py --java-home /path/to/jdk-25` for all targets, or select one with `--target VERSION`. Do not run targets concurrently in one checkout.
5. Add tests for behavior changes and update status documentation without claiming untested capabilities.

## Design rules

- Put Minecraft/Yarn types only in the adapter.
- Put Baritone behind `NavigationProvider`; use only its public `baritone.api` surface.
- Use AI for interpretation and higher-level decisions, deterministic code for geometry, transforms, operations, serialization, and validation.
- Observe and verify every mutation, immediately for sensitive actions or through adaptive component/final checkpoints for simple batches. Never treat `issued` as observed success.
- Require an explicit approved area for destructive work.
- Evolve the wire protocol compatibly and update its schemas.
- Keep optional integrations optional and respect their licenses.

## Pull requests

Explain the user-visible outcome, boundary/API changes, safety impact, tests, and any live-Minecraft validation performed. Small end-to-end improvements are preferred over broad disconnected scaffolding.
