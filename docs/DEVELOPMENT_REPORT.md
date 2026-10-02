# Development and performance report — 2026-10-01 UTC

The original report is retained below as historical evidence. The new smart-builder
pass is described in the dated appendix; do not apply the old test counts to current code.

Existing repository: `BADMAAAN/BlockMind`. Original commits `0373072` and `45a1edf` preserved. No new repository, release, stable-version announcement or unrelated product modules.

## Outcome and evidence

Actual 1.21.11 Creative foundation benchmark: SAFE **64.754 s**, FAST **31.408 s**, MAX **35.971 s** for **64 correct / 64 expected**, zero missing/wrong/extra/temporary blocks in each. FAST reduced time **51.5%**, or **2.06× end-to-end throughput**. Single samples, partial foundation, pre-optimization strict baseline versus optimized execution; no full-house speedup claim. See the [before/after table, raw-evidence references and definitions](PERFORMANCE.md).

Focused vertical-access fixture passed **28/28**, with no remaining temporary blocks, **32.528 s**, run `20261001T211225`. Volume was actually **1 → 0 → 1** in these passing live tests. Full-house trials before the access fixes failed; `20261001T205102` final scan reported **1,402 expected / 569 correct / 833 missing / 0 incorrect / 0 extra / 0 temporary**. Detailed outcomes: [LIVE_TESTING.md](LIVE_TESTING.md). Complete live acceptance remains unverified; no version is promoted to SUPPORTED + TESTED.

## Causes and exact optimizations

The final full retry `20261001T211643` reached 680 checkpoint-completed operations before upper-wall access/navigation failures and a native client exit (`0xC0000409`), without an authoritative final scan. Final correct/missing/incorrect/extra/temporary totals and audio restoration are **NOT VERIFIED** for that attempt. The checkpoint retained six temporary positions. This prevents a completed-MVP claim; the native crash cause is not established. Full access/recovery acceptance remains required.

The strict baseline repeatedly observed, generated positions, navigated and verified individual cubes. Game-tick waiting dominated local socket overhead. Repeated/uncentered goals and near-first placement caused extra moves/collisions/occlusion. Grounded gravity and normal stepping also caused false hazard checks. Profiling separates request waits from actual adapter execution; five probes in the failed full run averaged **0.197 ms**, while observe requests averaged **53.256 ms**.

Implemented: separate raw-plan/execution ordering; semantic component/layer serpentine runs; reachable clusters and position reuse; far-to-near independent cubes; dynamic stable Creative hotbar slots with cached item checks; skip redundant selections/look updates; safe flat local steering with Baritone fallback and centered arrival; bounded progressive batches; compact mismatch checkpoints, strict repairs/rechecks and authoritative final scans; aggregate timings, counts and means. Temporary access uses supported stair columns and a floor bridge, is owned/checkpointed before mutation, reusable within phases and cleaned with actual break targeting/alternate candidates. No arbitrary placement sleeps or game mutations on network threads.

## Files changed

- Core: `ai-core/src/blockmind/{cli,design,geometry,models,navigation,network,protocol,runtime,simulation,logging}.py`, new `execution.py`, `interaction.py`, `performance.py`, package metadata and `blockmind.toml`.
- Fabric: shared `GameAccess`, `ActionExecutor`, `AudioSession`, `MovementSafety`, `TcpBridge`, client bootstrap and navigation providers. Mapping-specific binding sources in `yarn`, `legacy`, `intermediate`, `modern`, `official`. Observation collection moved from the old mapping-coupled collector into the game bindings, not removed as a capability.
- Builds: `targets.json`, Gradle/Loom files, official-name build variant, resource metadata and six-target CI.
- Tests/tools: original six Python tests preserved; added performance/recovery/schema/transport suites, six Java test classes, optional client-game-test source, `scripts/build_adapters.py` and `scripts/live_acceptance.py`.
- Documentation: English/Russian README, architecture, roadmap, contribution/setup/navigation/protocol/Baritone/GitHub notes, compatibility/live/performance evidence and compact benchmark JSON.

