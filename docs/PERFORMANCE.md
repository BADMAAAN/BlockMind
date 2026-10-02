# Live build performance and audio

The dated scheduler update below supersedes the ordering/stability description.
Historical SAFE/FAST/MAX samples are not isolated comparisons of the new scheduler.

Measured on 2026-10-01 UTC, Windows, Minecraft **1.21.11**, Fabric Loader **0.19.5**, API **0.141.6+1.21.11**, official Baritone **1.17.0**, adapter **0.1.1-dev**, protocol **0.1.0**, Temurin JDK 25.0.4.1. These are development measurements, not a stable-release claim.

## Before / after: actual partial live benchmark

Same disposable flat Creative fixture, origin `(100,-60,100)`, same first **64 foundation blocks** from the modern-house acceptance plan, controlled first-placement failure, default batch limit 16. Player interactions only; no structure teleportation, server `setBlock` or simulation. The SAFE sample is the strict pre-optimization baseline; FAST includes batching, position/order optimization and a corrected false-positive movement guard. This is **one sample per profile**, not a statistical study or an isolated batching-only comparison. Client/world startup is excluded; baseline scan, execution, final validation and checkpoint work are included in total run time.

| Metric | Before: SAFE | After: FAST | MAX |
|---|---:|---:|---:|
| Total Core run, seconds | 64.754 | 31.408 | 35.971 |
| Observed blocks / builder elapsed second | 0.991 | 2.047 | 1.785 |
| Navigation wait, seconds | 27.442 | 20.408 | 22.577 |
| Placement wait, seconds | 6.348 | 2.226 | 1.906 |
| Individual verification, seconds | 6.074 | 0.555 | 0.852 |
| Component verification, seconds | not used | 0.074 | 0.052 |
| Authoritative final scan, seconds | 1.771 | 1.787 | 2.097 |
| Navigation requests | 63 | 14 | 20 |
| Full local observations (`observe`) | 268 | 48 | 72 |
| Normal request/result round trips* | 728 | 196 | 256 |
| Action batches | 0 | 8 | 7 |
| Component repair operations | n/a | 6 | 8 |
| Actual adapter rotations | 126 | 65 | 73 |
| Hotbar slot switches | 0 | 0 | 0 |
| Expected / correct | 64 / 64 | 64 / 64 | 64 / 64 |
| Missing / incorrect / extra / temporary | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| Master volume before / during / after | 1 / 0 / 1 | 1 / 0 / 1 | 1 / 0 / 1 |

FAST reduced total time **51.5%**, or **2.06× end-to-end throughput**, on this partial test. MAX was slower than FAST because it needed more repositioning/repairs. Four actions per tick are not a universal throughput promise. No full-house speedup is claimed.

*Request counts are the saved transport snapshot before the final metrics/audio-finish requests. They exclude handshake/unsolicited observations and are not packet counts. Builder elapsed starts after baseline capture; total Core run starts before it. Do not divide blocks by one timer and label it as the other. The single-material sample has no slot switches and cannot prove multi-material selection savings.

Raw local evidence (ignored generated artifacts):

- SAFE: `build/live-test/20261001T203735/result.json`
- FAST: `build/live-test/20261001T204339/result.json`
- MAX: `build/live-test/20261001T204839/result.json`

Each directory also contains `core.ndjson`, `client.log`, an atomic project JSON, and the disposable test result. A compact non-personal evidence summary is tracked in [benchmarks/2026-10-01-live-64.json](benchmarks/2026-10-01-live-64.json). Earlier samples incorrectly counted natural grass-to-dirt transitions as extra blocks; they failed and are not used as passing evidence. Extra **new occupied baseline-air** positions remain a failure.

## What was slow / what changed

The baseline used fresh observations, interaction generation, navigation, placement and property queries for almost every block, including repeated moves and look synchronization. Much of a localhost action's wait is the next game tick, not socket transmission. Short corrections still generated provider work; near-first placement could block the ray to farther cells and cause retries. Grounded gravity and normal upward steps were being misclassified as hazardous collision. The corrected guard still detects actual suffocation, falling/drops and other hazards.

