# Development and performance report — 2026-10-01 UTC

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
