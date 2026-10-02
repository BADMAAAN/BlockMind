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

## Scheduler and crash investigation update — 2026-10-01 UTC

New full attempts `20261001T215603` and `20261001T215907` are **FAILED**. The first
stopped after the 221-cell foundation checkpoint on a paused observation error;
the second timed out after 30 minutes with 692 checkpoint-completed IDs. Neither
has final authoritative world counts. Both exercised acknowledged pause/resume;
the second held Core placement attempts at 222 → 222 during the pause. A successful
pause check does not imply full build or crash-resume acceptance.

The paused-read defect was fixed with bounded read-only retries after resume,
without replaying mutations. Further changes add first-floor/upper facade work
rings, visible-side-face candidate checks, column-first windows, separate stair
lanes and globally ordered final repair. These require fresh live evidence.

Windows Application Error / WER records for failed test clients (including
`20261001T211643` and `20261001T215603`) identify **OpenAL.dll 1.23.1.0**, offset
`0xA2B05`, exception `0xC0000409`, parameter 7, event type BEX64. The exceptions
followed Fabric game-test assertion failure/world closure. Initially no native dump or
JVM `hs_err` was found in the run directory; later scoped dump inspection is below. Java thread
snapshots alone cannot establish an audio/Baritone causal stack.

`0xC0000409` is a fast-fail termination code, not proof that a literal stack-buffer
overrun occurred ([Microsoft fast-fail documentation](https://learn.microsoft.com/en-us/cpp/intrinsics/fastfail?view=msvc-170)).
The evidence identifies a faulting module and a failing-test-shutdown correlation;
it does **not** establish that mute, placement rate or Baritone caused the failure.
The first test-only mitigation explicitly closed the sound manager on the client thread
before throwing a failed-acceptance assertion. This is a targeted harness mitigation,
not a production audio-disable workaround. It was **not sufficient**: full trial
`20261001T223549`, deliberately ended after the captured second-floor access defect,
again exited with `0xC0000409` in OpenAL. No native-crash fix is claimed.

That trial validated the foundation, first slab and four first-floor facades at
component checkpoints (609 physical placement IDs; door companion is separately
verified). The second-floor approach failed with `movement aborted: void risk` on
a short descent to known ground. Its final saved checkpoint had 614 completed IDs,
but the world was not finally scanned. The run is FAILED, not 614 final-correct blocks.
The descending three-tick projection now clips at observed collision support;
actual-position drop/hazard/void checks remain enabled. A regression test preserves
an ungrounded projection and confirms that known-ground descent cannot tunnel through
the floor. This change needs a fresh full live run.

Subsequent scoped inspection found Windows local crash dumps for those exact test
PIDs, outside the per-run directories. Dumps for PID 27588 and 34428 were copied
into their ignored run directories. `inspect_native_dump.py` confirms exception
parameter 7 and instruction pointer `OpenAL.dll+0xA2B05`; the timestamp/size-matching
DLL has `mov ecx, 7; int 0x29` at that location. Raw stack words point to adjacent
termination code (`+0x9FFDD`, `+0xCF997`). They are **not a symbolized/unwound stack**.

Disassembly at `+0xCF980` tests a static nonzero thread-like field before calling
termination; the matching OpenAL 1.23.1 WASAPI source has a static proxy thread,
and MSVC's `std::thread` destructor terminates for a joinable thread. This is a
strong **shutdown-lifecycle hypothesis**, not proof of the exact missing native
cleanup call ([OpenAL WASAPI source](https://github.com/kcat/openal-soft/blob/1.23.1/alc/backends/wasapi.cpp),
[Microsoft STL thread source](https://github.com/microsoft/STL/blob/main/stl/inc/thread)).
It narrows the failure beyond a generic stack-overrun label; no placement/Baritone
causality is established. The test-only disposal was moved **after world closure**.
The negative fixture `20261001T231428` built and finally verified 1/1 block with zero
navigation/provider goals, then intentionally failed because its requested STOP
threshold (2) was not exercised. It again exited with `0xC0000409`; its exact-PID dump
was retained. This second mitigation is also **ineffective**. Heavy navigation/action
load is not required to reproduce the failure, although this does not prove Baritone
is unrelated or identify the exact missing cleanup call.

Full trial `20261001T224524` passed the former false-drop check, but a rejected
temporary side-face placement abandoned second-floor access (613 saved IDs).
`20261001T225418` retried that placement successfully, then exposed an insufficient
upper-slab landing and an enclosed player; bounded failures/cleanup made no further
useful progress (610 saved IDs). Both were deliberately ended after diagnosis, lack
an authoritative final scan, and reproduced the native shutdown. Access now uses
full upper-slab/roof exterior rings and enters the new landing before extension;
cleanup refuses to dismantle access when inside retreat fails. These changes require
fresh full live verification, not retrospective success labels.

Read-only reproduction (optional developer packages, not Core dependencies):

```powershell
python -m pip install minidump==0.0.24 pefile==2024.8.26 capstone==5.0.9
python scripts/inspect_native_dump.py 'build/live-test/20261001T224524/java.exe.34428.dmp' --image 'C:\path\to\matching\OpenAL.dll'
```

Only module offsets/instructions are printed, no captured strings/environment.
Dumps are sensitive generated evidence and must not be committed or shared publicly.

Diagnostics now retain client tick/action/goal/queue state, Java failure threads,
OpenAL logs and JVM error-file location. All stay in ignored disposable test output.
The Gradle wrapper exit (1) is distinct from the actual child Minecraft native exit
(-1073740791); both are saved. Audio is not disabled and no native library is replaced.

Русское резюме: журнал Windows указал модуль OpenAL.dll, но полного нативного стека
для установления первопричины нет. Сбой связан по времени с завершением неуспешного
теста; нельзя приписывать его Baritone или громкости без дополнительных доказательств.
Новые полные прогоны пока не подтверждают завершённый дом. Сохранённый прогресс — не
итоговый скан мира.

## Reproduction

See [SETUP.md](SETUP.md) for installing the editable Core and JDK 25. Run only one Gradle target/client test at a time in the checkout.

```powershell
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --timeout 3600
# A shorter partial test, explicitly NOT full acceptance:
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-blocks 64 --timeout 600
# Focused floor-layer / low-wall access and temporary-cleanup fixture (28 cells):
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-access --timeout 600
# Four-facade glass fixture (160 expected cells including foundation/slab):
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-perimeter --timeout 900
# Isolated ordering comparison only, same partial fixture/current runtime:
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-perimeter --legacy-scheduler --timeout 900
# STOP + fresh Core session, same client/world, scan/replan/owned-temp cleanup:
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --restart-after 700 --timeout 1800
```

Each run creates `build/live-test/<UTC timestamp>/client.log`, `core.ndjson`, `result.json` and `projects/*.json`. They are ignored generated evidence, not repository binaries. Successful tests can create a screenshot of their tested world; a partial screenshot must never be presented as a completed house. Timeout/disconnect failures retain checkpoint progress with `final_world_counts: NOT VERIFIED`. The script terminates only its own launched process tree if it cannot exit normally.

## 2026-10-02: Creative flight and fixed Enderman reconstruction

See [the reference/confidence record](reference-builds/vscraft-enderman.md) and
[compact exact evidence](evidence/builder-2026-10-02.json). The user replaced the
bear with this Enderman and approved recreated stone mottling and crowns.
Current revision 2 contains **1,243 physical cells**; it is not general video ingestion.
Earlier 1,147-cell runs below used obsolete revision 1, with visibly short arms.
Source comparison at 07:10–07:35 corrected total arm height from 22 to an inferred
34, with lower ends six cells above the feet. Old counts are historical diagnostic
evidence, not acceptance of current geometry.
Compilation, simulation and reference-size partial probes are separate evidence.

The 64-cell Creative flight runs `20261002T002526` and `20261002T004053` passed
64/64, with zero missing/wrong/extra/temporary cells, restored Master Volume and
normal exit 0. Direct steering exposed stationary failures on the 28-cell volume;
bounded loaded-cell A* subsequently passed 28/28 without navigation failures.
The measured timings and regressions in rotations are in [PERFORMANCE.md](PERFORMANCE.md).

224-cell legs probes `20261002T004805` and `20261002T005533` ended at 28/224 and
223/224 respectively. The second exercised pause/resume, attempts stable 43/43.
First whole reconstruction `20261002T005958` ended **251/1,147**, 896 missing,
zero incorrect/extra/temporary, in 230.043 Core seconds. A deliberately rejected
support was deferred too long, accumulating dependency failures before component
repair. Immediate repair of required support IDs and back-face visibility checks
were added afterwards. These runs reproduced native OpenAL fast-fail on the failed
assertion/shutdown path; this is not a native crash fix.

STOP/reconnect run `20261002T010535` finished **678/1,147**, 469 missing,
zero incorrect/extra/temporary cells, **FAILED**. Aggregate Core time was
1,220.469 s (233.156 before reconnect + 987.313 after). Its first session
acknowledged STOP at 160 confirmed cells with zero temporary intents; the same
client/world reconnected and scanned before continuing. This is **Core-session
recovery**, not an actual native process crash/restart or proven world identity.
The remaining failures involved blocked/unreachable faces and under-cap positions;
required-support verification for bursts, conservative voxel traversal, and whole
hollow-volume exterior constraints were subsequently refined. Repeat
`20261002T012731` interrupted a read at STOP: 160 checkpoint IDs, no final world
scan, no reconnect. Typed local STOP handling now returns STOPPED without read
replay or a claimed final scan. Its regression test passes; full repeat
`20261002T013447` exercised that correction and STOP/reconnect, but ended
**697/1,147**, 450 missing, zero incorrect/extra/temporary cells, FAILED.
Aggregate Core time was 526.639 s. A head-floor placement could occupy the
player's own conservative flight head-clearance cell, invalidating later routes.
Placement now preserves that clearance even when the eye is lowered. The next
repeat `20261002T014601` again ended 697/1,147, 450 missing, zero other
discrepancies, FAILED, 527.269 aggregate Core seconds. Pre-navigation geometry
alone was insufficient. The current strict path observes actual arrival before
mutation, the adapter enforces its flight envelope, and exterior shell approaches
stay outside its footprint at any height below the cap. Revision-2 run
`20261002T020357` failed at the open head floor. A pre-repair scan recorded
781 correct / 462 missing / zero incorrect, extra and temporary; a Windows
checkpoint PermissionError interrupted repair/finalization. Final world counts
are NOT VERIFIED. The open floor now allows above-floor access during that
component only; closing walls still require actual exterior arrival. Bounded
atomic-rename retries never replay an in-world action. Run `20261002T021814`
completed whole-world validation: **1,243/1,243**, all discrepancy counts zero,
1,490.109 aggregate Core seconds. However, the camera harness instantiated
GameAccess on the gametest thread, triggering Fabric's thread guard. World PASS
is separate from this **FAILED client/visual process**, which reproduced OpenAL
fast-fail during exception shutdown. The constructor now runs on the client
thread; reopening the saved owned world is read-only, never a rebuild/repair.

Saved-world inspection `20261002T025558` and repeat `20261002T025938` both
independently verified **1,243/1,243**, zero discrepancies, **zero mutations**,
three accepted/arrived camera views and client exit 0. The repeat's elevated
quarter view shows roof plants/trunks/crowns. Core read-only checks took
3.735/4.512 s; neither is construction timing. **REFERENCE LIVE ACCEPTANCE: PASS**
combines physical construction world validation with successful saved-world
inspection; the original interrupted camera/client run remains FAILED.

The first reopening (`20261002T025154`) failed before Core connected: Fabric's
`deleteGameTestRunDir` removed its own saved dev-world directory, leading to a
RecoverWorldScreen. A pre-launch backup preserved the actual completed world
and was restored without editing block/NBT contents. An intermediate Gradle
configuration-cache failure (`20261002T025451`) did not start a client. Explicit
`--resume-project` now preserves only the fixed dev run directory, loads only its
last owned save, verifies its dimension and scans without executing/repairing a
plan. Missing/reset/changed placement counters fail closed. It requires a source
checkpoint whose whole-world validation passed before its client failed. No
personal-world discovery or arbitrary saved-world identity proof is provided.
Ordinary fresh tests still clear their own disposable run directory.

For reproduction in a disposable world (one own client, no parallel Gradle):

```powershell
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --reference vscraft-enderman --creative-flight --restart-after 160 --timeout 1800
```

`--reference vscraft-enderman-legs` tests only the uniform 224-cell leg probe.
Revision-2 simulation verified all 1,243 cells but cannot prove reach, collision,
flight, foliage/plant updates or live reference appearance. Camera inspection, when
enabled for a passing whole reference, runs only after Core's final scan with normal
flight keys; no camera teleport or additional block writes. It is excluded from Core
build timing, restores its test-only FOV/HUD, and records separate view metadata.
The harness allows up to 180 s for these post-validation full-reference views
and owned-client shutdown (30 s for other fixtures); neither is Core build time.

### Authoritative latest old-house regression (not the visual reference)

`20261001T232042`: **796/1,402 correct**, 606 missing, zero incorrect,
**15 extra permanent and 164 owned temporary cells**, **FAILED**.
Core total time 1,270.914 s; actual travel 1,636.582 blocks, transport NAV 476,
rotations 1,389, material switches 94. Master Volume was observed 1→0→1.
Pause/resume attempts held 222/222. Requested STOP at 700 was **not exercised**
because execution failed before that threshold. Subsequent access/exterior/repair
changes were not loaded in that full-house run and do not upgrade it to PASS.
Its final world counts supersede earlier checkpoint-only 680/692 numbers.

## Still required before SUPPORTED + TESTED

### Cleanup-hardening continuation — 2026-10-02 Moscow

`20261002T190211` ran the same 28-cell vertical-access fixture using the current
global scheduler, shared exterior access and `GUARDED_BREAK`, with ordinary ground
navigation (Creative flight off). Authoritative scan: **28/28 correct**, zero missing,
incorrect or extra permanent cells, **2 temporary remaining: FAILED**. The remaining
cobblestone column was at `(97,-60,100)` and `(97,-59,100)`. Core took **146.708 s**;
actual travel **191.007 blocks**, transport NAV **135**, Baritone goals **14**, local
movement starts **132**, rotations **343**, material switches **4**, region switches
**3**, backtracks **0**, Core observations **393**, transport round trips **1,698**.
These layers are distinct counters, not interchangeable navigation totals.
Master Volume was observed **1→0→1**; Windows audio was unchanged. All construction
and cleanup used actual player interactions. The failed assertion/shutdown reproduced
native `0xC0000409`; client/Gradle exited 1. It is not a successful live acceptance.

The first attempt did not record per-rejection reasons, so an exact live reason for
those two cells is not asserted. Inspection found a concrete retry defect: a rejected
cleanup stance could be reused on the next attempt. Core now excludes it, logs the
adapter reason and checks the same fractional body/support footprint. Focused model
tests prove alternative selection after a controlled rejection and bounded unresolved
ownership, not live physics. The failed own save was copied before a fresh repeat.

Repeat `20261002T190812`: **PARTIAL ACCESS LIVE ACCEPTANCE: PASS**. Final scan
**28/28**, all missing/incorrect/extra/temporary counts zero, client/Gradle exit **0**.
Core **145.289 s**, actual travel **189.710 blocks**, transport NAV **134**, Baritone
goals **14**, local movement starts **131**, rotations **342**, material switches **4**,
region switches **3**, backtracks **0**, Core observations **387**, transport round trips
**1,670**. One rejected breaking stance was observed, then cleanup used another stance
and removed all owned access. Master Volume **1→0→1**. This single repeat is reliability
evidence for the small fixture, not a statistical speedup or a full-house/native-crash fix.
Raw local logs, both owned save backups and the generated acceptance view remain ignored.

The full-house status above is unchanged; no general native-crash fix or whole-build
speed improvement is claimed. Shared access differs from the historical older fixture
implementation, so its old 32.528 s is not a controlled before/after comparison.

Full autonomous house completion, final block/property comparison, no extras or owned temporary blocks, actual pool stability/door orientation, live stop/emergency-stop during mutation and navigation, disconnect/resume without uncontrolled replay, and hazard fixtures. Current deterministic transport/control/recovery tests are valuable but not a substitute for those live scenarios. Other configured Minecraft targets are **BUILD VERIFIED only**, not runtime-tested.

## Русское резюме

Живые испытания выполнялись в отдельном одноразовом мире Minecraft 1.21.11. Команда установки позиции относится только к тестовой подготовке; строительство идёт через обычные взаимодействия игрока и реальный TCP/Core, без подмены симуляцией. SAFE, FAST и MAX подтвердили **64/64 блока фундамента**, ноль расхождений/лишних/временных блоков, восстановление громкости 1 → 0 → 1. Исправленный тест низкой стены/доступа подтвердил **28/28** с полной уборкой временных опор.

Это не полная приёмка дома. Последний авторитетный скан `20261001T232042` дал
796 верных из 1 402, 606 отсутствующих, 0 неверных, 15 лишних постоянных и
164 временных блока: FAILED. Громкость восстановлена. Сбой 0xC0000409
локализован в OpenAL.dll; гипотеза завершения WASAPI подтверждена косвенно,
но точный нативный стек/первопричина и исправление не доказаны. Для эндермена
актуальна новая схема на 1 243 ячейки; старые прогоны на 1 147 — история
диагностики, не её приёмка. Статус версии не повышается до SUPPORTED + TESTED.
Логи и миры находятся в `build/live-test/`; личные миры не изменяются.