Implemented changes:

- Separate raw geometry from dependency-aware execution ordering. Component/layer serpentine sweeps and nearby reachable clusters avoid back-and-forth movement; sensitive/dependency barriers remain fixed.
- Reuse the actual current interaction position; choose positions covering multiple upcoming simple operations. Avoid future construction feet cells when a safe alternative exists. Supported independent cubes use far-to-near placement.
- Bounded Creative action batches replace per-cube request/observe cycles. Game-thread execution stays tick-aware and interruptible.
- Compact component/layer mismatch checks drive strict local repair, followed by revalidation. Final scan covers the whole approved temporary region, using requests of at most 4,096 cells. Final missing/wrong blocks trigger one bounded strict repair pass (up to 256), then another full scan; unresolved errors remain failure.
- Safe flat one/two-block steering avoids Baritone where possible; longer, elevated or obstructed routes use Baritone. Already-centered/reached targets skip navigation. Backend arrivals are centered using observed movement rather than assuming the block coordinate means the player is clear of adjacent placement cells. No stale full-path cache is reused after world mutations.
- Direct look updates skip identical rotations; stable dynamic Creative material slots avoid repeatedly provisioning/selecting the same item. No cinematic delays or invented sleeps.
- Temporary access platforms can be reused until phase cleanup. Supporting per-target scaffolds retain strict checks and ownership tracking.
- Background bounded socket queues perform I/O; all Minecraft state/actions/volume changes remain on the client thread. No game thread blocks awaiting Python/network.

## Profile behavior

| Profile | Simple batch cap | Actions / tick | Verification |
|---|---:|---:|---|
| SAFE | 1 (strict requests, no batch) | tick/result-driven | Immediate for every operation |
| NORMAL | 4 | 1 | Component/layer checkpoints plus repairs/final scan |
| FAST (default) | 16 | 2 | Same correctness checkpoints; clustered/reused positions |
| MAX | 32, clamped to configured limit | 4 | Same correctness checkpoints; larger tick slices |

Default configured maximum is **16**, even in MAX. `--max-action-batch 32` explicitly raises it. Actual batches can be much smaller due to reach/visibility/component/dependency barriers. Turning off adaptive or component validation disables the fast path rather than removing final verification. Survival and adapters lacking batch capabilities use strict execution. Directional blocks, doors, logs, redstone, uncertain blocks, scaffolds, destructive operations and retries are never simple batches. Technical synthesis remains out of scope.

STOP/emergency stop cancels remaining queued/batched operations and navigation, releases movement and applies audio restoration. It is processed at the client-thread boundary, not by interrupting a synchronous Java call. The current bounded tick slice or already-transmitted game packets may have taken effect. Reconcile actual world state on resume; do not replay unknown outcomes blindly.

## Configuration and commands

The checked-in `blockmind.toml`:

```toml
[execution]
speed_profile = "fast"
adaptive_verification = true
component_validation = true
max_action_batch = 16
placement_radius = 3.8

[navigation]
reuse_interaction_positions = true
prefer_local_movement = true

[audio]
mute_game_audio = true
restore_audio_after_build = true
```

CLI overrides file settings; policy is saved in project metadata and reused on resume. Radius must be 1..4.5; it never bypasses the adapter's actual raycast/reach checks. Batch must be integer 1..32. Flags:

```powershell
blockmind "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool." --origin 100 65 100 --speed fast --interactive
blockmind "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool." --origin 100 65 100 --speed max --max-action-batch 32 --interactive
# Append --no-mute-game-audio to preserve sound.
# Append --mute-game-audio --no-restore-audio-after-build to explicitly leave sound off.
```

Start in a disposable world with matching adapter/API/Baritone; flat ground is one block below origin. Interactive terminal commands: `status`, `perf`, `speed safe`, `speed normal`, `speed fast`, `speed max`, `mute`, `unmute`, `pause`, `resume`, `stop`, `emergency-stop`. These are not Minecraft chat commands. Settings change at subsequent bounded boundaries. A fresh developer session supports `blockmind --command perf`, `--command speed --speed fast`, `--command mute`, `--command unmute`; do not start a second Core alongside a running build.

