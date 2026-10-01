# Live build performance and audio

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

## Русское резюме

Реальные замеры в Minecraft 1.21.11 на одном и том же участке **64 блоков фундамента**: SAFE 64,754 с; FAST 31,408 с; MAX 35,971 с. Везде 64 верных блока, нет пропущенных, неверных, новых лишних и временных блоков. FAST сократил время на 51,5% (производительность в 2,06 раза выше). Это одиночные замеры частичного участка, **не скорость полного дома**. MAX медленнее FAST из-за дополнительных перемещений и исправлений. Громкость действительно менялась 1 → 0 → 1.

Ускорение обеспечивают порядок по компонентам/слоям, повторное использование позиции, небольшие пакеты простых блоков, локальные перемещения, пропуск лишних поворотов/выборов материала и компактная проверка с ремонтом. SAFE проверяет каждое действие; NORMAL/FAST/MAX выполняют до 1/2/4 действий за тик. По умолчанию пакет не больше 16; MAX можно явно увеличить до 32. Чувствительные блоки, опоры, разрушение и повторы остаются строгими. Итоговая проверка обязательна; ограниченный итоговый ремонт не скрывает оставшиеся ошибки.

STOP и аварийная остановка отменяют оставшуюся очередь/пакет, навигацию и отпускают клавиши. Уже отправленные игровые действия не отменяются. `blockmind.toml` и флаги управляют скоростью и звуком; команды запуска выше одинаковы для обеих локализаций. `--no-mute-game-audio` оставляет звук; `--no-restore-audio-after-build` оставляет Master Volume равным нулю. Системный звук не изменяется. Главные оставшиеся узкие места — перемещения, видимость, строгие исправления и доступ к верхним слоям. Тесты сравнения свойств не доказывают правильное размещение направленных блоков в игре.
