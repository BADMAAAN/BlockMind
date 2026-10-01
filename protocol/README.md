# BlockMind protocol 0.1.0

Local TCP NDJSON, maximum envelope **1 MiB**, with `protocol`, nonempty `id`, `type`, object `payload`. Each request ID is assigned once; results repeat it. Core binds only to a loopback IP (default `127.0.0.1:8765`). No authentication; never expose this port remotely.

## Handshake

TCP connection alone is not readiness. Adapter sends:

```json
{"protocol":"0.1.0","id":"hello-1","type":"hello","payload":{"adapter":"blockmind-fabric","adapterVersion":"0.1.1-dev","minecraft":"1.21.11","protocol":"0.1.0","capabilities":["OBSERVE_BLOCKS","PLACE_BLOCK","NAVIGATE"],"navigation":{"provider":"baritone","available":true}}}
```

The abbreviated capabilities above are illustrative. Core validates metadata, rejects any unequal protocol version and sends `hello_ack` with the same ID and `accepted: true`. Only then are requests enabled. A later `hello` updates provider availability/capabilities when a world loads; Minecraft version cannot change within the session. Missing capabilities fail clearly before sending the corresponding action.

Current advertised capabilities: `OBSERVE_BLOCKS`, `OBSERVE_ENTITIES`, `PLACE_BLOCK`, `BREAK_BLOCK`, `INTERACT`, `CREATIVE_PROVISION`, `CANCEL_NAVIGATION`, `BLOCK_STATE_ORIENTATION`, `HAZARD_SCAN`, `LOOK`, `SELECT_HOTBAR`; `NAVIGATE` only when the optional provider is available.

Additive experimental capabilities: `ACTION_BATCH`, `VALIDATE_BATCH`, `EXECUTION_CONFIG`, `AUDIO_CONTROL`, `PERFORMANCE_METRICS`. Core retains strict single-action execution when batch capabilities are absent. All configured Minecraft targets use the same protocol and schemas.

## Implemented messages

| Type | Direction | Meaning |
|---|---|---|
| hello | Adapter → Core | Metadata and capability updates |
| hello_ack | Core → Adapter | Negotiation accepted |
| observation | Adapter → Core | Player, inventory, blocks/properties, entities, hazards |
| action | Core → Adapter | Normal serialized request |
| control | Core → Adapter | Priority pause/resume/stop/emergency_stop/cancel_navigation |
| action_result | Adapter → Core | Matching ID, success/reason, observed state or response data |
| error | Core → Adapter | Invalid protocol/metadata diagnostic before disconnect |

General `event` messages are reserved, **not currently implemented**.

## Actions and observation

- `approve_region`: `region`, `temporaryRegion`, `dimension`; requires idle executor. Mutations are denied without approval.
- `observe`, `observe_block(position)`, `observe_positions(positions)`, `observe_region(region)`. Explicit scans are limited to 4,096 cells per request. A block response includes `loaded`, block ID, string-valued properties, replaceability and collision presence. Unloaded state is not air.
- `navigate(target)`: generic coordinate goal; exact target and mandatory hazard policy. Goal labels remain architectural vocabulary; follow/explore are not implemented behaviors. Tolerance is advisory; current provider requires the player's block position to match.
- `look(yaw,pitch)`, `select_hotbar(slot)`, `provision(item)` (Creative only).
- `place_block(position,block,properties,temporary)`, `break_block(position,temporary)` and `interact(position,expected,temporary)`. `expected` has block/properties; interaction without expected state is rejected.

Mutations execute on the client thread and poll actual world state for up to 80 ticks. Success requires block ID and all requested properties to match. Navigation has a 2,400-tick deadline. Controls interrupt pending work and clear queued requests; they are not blocked by normal Core action serialization. Pause aborts current action; resume permits later work. Stop remains terminal until explicit new/reconciled region approval. Already-transmitted Minecraft packets cannot be revoked.

Observations are local (radius six); unsolicited samples occur every 40 ticks while connected/in-world. Core also requests fresh local state around operations. Schemas document wire shapes; adapters additionally validate runtime inputs. Unknown optional fields are allowed. Wire version is unchanged across all configured game targets; exact-version policy is intentionally stricter than a major-only compatibility promise.

## Bounded Creative batches and performance

`action_batch(operations)` accepts 1..configured-limit operations (hard maximum 32), each with stable `id`, `position`, `block` and optional properties. Only known simple cubes without properties/temporary flags are allowed, in Creative non-SAFE mode. NORMAL/FAST/MAX process at most 1/2/4 operations per client tick. Every item still checks approval, actual reach/raycast/collision and normal player placement. Controls cancel the remaining slice/queue; already-issued packets cannot be undone.

Its `action_result` contains per-item `id`, `issued`, `reason`. **Issued is not verified.** A batch-level success means processing finished, not that every block exists. Core uses `validate_batch(operations)` for actual component/property checks (maximum 256 expected blocks per request), returning `expected/correct/missing/incorrect` and compact `mismatches` with IDs/observed states. Repairs use the strict path. Final full-region validation remains authoritative, including extras and owned temporary blocks.

`configure_execution` carries speed, maximum batch, local-movement and audio policy. `finish_project` applies audio restoration. `performance` returns adapter counters/timings. `ping` returns directly from the socket thread without accessing Minecraft, measuring local protocol scheduling/round-trip overhead separately from game-tick waiting. See the action schema and [performance documentation](../docs/PERFORMANCE.md). Schema limits are 32 placement / 256 validation operations; runtime additionally enforces the configured placement limit.

## Failure and reconnect

Malformed/oversized messages close the connection. Background reader/writer queues are bounded; game-thread operations do not write to sockets. Duplicate request IDs replay a cached response (last 256 per connection) and do not reapply pending/queued work. This is **not** durable exactly-once execution across disconnects.

Disconnect fails pending Core futures, cancels adapter navigation/actions, releases movement and invalidates region approval. A new connection renegotiates metadata. Requests are never blindly replayed: load the checkpoint and reconcile the real world. A Core request timeout attempts emergency stop and reports the unknown outcome.