Only **Minecraft Master Volume** is saved/changed through game options APIs. Reconfiguration does not overwrite the saved original volume. Finish, stop, disconnect and world loss restore it by default; pause keeps the active build muted. `restore_audio_after_build=false` leaves volume zero for that client session, without editing OS/device audio or options files. An explicit interactive `unmute` restores the remembered value. A process crash cannot guarantee restoration through game code.

## Reproduce and inspect

Run sequentially (shared Loom launch files cannot support parallel target/client builds):

```powershell
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed safe --benchmark-blocks 64 --timeout 600
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-blocks 64 --timeout 600
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed max --benchmark-blocks 64 --timeout 600
# Full house (1,402 expected world blocks), not a partial benchmark:
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --timeout 3600
```

See [LIVE_TESTING.md](LIVE_TESTING.md) for fixture behavior and limitations. Do not extrapolate foundation speed to roof, pool or stateful blocks. Use multiple samples on the same machine for future comparisons; report distributions, not only the best run.

`project.performance` stores elapsed, successful unique operated block count/rate, attempted operation rate, per-phase seconds/counts/means and before/during/after audio/adapter snapshots. `PERF` logs occur at component checkpoints/finalization, never each tick. Timers include:

Repair counters count operations scheduled for repair, not a promise that each repair succeeded; verification determines that outcome. Local goal counts can include centering after a Baritone goal, so adding local and Baritone counts is not always the number of protocol navigation requests. One-shot `--command mute` leaves mute active for the client session by default because its connection closes immediately; use interactive `mute`/`unmute` for an active build.

- Core: planning, interaction-position generation, observation wait, navigation wait, placement wait, strict verification, component verification, final scan, checkpoint I/O, control wait; repair/batch rejection counts.
- Transport: `request.<kind>` wall time/count/mean. Five pre-build `ping` requests measure local protocol/scheduling overhead separately from Minecraft tick wait. Older evidence above predates this probe and does **not** claim a pure TCP-latency number.
- Adapter: rotation/selection time and counts, placement/inspection execution time, issued-placement count, master volume.
- Navigation: Baritone start time, goal count and active wall time; local goal count. Active wall time is **not** internal pathfinding CPU time; no profiler claim is made for Baritone's own search internals.

The failed full-house trial `20261001T205102` measured five protocol-only pings averaging **0.197 ms**, versus average tick-scheduled `observe` wait **53.256 ms**. Its final result was 569 correct / 1,402 expected, 833 missing, no wrong/extra/temporary blocks. It is evidence about overhead/failure, **not** a successful full-house speed benchmark.

Timings overlap across layers, so do not sum them into total time. A snapshot of successful blocks measures observed expected placement operations, not raw packets. A door upper-half verification is not another physical placement. Core observation and transport request timers can cover the same wait. Idle is event/tick/control wait, not an artificial delay.

## Remaining bottlenecks and evidence limits

The latest full retry (`20261001T211643`) reached 680 checkpoint-completed operations before upper-wall navigation/access failure and an abnormal native client exit, without final validation. This is **not** 680 authoritatively final-correct blocks or a completed house. Its early 221-block foundation checkpoint took 58.622 s, but that phase timing must not replace the complete 64-block before/after benchmark above. Navigation failure/long deadline waits and higher access planning remain concrete blockers; the native exit cause is unverified. See [LIVE_TESTING.md](LIVE_TESTING.md).

Navigation/repositioning remains the largest measured cost (FAST 20.408 s of 31.408 s). Ray occlusion/player collisions still cause strict repairs. Dense interiors/elevation need better shared access planning. Full-region baseline/final scans intentionally remain. Glass panes, doors, water and technical blocks remain strict, so simple-floor gains cannot be extrapolated. Full-house correctness and orientation-sensitive live acceptance are not established by these benchmarks. See [COMPATIBILITY.md](COMPATIBILITY.md): build verification is separate from runtime verification.