## Profiles, batches and verification

SAFE uses strict single actions. NORMAL/FAST/MAX allow simple Creative batches of up to **4/16/32**, clamped by configured maximum **16**, with **1/2/4 actions per client tick**. FAST is default. MAX is not necessarily faster. Stateful/directional blocks, doors, redstone, scaffolds, destruction, uncertain blocks and retries remain strict in every mode. Survival/batch-incapable adapters stay strict.

`ACTION_BATCH` capability enables bounded `action_batch`; replies distinguish **issued**, not observed completion. `VALIDATE_BATCH` supports up to 256 expected operations with compact mismatch data. Explicit region scans are at most 4,096 cells/request. Each item enforces approval, real reach/raycast/collision and player interaction. Queue limits, priority STOP/emergency stop, navigation cancellation and key release remain. Already-issued packets/current synchronous tick slice cannot be undone. A pending profile change does not block reading emergency stop.

Component/layer checkpoints repair mismatches strictly and revalidate. Full final scan checks requested IDs/properties, new unexpected occupied cells and tracked temporary blocks. Missing/wrong final operations trigger one bounded repair pass up to 256 operations; remaining mismatches are failure, never a success label. Natural grass-to-dirt baseline transitions are diagnostic changes, not newly placed extras. Pre-existing conflicts and legacy checkpoints without a confirmed baseline cannot be automatically cleared. Resume reconciles actual blocks instead of blindly trusting completion flags.

## Navigation and audio

Baritone remains optional, public-API-only and separately installed; pathing may not modify terrain. Local steering is restricted to observed flat one/two-block moves; elevation/obstacles/travel use Baritone. Exact centered targets/current interaction positions avoid new goals. Stale whole paths are not cached across mutations. Immediate hazard/fall/suffocation checks remain. Internal Baritone search CPU is not measured; start/active wall time and goal counts are reported.

Only Minecraft Master Volume is changed through game APIs, not OS/device settings or live configuration-file edits. Original volume survives repeated configurations. Defaults mute while active and restore on finish/stop/disconnect/world loss. Pause keeps mute during the active build. Explicit permanent mute leaves volume zero for the current client session; explicit unmute restores the remembered value. A process crash cannot guarantee restoration.

## Verification results

- **44 Python tests PASS**, including all original six; editable installation with test extras PASS; Python compilation PASS.
- Simulation acceptance: **1,402/1,402 correct**, zero missing/wrong/extra/temporary. Simulation is not Minecraft physics.
- Clean Fabric build/package/test PASS for **1.20.1, 1.20.4, 1.20.6, 1.21.1, 1.21.11, 26.3**; **13 Java tests per target**, zero failures/errors. Gradle runtime JDK 25; game/bytecode minimum 17/21/25 by target.
- Live partial foundation tests in SAFE/FAST/MAX and focused vertical-access test PASS as described above. Full-world, directional-machine, live hazard/control/disconnect-resume acceptance across the version matrix remains incomplete.
- Staged sensitive-file review found no credential patterns; worlds, logs, downloaded test dependencies, builds and project snapshots remain ignored. CI has matching checks; no remote green status is claimed before observing it.

## Exact test commands

After [SETUP.md](SETUP.md), in a disposable matching Creative world (top ground one below origin):

```powershell
$prompt = 'Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool.'
blockmind $prompt --origin 100 65 100 --speed fast --interactive
blockmind $prompt --origin 100 65 100 --speed max --max-action-batch 32 --interactive
blockmind $prompt --origin 100 65 100 --no-mute-game-audio
blockmind $prompt --origin 100 65 100 --mute-game-audio --no-restore-audio-after-build
```

Alternatively use the automated fixture, serially:

```powershell
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-blocks 64 --timeout 600
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed max --benchmark-blocks 64 --timeout 600
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-access --timeout 600
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --timeout 3600
python scripts/build_adapters.py --java-home 'C:\path\to\jdk-25' --clean
```

Harness MAX keeps default batch 16; ordinary CLI can explicitly raise it to 32. Full house omits benchmark flags. Interactive terminal commands: `perf`, `speed safe|normal|fast|max`, `mute`, `unmute`, plus status/pause/resume/stop/emergency-stop. `blockmind.toml` holds equivalent settings; project checkpoints persist them.

## Remaining work / repository handoff

Navigation, strict stateful placement and upper/interior access remain bottlenecks. A successful small wall fixture is not proof of all roof/pool/door mechanics. Finish the exact complete live acceptance and safety/recovery fixtures before a release or runtime-supported label. No image/video reconstruction, Survival gathering, full technical synthesis, new styles or polished UI were added.

Implementation commit: **696a0544c9a2179754c77a10f5d6a6231e656eb7** — `feat: add multi-version live runtime and adaptive build execution`. Diagnostic follow-up: **9f3a0608f7589cf7146de76119c84e99b06eb4c2** — `test: preserve live timeout and client exit diagnostics`. Documentation/evidence follows in a separate commit. Push is authorized only to the existing confirmed `BADMAAAN/BlockMind`; final chat handoff records its exact commit hash and actual push result. No release is created.

## Русское резюме

Работа выполнена в существующем репозитории, история сохранена. На реальном участке 64 блоков FAST показал 31,408 с против 64,754 с у строгого исходного режима: сокращение времени 51,5%, производительность в 2,06 раза выше. MAX — 35,971 с. Везде ноль расхождений и временных блоков; звук возвращался 1 → 0 → 1. Исправленный тест доступа подтвердил 28/28 блока с полной уборкой опор. Это частичные испытания, не заявление о завершённом доме.

Добавлены режимы скорости, ограниченные пакеты по тикам, сохранение/повторное использование позиций и материала, компактные проверки с ремонтом, итоговая сверка, метрики и управление громкостью. STOP и границы сохранены. Пройдены 44 теста Python, установка/компиляция/симуляция 1 402 блоков, шесть чистых сборок и по 13 тестов Java. Полная живая приёмка остаётся отдельным незавершённым этапом; подробные измерения и команды приведены выше. Релиз и заявления о стабильности не создавались.

---

## Smart autonomous builder pass — 2026-10-01 UTC / 2026-10-02 Moscow

Baseline: existing clean `main` at `19db2c8`; original history and functionality
preserved. Synced ChatGPT project sources were not edited. All build/client tests
were serial; no personal worlds, new repository, release or anti-cheat workaround.

### Implemented and bounded

The old route optimizer treated panes/stateful verification as barriers and only
optimized short same-height runs; SAFE retained the raw interleaved order. The new
`ConstructionScheduler` separates verification from movement, derives semantic
WorkZones, orders construction phases/dependencies and finishes ready active zones.
LINEAR, SERPENTINE, both perimeter directions, LAYERED and COMPONENT-FIRST are
represented, with deterministic bounded lookahead. Columns/windows finish bottom-up.
Final repair retains that global order instead of reintroducing raw facade ping-pong.
See [scheduler constraints and limitations](SCHEDULER.md).

Local execution retains real reach/raycast/safety/property verification and bounded
batches. Shared house-specific supported stairs, separate approach lanes, facade/
upper-slab/roof rings, entry onto new landings, ownership-before-mutation and retreat-before-cleanup
are experimental. Cleanup excludes actual own footing and never clears unowned
obstacles. Failed retreat from inside the structure refuses cleanup instead of
dismantling access. A general access/sole-exit graph is **not implemented or proved**.

