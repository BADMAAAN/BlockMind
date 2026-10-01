# Live test evidence

Development evidence from **2026-10-01 UTC**. A build, handshake, simulation or partial structure does not establish a completed live MVP.

## What ran

The opt-in `scripts/live_acceptance.py` launches Fabric's **1.21.11 client game-test** runner, downloads official Baritone 1.17.0 with its upstream digest checked, and creates an isolated flat Creative test world. It sets the fixture player position with a server command, waits for chunks, then runs the real Python Core over loopback TCP. **All construction uses ordinary player interactions**, not server commands or direct world writes. The controlled first-placement failure exercises recovery. The runner closes only its own test client; personal game profiles/worlds are not touched.

Java runtime: Temurin 25.0.4.1; Loader 0.19.5; API 0.141.6+1.21.11; adapter 0.1.1-dev; protocol 0.1.0. Native graphics worked in this Windows environment. Successful partial tests prove the tested path, not arbitrary hardware/server compatibility.

## Completed partial benchmarks

SAFE `20261001T203735`, FAST `20261001T204339` and MAX `20261001T204839` each physically built the same 64 foundation cells and passed a final full-region scan:

```text
MODE=LIVE
expected=64 correct=64 missing=0 incorrect=0
extra_permanent=0 temporary_remaining=0 verified=true
masterVolume=1 → 0 → 1
```

Actual navigation and retry recovery occurred. FAST took 31.408 s versus strict baseline 64.754 s; MAX 35.971 s. [Detailed timing, methodology and limits](PERFORMANCE.md), [compact evidence](benchmarks/2026-10-01-live-64.json). These are **partial foundation** results; they do not test roof access, water containment or directional door placement.

## Full-house status

The acceptance design has **1,402 expected world blocks**, including both door halves and a sealed pool bottom. One physical door item creates two expected states; the material/placement count differs accordingly.

An earlier full run (`20261001T200203`) demonstrated actual placement/navigation and controlled failure recovery, but was intentionally stopped during optimization after **542 checkpoint-completed operations**. It had no completed final world scan; correct/missing/incorrect/extra totals are **NOT VERIFIED**. Checkpoint progress must not be described as final-world correctness.

Full FAST attempt `20261001T205102` completed its final scan in **338.193 s** with **569 correct / 1,402 expected**, **833 missing**, **0 incorrect**, **0 extra**, **0 temporary**; `verified=false`. A second attempt `20261001T210228` also stopped at the wall-access transition. These are actual failed final reports, not full-house speed benchmarks. Volume restored to 1 in both. Five protocol-only probes in the first attempt averaged **0.197 ms**; this is local socket/scheduling round-trip time, not game-action latency.

The access ramp had two concrete defects: diagonal-only stairs lacked adjacent support for placement, and its end did not bridge the gap to the floor. Columns/bridge now address these. A focused **28-block partial vertical-access** fixture (`20261001T210920`) placed all expected floor/wall blocks but failed because one owned temporary block remained. Cleanup now targets the actual block rather than requiring a placement-support face, retries alternate candidates, and navigation centers arrival before interactions.

The corrected vertical fixture **passed** as `20261001T211225`: **28/28 correct**, missing/incorrect/extra/temporary all **zero**, 32.528 s, volume **1 → 0 → 1**, one controlled failure repaired. This proves low-wall access and owned cleanup for the small tested case, not second-floor/roof/door/pool acceptance. Failed earlier tests remain diagnostics, not successes.

Full retry `20261001T211643` passed the former low-wall barrier and reached **680 checkpoint-completed operations**, but ended during access/navigation at the top first-floor wall after repeated failed goals. The client process exited with **-1073740791 / NTSTATUS 0xC0000409**. The Core report had no final scan: `verified=false`, `final_world_counts=NOT VERIFIED`; the last checkpoint tracked six temporary positions. These are not final correct/missing counts, and this trial does not prove cleanup or audio restoration. The native exit's root cause has not been established. The harness now records exception types and final client exit codes instead of an empty timeout string, and refuses overall success if the client process fails after world validation.

Initial attempts exposed early Baritone initialization, a missing nested runtime dependency in Loom's dev classpath, shared launch files from simultaneous target builds, and false-positive movement checks. These were fixed; failed attempts remain diagnostics, not successes. One MAX launch (`20261001T204817`) failed before creating a world because Java could not establish its loopback socket with the runner's long temp path; the following run used a short TEMP/TMP directory and passed. Earlier partial validator results wrongly counted natural grass-to-dirt transitions as extra blocks; corrected validation still rejects newly occupied baseline-air cells outside the design.

## Reproduction

See [SETUP.md](SETUP.md) for installing the editable Core and JDK 25. Run only one Gradle target/client test at a time in the checkout.

```powershell
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --timeout 3600
# A shorter partial test, explicitly NOT full acceptance:
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-blocks 64 --timeout 600
# Focused floor-layer / low-wall access and temporary-cleanup fixture (28 cells):
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-access --timeout 600
```

Each run creates `build/live-test/<UTC timestamp>/client.log`, `core.ndjson`, `result.json` and `projects/*.json`. They are ignored generated evidence, not repository binaries. Successful tests can create a screenshot of their tested world; a partial screenshot must never be presented as a completed house. Timeout/disconnect failures retain checkpoint progress with `final_world_counts: NOT VERIFIED`. The script terminates only its own launched process tree if it cannot exit normally.

## Still required before SUPPORTED + TESTED

Full autonomous house completion, final block/property comparison, no extras or owned temporary blocks, actual pool stability/door orientation, live stop/emergency-stop during mutation and navigation, disconnect/resume without uncontrolled replay, and hazard fixtures. Current deterministic transport/control/recovery tests are valuable but not a substitute for those live scenarios. Other configured Minecraft targets are **BUILD VERIFIED only**, not runtime-tested.

## Русское резюме

Живые испытания выполнялись в отдельном одноразовом мире Minecraft 1.21.11. Команда установки позиции относится только к тестовой подготовке; строительство идёт через обычные взаимодействия игрока и реальный TCP/Core, без подмены симуляцией. SAFE, FAST и MAX подтвердили **64/64 блока фундамента**, ноль расхождений/лишних/временных блоков, восстановление громкости 1 → 0 → 1. Исправленный тест низкой стены/доступа подтвердил **28/28** с полной уборкой временных опор.

Это не полная приёмка дома. Ранний полный прогон остановлен на 542 сохранённых операциях без итогового скана; следующий полный скан дал 569 верных из 1 402, 833 отсутствующих и ноль неверных/лишних/временных. Последний повтор дошёл до 680 сохранённых операций, но завершился с отказами маршрутов и аварийным выходом клиента 0xC0000409 без итоговой проверки. Его финальные количества и восстановление звука **не подтверждены**; причина нативного завершения не установлена. Статус версии не повышается до SUPPORTED + TESTED. Логи, сохранения и измерения находятся в `build/live-test/`; личные миры не изменяются.