## Scheduler update — 2026-10-01 UTC / 2026-10-02 Moscow

The frozen optimizer at `19db2c8` is available only for isolated developer fixtures.
The new global scheduler no longer treats strict glass verification as a route barrier.
Both SAFE and Creative batched execution use semantic work zones and dependency ordering;
the final repair also follows this order. See [SCHEDULER.md](SCHEDULER.md).

Reproducible **route-only**, identical-geometry results from
`python scripts/benchmark_scheduler.py`:

| Fixture | Target distance before → after | Region switches | Recent-region backtracks |
|---|---:|---:|---:|
| 64 foundation cells | 66.123 → 66.123 | 0 → 0 | 0 → 0 |
| 28 vertical cells | 34.708 → 34.243 | 5 → 3 | 2 → 0 |
| 16 glass cells on four sides | 187.485 → 35.147 | 15 → 3 | 12 → 0 |
| Full 1,402-cell design | 3,210.190 → 1,689.171 | 111 → 12 | 91 → 0 |

These are distances between **operation targets**, not player movement, navigation
requests or live time. Column-first facade work increases target-Y transitions in
the full design (19 → 459) and target material changes (122 → 126). No actual elevation
or material-selection improvement is inferred. Actual adapter tick-sampled floating
travel, block-Y transitions, rotations, selections, provider goals and transport
requests are now recorded separately, with pre-run counters subtracted. Unique
interaction feet positions are not a count of visits. Logical Core navigation calls
can skip an already-reached goal and are not transport request counts.

Full run `20261001T215603` stopped after the 221-cell foundation checkpoint when a
paused read returned an error. Read-only observation retries now wait for explicit
resume; mutation requests are never blindly replayed. Full run `20261001T215907`
timed out with 692 checkpoint-completed IDs, **without final authoritative counts**.
Its pause/resume acknowledgement test held Core placement attempts at 222 → 222.
These runs preceded the latest first-floor work ring, visible-side interaction,
column-first facade, distinct access lanes and ordered final repair. Neither is a
passing full-house benchmark. Final acceptance evidence is maintained in
[LIVE_TESTING.md](LIVE_TESTING.md).

Русское резюме: на одинаковой геометрии исчезло перемежение четырёх стеклянных
фасадов (15 → 3 смены зоны, 12 → 0 возвратов). Это доказательство порядка очереди,
не замер пройденного игроком пути. Новая полная живая приёмка обязательна; промежуточные
221/692 сохранённых операций не выдаются за итоговые верные блоки.

## Русское резюме

Реальные замеры в Minecraft 1.21.11 на одном и том же участке **64 блоков фундамента**: SAFE 64,754 с; FAST 31,408 с; MAX 35,971 с. Везде 64 верных блока, нет пропущенных, неверных, новых лишних и временных блоков. FAST сократил время на 51,5% (производительность в 2,06 раза выше). Это одиночные замеры частичного участка, **не скорость полного дома**. MAX медленнее FAST из-за дополнительных перемещений и исправлений. Громкость действительно менялась 1 → 0 → 1.

Ускорение обеспечивают порядок по компонентам/слоям, повторное использование позиции, небольшие пакеты простых блоков, локальные перемещения, пропуск лишних поворотов/выборов материала и компактная проверка с ремонтом. SAFE проверяет каждое действие; NORMAL/FAST/MAX выполняют до 1/2/4 действий за тик. По умолчанию пакет не больше 16; MAX можно явно увеличить до 32. Чувствительные блоки, опоры, разрушение и повторы остаются строгими. Итоговая проверка обязательна; ограниченный итоговый ремонт не скрывает оставшиеся ошибки.

## Adaptive bursts and opt-in Creative flight — 2026-10-02

These are **single-run partial benchmarks**, not reference-statue or full-house
acceptance. All rows below finished with the exact expected count, zero missing,
incorrect, extra permanent or owned temporary cells, restored Master Volume
1 → 0 → 1, and client exit 0. Geometry and the injected first-placement failure
were held constant within each fixture. Creative flight changes the movement
workflow, so this is not an isolated scheduler comparison.