Navigation failures have classified reasons; failed candidates are excluded locally,
stationary routes cancel after 200 client ticks, and limited deferred work is retried
after other progress. FAST now halts inside a zone after ten distinct failed operations,
not just at a potentially very large zone's end. Read-only requests aborted by explicit
pause wait for resume and retry at most twice; unknown mutations are never replayed.

Checkpoints use flush + file fsync + atomic replace, retain scheduler/batch/goal/owned
temporary intents and bounded observations. Resume scans and reconciles actual blocks,
clears stale batch/goal and reorders. Original-world identity still relies on the user
reconnecting to the correct world; a matching dimension is not unique identification.

The adapter now samples floating-point player travel and elevation transitions on the
client thread. Actual movement/provider/rotation/selection counts are distinct from
target-route proxies, logical Core calls, transport requests and unique feet positions.
No per-tick LLM, full TSP search, hidden world placement or artificial pacing was added.

### Verification to date

**67 Python tests PASS** (19.414 s), preserving the original 44; simulation acceptance still
checks 1,402 expected blocks. New tests cover four-sided glass ordering, traversal
directions, serpentine/layered/linear strategies, dependency overrides/cycles, partial
component/window/scaffold/validation interruption and reconciliation, atomic replace
failure, pause-read retry, deferred work, supported access geometry/ownership, own-footing
protection, rejected-access-placement alternatives, unsafe cleanup refusal, observed
temporary counts (not unapplied journal intents) and the FAST failure bound.
Simulation is not a live physics proof.

All six clean build/package/test targets PASS with **15 Java tests each**, zero failures
or errors, after the descending projection correction. New Java tests cover stationary
route cancellation and known-ground projection clipping while preserving actual danger
checks. Python compilation and whitespace validation also passed.

Reproducible target-route-only results and limitations are in [PERFORMANCE.md](PERFORMANCE.md).
For the four-sided glass regression, switches are 15 → 3 and recent-zone returns 12 → 0
on identical geometry. Full-plan proxy distance is 3,210.190 → 1,689.171, but vertical
target changes increase; these values are **not actual player travel or live speedup**.

New full live attempts and exact diagnostics are in [LIVE_TESTING.md](LIVE_TESTING.md).
`20261001T215603` exposed pause-read abortion; `20261001T215907` timed out with 692
checkpoint IDs, no final counts. `20261001T223549` validated first-floor components,
then exposed false void risk while descending toward second-floor access. It was
deliberately ended after diagnosis with 614 saved IDs and no final world scan.
`20261001T224524` exposed a rejected temporary side-face placement (613 saved IDs);
`20261001T225418` recovered that placement but exposed insufficient upper-slab access
and enclosure (610 saved IDs). Both were deliberately ended after diagnosis, without
final counts. Fresh live acceptance is required after corrections; none passes.

Windows WER identifies OpenAL.dll 1.23.1.0 / `0xA2B05` / `0xC0000409` after failed
game-test assertion/shutdown. Java threads, action/goal/queue snapshots, latest.log,
OpenAL log and child-vs-wrapper exit codes are retained. Exact-PID Windows crash dumps
were later found and copied into ignored output. Matching-image disassembly confirms
`mov ecx, 7; int 0x29`; raw adjacent termination addresses are not an unwound/symbolized
stack. Static WASAPI thread destruction is a strong lifecycle hypothesis, not proof
of the exact missing native cleanup call (primary sources linked in LIVE_TESTING).
Explicit SoundManager disposal before and after world closure both **failed to prevent
termination**. Negative fixture `20261001T231428` reproduced it after 1/1 verified block
and zero navigation/provider goals. Neither mute nor Baritone is established as the
cause. There is no native-crash-fixed claim.

### Deliberately gated future work

