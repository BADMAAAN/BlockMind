# BlockMind Protocol 0.1

BlockMind Core and Minecraft adapters communicate through newline-delimited JSON over a local TCP socket. Every envelope has `protocol`, `id`, `type`, and `payload`. Action results repeat the request `id`, making the protocol transport-neutral and safe for concurrent extensions.

The MVP binds to `127.0.0.1:8765` only. It has no authentication and must not be exposed to an untrusted network.

Message types:

- `hello`: adapter identity, game version, capabilities;
- `observation`: structured player, inventory, nearby block, entity, and hazard data;
- `action`: one primitive action or navigation goal;
- `action_result`: observed outcome for the matching action;
- `event`: progress, disconnect, damage, or runtime diagnostics;
- `control`: pause, resume, stop, or emergency stop.

Compatibility follows semantic versioning. Unknown optional payload fields must be ignored; a different major protocol version must be rejected.