| Fixture / run (UTC) | Seconds | Actual travel | Transport NAV | Rotations | Repairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64-cell ground baseline `20261001T234303` | 29.424 | 65.625 | 9 | 78 | 2 |
| 64-cell adaptive ground `20261002T000344` | 28.398 | 58.315 | 11 | 77 | 2 |
| 64-cell adaptive flight, direct steering `20261002T002526` | 20.823 | 46.499 | 9 | 181 | 1 |
| 28-cell flight, direct steering `20261002T002819` | 95.824 | 32.563 | 20 | 232 | 4 |
| 28-cell flight, bounded obstacle routing `20261002T003336` | 27.243 | 35.160 | 10 | 129 | 4 + 1 final |
| 64-cell adaptive flight repeat `20261002T004053` | 20.078 | 47.675 | 8 | 179 | 1 |

Adaptive ground bursts alone improved this pair by only 3.5% and increased NAV
calls: **not enough evidence of substantial speed improvement**. The first
flight 64-cell test was about 29.2% faster than the initial ground baseline, but
rotations increased. Direct flight had seven stationary-route failures on the
28-cell fixture despite ultimately passing. Bounded approved-region A* and
body-clear segment checks removed these route failures in the subsequent run.
No claim of arbitrary obstacle routing, unbounded flight, or full-statue speed
is made. Newer run evidence supersedes these implementation-stage snapshots.

Seconds above use `performance.total_run_seconds`, including configuration,
observations, navigation, verification/repairs and checkpoint work. Earlier draft
figures 29.309/28.273 were builder elapsed, not total Core run time, and are corrected.
The 64-cell flight repeat was 31.8% faster than the one ground baseline, with 27.4%
less actual travel and NAV 9→8, but rotations 78→179. Two flight runs are not a
statistically controlled repeated A/B series. Startup/Gradle time is excluded.
None of these timings is a measurement of the whole Enderman.

For the identical 64-cell ground baseline versus the later flight repeat:

| Metric | Before `20261001T234303` | After `20261002T004053` |
| --- | ---: | ---: |
| Core total seconds | 29.424 | 20.078 |
| Final correct cells / total seconds | 2.175/s | 3.188/s |
| Actual player travel | 65.625 | 47.675 |
| Transport navigation requests | 9 | 8 |
| Core observation calls | 33 | 22 |
| Transport request/response round trips | 170 | 158 |
| Component/local repairs | 2 | 1 |
| Work-region switches / backtracks | 0 / 0 | 0 / 0 |
| Distinct interaction feet positions | 9 | 8 |
| Correct cells per distinct feet position | 7.111 | 8.000 |
| Correct cells per traveled block | 0.975 | 1.342 |
| Rotations | 78 | 179 |

Round trips are the sum of recorded transport request counts, including approval,
configuration, ping, observations, scans, actions and validation. In these historical
runs the snapshot precedes the final performance/finish/audio-restoration requests;
their round trips and short final-control wait are not included. Current code takes
the total time/transport snapshot after those final controls. Core observation
calls are a narrower counter, not all observed cells or all protocol observations.
Distinct positions are not the number of visits. The same 64-cell geometry and
injected initial failure were used; this comparison includes opt-in flight and is
not an isolated adaptive-burst improvement. No route-switch improvement is claimed
for this single-zone fixture. Route-only multi-facade improvements above are separate.

Historical STOP/reconnect snapshots have two measurement limitations: stopped
adapter responses lack counters (negative travel in old raw logs is invalid),
and persisted operation attempts were included in resumed component placement
counts. Neither is used as aggregate travel or newly built cells/sec evidence.
The current code records missing/reset adapter deltas as `null` and counts only
operations actually attempted and world-verified in that Builder session, with
regression tests. Final correct counts always come from the separate world scan.

