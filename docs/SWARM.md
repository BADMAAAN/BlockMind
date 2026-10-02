# BlockMind Swarm / Совместная работа

Status: **PLANNED architecture only**. No multi-client launcher, runnable Coordinator,
worker transport, Task Board service, leases or inventory reservations are claimed yet.
Reliable single-worker acceptance remains the Phase A gate.

Launcher → Coordinator → shared project/task board → normal BlockMind workers.
The Coordinator assigns contiguous semantic components, not keypresses or individual
placements. Workers reuse the same anti-backtracking scheduler and local safety loop.
Structured messages carry worker ID/capabilities, world identity/dimension, task/zone,
status/progress, position, hazards, resource needs and heartbeat, not token-heavy chat.

Planned tasks: ID/type/component/region/dependencies/priority/owner/state/resources/
progress/retries. States: PENDING, READY, ASSIGNED, RUNNING, BLOCKED, DONE, FAILED,
CANCELLED. Only dependency-ready tasks go to a worker advertising every required
capability (BUILD, NAVIGATION, LOGISTICS, COMBAT, ELYTRA, REDSTONE, SCOUT).

Region leases use world identity, bounded spatial region, owner, expiry and fencing
token; intersecting leases cannot be held concurrently. Expired/dead/disconnected
owners lose mutation authority. Reassignment first reconciles actual blocks and owned
temporary structures. Death records last position, optionally requests equipment
recovery, then reassigns independent unfinished work; one worker cannot fail the whole project.

Shared memory retains project geometry/progress, positions, hazards, unavailable paths,
owned access, storage and resources with observation age/provenance. A discovered lava
hazard is available to other workers, but stale observations are revalidated locally.
Resource reservations atomically reserve counts per storage revision/task/lease; courier
tasks retrieve, transport and confirm delivery. Cancellation/expiry returns reservations.
No two couriers may reserve the same last stack.

Required model tests before implementation is promoted: overlapping lease exclusion;
expiry/death recovery; dependency/capability matching; DONE unlocking children;
reservation double-allocation; reconciliation/reassignment after lost worker; governor
budget refusal. Real multi-client tests on an owned/authorized server remain separate.
Controlled engineering stress tests must have entity/update/TPS/MSPT limits and aborts;
third-party disruption and anti-cheat bypass are outside scope.

## Русское резюме

Swarm пока описан архитектурно, несколько Minecraft-клиентов не запускались.
Координатор выдаёт связные участки, рабочий сам строит безопасно. Будущие временные
аренды регионов и резервирование ресурсов должны исключать конфликт действий;
отказ одного рабочего требует сверки мира и переназначения, а не остановки всего проекта.
Эти гарантии ещё должны быть реализованы и проверены, прежде чем называться функциями.