[SURVIVAL.md](SURVIVAL.md) defines needs, inventory/equipment/storage, interruption,
food/emergency policy, defensive combat and isolated Elytra capability boundaries.
[SWARM.md](SWARM.md) defines Coordinator/task board, dependency/capability matching,
expiring fenced region leases, shared hazards/resources, reservations/couriers and
failure reconciliation/reassignment.
[RESOURCE_GOVERNOR.md](RESOURCE_GOVERNOR.md) specifies configurable BALANCED reserves,
real process-tree RSS/native memory and CPU, launch refusal, pressure/critical states
and acknowledged graceful actions. These are **design documents, not runnable modules**;
their model tests and multi-client acceptance have not been implemented. Phase A has
priority; no six-client capacity or autonomous Survival claim is made.

README EN/RU, architecture and roadmap link the implemented experiment separately
from those future boundaries. Stress work is limited to owned/authorized worlds and
explicit budgets/abort conditions. No launcher polish, PvP/anti-cheat evasion, video
reconstruction, technical-machine synthesis or unsupported version promise.

## 2026-10-02: bounded bursts, Creative access and fixed Enderman

The active visual reference is now [Goldrobin's VScraft Enderman](reference-builds/vscraft-enderman.md),
not the earlier bear. The user approved reconstruction of surface mottling and
tree crowns. Revision 1 contained 1,147 deterministic physical cells but its arms
were visibly too short. Current revision 2 has **1,243**: 1,056 structural cells,
15 logs, 144 persistent leaves and 28 plant cells. The body is
12×8×48; recreated foliage expands the bounds to 14×8×58. Legs and torso have
direct dimensional evidence; the 8-cube head, forward projection and revised
34-block arms remain disclosed inferences. Views at 07:10–07:35 put the hands
near the lower legs. Material-budget inference was rejected in favor of the
observed silhouette. No author's paid schematic/world was copied.

Execution adds bounded homogeneous bursts with actual state feedback, already-
verified external dependencies and immediate local repair of required supports.
Explicit opt-in Creative flight uses normal keys/ability packets and approved,
loaded, bounded A* routes; pause/STOP/disconnect release work and do not continue
takeoff. Airborne cancellation keeps hovering rather than causing a fall. This
is not Survival flight. Visibility excludes back faces and uses conservative
bounded voxel traversal; hollow shell access can exclude the entire interior
and under-cap volume, not only one wall plane. These are experimental constraints,
not a universal collision-shape model, sole-exit proof or arbitrary obstacle solver.

Latest Python suite: **100 tests PASS**, 21.424 s, preserving the original 44,
including strict interaction geometry for the entire 8×8 open head floor.
Revision-2 fixed-fixture simulation: **1,243/1,243**, all discrepancy counts zero.
Simulation models automatic upper plant companions, not real Minecraft physics.
The final clean matrix passed all six targets with **25 Java tests each**, zero
failures/errors, including the client-side placement/flight-envelope guard.
Compilation/packaging is not runtime acceptance. No concurrent Gradle/client launch.

Partial measured live evidence is in [PERFORMANCE.md](PERFORMANCE.md) and
[the compact evidence artifact](evidence/builder-2026-10-02.json). Ground 64-cell
Core total time 29.424 s versus flight 20.823/20.078 s; all 64 expected cells
correct, no extra/temporary cells, Master Volume 1→0→1, client exit 0. The second
flight run was 31.8% faster than the single ground baseline but doubled rotations;
this is not a repeated statistical A/B guarantee or whole-statue speedup.

Source-sized legs probes failed at 28/224 and 223/224. Whole reference attempts
failed at 251/1,147 and **678/1,147**, latest 469 missing and zero wrong/extra/temporary.
The latter exercised acknowledged STOP at 160 and same-client/world Core-session
reconnect, with aggregate Core time 1,220.469 s. This is not native crash recovery.
Repeat `20261002T012731` exposed STOP arriving during a read: 160 checkpoint IDs,
no final world counts and no reconnect. A typed local STOP interruption now returns
STOPPED without a final scan or replay; its regression test passes. The next full
repeat `20261002T013447` exercised STOP/reconnect but ended 697/1,147. Repeat
`20261002T014601` also ended 697/1,147, 450 missing, zero other discrepancies,
527.269 aggregate Core seconds. A virtual pre-navigation candidate was insufficient:
strict placement now observes and checks actual arrival; client-thread placement
preserves flight clearance and exterior work rejects all under-shell approaches.
Revision-2 run `20261002T020357` failed at the open head floor: future-shell
exclusion left central floor cells without an exterior approach. A pre-repair
world scan recorded 781 correct / 462 missing and zero other discrepancies;
the final scan was not completed after a Windows checkpoint rename PermissionError.
Final counts are NOT VERIFIED, not a 781-cell acceptance. Open-top access is now
restricted to this floor component; closing walls still require actual exterior
arrival. Atomic renames retry transient PermissionError only, bounded to six
attempts without replaying world actions. Run `20261002T021814` completed a
whole-world scan with **1,243 correct, zero missing/incorrect/extra/temporary**,
1,490.109 aggregate Core seconds across STOP/reconnect. World validation passed,
but the camera harness constructed GameAccess on the wrong thread and its client
failed (wrapper 1, native `0xC0000409`). Full process/visual acceptance was not
passed. The test-only constructor is now dispatched to the client thread;
read-only reopening/inspection `20261002T025558` passed **1,243/1,243**, zero
discrepancies, zero mutations, all three normal-flight views and client exit 0.
Repeat `20261002T025938` also passed with an elevated quarter view showing the
plants/trees. Revalidation took 3.735/4.512 s and is NOT construction timing.
The intervening dev-world reload failed because Fabric's launch task cleared
its own run directory; the pre-launch backup preserved the completed world.
Explicit saved-world inspection now skips that cleanup, while ordinary fresh
tests retain it. No personal-world search or automatic repair is performed.
**REFERENCE LIVE ACCEPTANCE: PASS**, combining original physical construction
world validation with successful saved-world revalidation/visual inspection.
This is not an uninterrupted original client run or general crash-recovery claim.
Native OpenAL fast-fail still
reproduces on failed assertion/shutdown paths and is not fixed.

The old 1,402-cell house remains a regression, not the main visual demo. Its
authoritative latest result is **796 correct, 606 missing, 0 incorrect, 15 extra
permanent, 164 owned temporary**, FAILED, 1,270.914 s. Later access corrections
were not loaded in that run. Partial tests do not upgrade its status.

Survival, Swarm and resource governance remain architectural specifications;
there are no runnable claims of multi-client coordination, automatic six-client
capacity, autonomous combat/gathering or general video/engineering synthesis.

### Русское резюме нового прохода

Добавлен глобальный порядок связных рабочих зон: стекло проверяется строго, но больше
не разрывает обход фасада. Реализованы ограниченные попытки/классификация отказов,
общие экспериментальные подходы, сохранение намерений до действия и сверка региона
при восстановлении. Пройдены 100 тестов Python и по 25 Java для шести версий.
Схема эндермена уточнена по финальному силуэту: 1 243 ячейки, руки длиной 34
с отмеченной неопределённостью; симуляция подтверждает 1 243/1 243 без расхождений.
Живая постройка тоже проверена: 1 243/1 243 и нули во всех расхождениях,
24 мин 50 с суммарного времени Core. Первый клиент упал на потоке модуля
снимков после проверки мира; два отдельных открытия сохранённого мира прошли
без изменений блоков, с тремя ракурсами и нормальным завершением клиента.
Нативный сбой подтверждён дампами и кодом fast-fail в OpenAL; гипотеза жизненного цикла
WASAPI сильнее исходного предположения, но точный стек/причина не доказаны и сбой не устранён.
Итоги живых прогонов нельзя заменять промежуточными сохранёнными ID.
Survival, Swarm и Resource Governor пока подготовлены архитектурно; работающие модули
и их проверки отложены за обязательную приёмку одного строителя.