`BuildBurst` is bounded to 1..32 homogeneous simple operations in one zone and
the approved placement area. The controller starts at at most 8 operations,
grows after two full correctly observed bursts, and halves on actual mismatch
or repair feedback. Issued acknowledgements are never counted as verification.
Every burst is followed by compact block-state validation; component and final
world scans still run. Partial/truncated bursts do not imply increased capacity.
Explicit supports can enter a burst only after their dependencies are already
world-verified outside that burst. Intra-burst dependencies remain prohibited.
Failed supports needed by descendants are repaired at the burst boundary rather
than deferring them until a component scan and accumulating dependency failures.

`--creative-flight` is explicit opt-in and requires adapter `CREATIVE_FLIGHT`.
The player uses normal Creative ability packets and movement keys, with no
teleport, direct position/velocity assignment or world block writes. Flight
targets and detours stay in the approved temporary region; unloaded/hazardous
or colliding cells are rejected. A* expansion is limited to 4096 cells. The
path is checked again while moving. Pause releases controls, STOP/disconnect
disable the takeoff request, and cancellation preserves airborne Creative
hovering instead of causing a fall. This is not Survival/Elytra navigation.

Русское резюме: новые короткие серии сами по себе дали лишь небольшой выигрыш.
Отдельно включённый полёт прошёл живой тест 64/64; затем тест объёмного участка
выявил застревания и проверил их исправление ограниченным обходом препятствий.
Эти сравнения скорости относятся только к указанным частичным прогонам.
Полная статуя отдельно прошла проверку мира; полный дом остаётся FAILED.

## Whole reference v2: construction is not revalidation speed

`20261002T021814` physically built the 1,243-cell authorized reconstruction and
its final world scan found 1,243 correct, zero missing/incorrect/extra/temporary.
Its camera process failed after that scan; saved-world read-only inspection
`20261002T025558` then passed with all three views and client exit 0.
The original failed process remains recorded, not silently converted to PASS.

| Whole construction metric | Measured value |
| --- | ---: |
| Aggregate Core seconds across acknowledged STOP/reconnect | 1,490.109 |
| Final correct physical cells / Core seconds | 0.834/s |
| Actual player travel | 1,582.508 blocks |
| Correct cells / actual travel | 0.785 |
| Transport NAV requests | 683 |
| Core observation calls | 3,071 |
| Recorded transport round trips, including final controls | 10,321 |
| Rotations / material switches / elevation transitions | 3,778 / 689 / 736 |
| Work-region switches / backtracks | 23 / 1 |
| Local repair operations | 3 |
| Distinct interaction feet, first session / resumed session | 46 / 545 |

Core time sums 94.569 s before STOP and 1,395.540 s after reconnect, excluding
startup, reconnect gap and post-validation camera inspection. Cumulative actual
movement subtracts the first pre-configuration adapter snapshot from the final
construction snapshot: it excludes the initial setup teleport and camera, but
includes the reconnect gap. Missing stopped metrics are not zeros; the final
cumulative counters supply this measurement. Distinct positions are per-session,
not a recorded union; adding them would double-count any shared cells. The first
STOP placement statistic records 159 while 160 world-correct cells were reconciled;
use physical final counts, not this interrupted statistic, for throughput.

The 3.735 s saved-world inspection performed zero mutations and is **not a
1,243-block construction time or a speed improvement**. Source geometry changed
from v1's 1,147 cells, so failed v1 durations are not an identical-geometry A/B
comparison. Whole-statue speedup has not been demonstrated. Navigation and strict
stateful work remain costly, and the server logged repeated tick-lag warnings;
this run is not smooth real-time/stable-capacity evidence.

STOP и аварийная остановка отменяют оставшуюся очередь/пакет, навигацию и отпускают клавиши. Уже отправленные игровые действия не отменяются. `blockmind.toml` и флаги управляют скоростью и звуком; команды запуска выше одинаковы для обеих локализаций. `--no-mute-game-audio` оставляет звук; `--no-restore-audio-after-build` оставляет Master Volume равным нулю. Системный звук не изменяется. Главные оставшиеся узкие места — перемещения, видимость, строгие исправления и доступ к верхним слоям. Тесты сравнения свойств не доказывают правильное размещение направленных блоков в игре.
