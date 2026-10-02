# Experimental local setup

No stable release or complete live-MVP claim. Exact pins and evidence are in [COMPATIBILITY.md](COMPATIBILITY.md); test outcomes in [LIVE_TESTING.md](LIVE_TESTING.md).

## Core

Python 3.11+:

```powershell
git clone https://github.com/BADMAAAN/BlockMind.git
cd BlockMind
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[test]'
python -m unittest discover -s tests -v
python -m compileall -q ai-core/src tests scripts
blockmind "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool." --simulate --origin 0 64 0
```

Simulation explicitly logs `MODE: SIMULATION`; it models blocks, not Minecraft physics. The acceptance geometry now has 1,402 expected world blocks (includes the upper door half and sealed pool bottom). One door item creates two expected blocks.

## Build one or all adapters

Use JDK **25** for Gradle/Loom; game Java minimum is separate (17/21/25 in the matrix). `JAVA_HOME` must point to the JDK directory.

```powershell
python scripts/build_adapters.py --java-home 'C:\path\to\jdk-25' --clean
# Or one target; quote -Ptarget in PowerShell:
cd minecraft-mod
.\gradlew.bat build '-Ptarget=1.21.11' --no-daemon
```

Linux: `./gradlew build -Ptarget=1.21.11 --no-daemon`. Default target: 1.21.11. All-target helper accepts repeated `--target VERSION`. It builds serially and writes `build/adapter-build-results.json`. **Do not run different target builds or client tests concurrently in the same checkout**: Loom shares development launch/cache files.

Artifact: `minecraft-mod/build/<version>/libs/blockmind-minecraft-mc<version>-0.1.1-dev.jar`. Do not install sources or a jar for another version. Latest 26.3 uses the official unobfuscated-name build file selected automatically by settings.

## Install in a separate game profile

Create a Fabric profile for the exact chosen Minecraft version, Loader 0.19.5, matching Fabric API, and the matching BlockMind jar. Install the official `baritone-api-fabric-<version>.jar` separately, using the matrix's upstream release. Do not use standalone Baritone artifacts. BlockMind's distributed jar never bundles or downloads Baritone.

Use a **disposable Creative Overworld**. Flat ground should have its top surface one block below `--origin`. The house/pool footprint is 17 × 21 blocks; allow at least 12 blocks of temporary-access space around it. Stay nearby. This is not approved for valuable worlds or unattended automation.

Enter the world before starting the build, so metadata includes navigation readiness:

```powershell
blockmind "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool." --origin 100 65 100 --interactive
```

Logs show `MODE: LIVE`, Minecraft/adapter/protocol versions, capabilities, failures and verification. There is **no simulation fallback**, teleport navigation or direct structure `setBlock`. Only one Core process may own port 8765. Adapter reconnects to loopback; pending mutations are never automatically replayed.

## Controls and resume

With `--interactive`, type `status`, `pause`, `resume`, `stop`, or `emergency-stop` in the same terminal. Controls bypass pending navigation. Stop is terminal for this run; emergency stop clears queues, cancels navigation, releases keys and prevents further mutations. Already-sent game packets cannot be undone.

Additional interactive commands: `perf`, `speed safe`, `speed normal`, `speed fast`, `speed max`, `mute`, `unmute`. They are terminal commands, not Minecraft chat commands. `perf` displays current Core timers without waiting for an extra game request. A profile change takes effect at the next bounded batch/operation boundary.

Project records/checkpoints are atomic files in `projects/`. Restart after disconnect/stop:

```powershell
blockmind --resume 'projects\PROJECT-ID.json' --interactive
```

Resume reads current blocks/properties, rejects a different dimension, marks already-correct work, and performs only missing/wrong work. Automatic clearing is limited to approved targets that were air in a confirmed captured baseline; pre-existing conflicts require explicit user action. Old project files can be loaded, but without `baseline_captured=true` unknown occupied blocks cannot be automatically cleared. Missing blocks can still be rebuilt and correct blocks skipped.

## Developer checks

Each command owns a fresh connection; do not start a second Core alongside an active build. Use interactive controls for active work.

```powershell
blockmind --command status
blockmind --command connection
blockmind --command capabilities
blockmind --command observe
blockmind --command navigation-test --target 102 65 100
blockmind --command goto --target 102 65 100
blockmind --command cancel-navigation
blockmind --command place-test --target 103 65 100 --block minecraft:oak_stairs --properties facing=north half=bottom --approve 100 64 98 110 75 110
blockmind --command break-test --target 103 65 100 --approve 100 64 98 110 75 110
blockmind --command validate --resume 'projects\PROJECT-ID.json'
```

Place/break require an explicit region and still enforce real reach/visibility/player collision. Position the player yourself or use navigation-test first. Developer validation is read-only and returns nonzero for an unverified report.

## Disposable live acceptance harness

```powershell
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --timeout 3600
```

This opt-in harness targets **1.21.11 only**, downloads the official matching Baritone artifact after digest verification, creates a disposable Fabric client-test world, sets Creative mode/player starting position as fixture setup, then runs the **real Core over TCP** with one controlled first-placement failure. Every structure block must use player interactions. It writes logs/result/checkpoints to `build/live-test/<UTC timestamp>/` and takes a screenshot only on full success. Test artifacts/dependencies are local and ignored, not distributed with the mod. Graphics/native libraries must be available. Inspect the result: invoking the harness does not imply acceptance passed.

## Performance and audio configuration

`blockmind.toml` is loaded from the current directory; `--config PATH` selects another file. CLI options override the file. Resume preserves the checkpoint's policy unless a config/CLI override was supplied. Defaults are FAST, maximum batch 16, placement radius 3.8, position reuse/local movement enabled, temporary audio mute and restoration enabled.

```powershell
blockmind "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool." --origin 100 65 100 --speed fast --interactive
blockmind "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool." --origin 100 65 100 --speed max --max-action-batch 32 --interactive
# Keep sound unchanged:
blockmind "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool." --origin 100 65 100 --no-mute-game-audio
# Explicitly leave Minecraft muted after finish:
blockmind "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool." --origin 100 65 100 --mute-game-audio --no-restore-audio-after-build
```

Only Minecraft master volume is changed through game APIs, never Windows/device audio. Prior volume is restored on finish, stop, disconnect and world loss unless restoration was disabled. Pause retains mute while the build session is active. Permanent mute lasts for the current client session; unrelated settings/options files are not edited.

Partial performance checks (not house acceptance):

```powershell
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed safe --benchmark-blocks 64 --timeout 600
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-blocks 64 --timeout 600
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed max --benchmark-blocks 64 --timeout 600
python scripts/live_acceptance.py --java-home 'C:\path\to\jdk-25' --speed fast --benchmark-access --timeout 600
```

Run serially. The harness uses default batch 16 even in MAX; ordinary CLI can raise it to 32. It saves validation and timing data in `result.json`. Full test omits `--benchmark-blocks`. [Measured results and timer definitions](PERFORMANCE.md).

### Русское резюме настроек

FAST включён по умолчанию. SAFE проверяет каждое действие; NORMAL/FAST/MAX используют ограниченные пакеты только для простых блоков в Creative. Направленные блоки, повторные попытки, временные опоры и разрушение всегда проверяются строго. Итоговый скан обязателен, при расхождениях выполняется ограниченный ремонт. `blockmind.toml` хранит настройки, флаги командной строки их переопределяют. `--no-mute-game-audio` оставляет звук; `--no-restore-audio-after-build` оставляет Minecraft без звука после окончания. Меняется только Master Volume, системный звук не затрагивается. Команды `perf`, `speed ...`, `mute`, `unmute` вводятся в терминале с `--interactive`.

## Limits

- Approved regions, bounded retries, owned scaffold cleanup and fall guards are defense in depth, not an absolute safety guarantee.
- Access planning is bounded and may fail in obstructed interiors/upper floors. Stateful-block matcher tests do not prove actual placement mechanics.
- Unloaded chunks abort scans; Core never assumes unknown terrain is safe.
- The unauthenticated socket accepts loopback IPs only. Remote control requires a separate security design.
- On some Windows runners Java NIO fails before Gradle compilation with
  `Unable to establish loopback connection` / `UnixDomainSockets.connect0`.
  In the 2026-10-02 continuation, an explicit existing directory via the process-only
  `-Djdk.net.unixdomain.tmpdir` JDK option allowed builds to start; changing selector
  providers did not. No Windows/global environment setting was changed. This is a
  runner workaround, not a normal installation requirement or a proved general cause.

Temporary-access projects now require an adapter advertising `GUARDED_BREAK` before
approval. Update Core and the version-matching Fabric JAR together; old adapters fail
closed instead of performing unguarded cleanup. See [cleanup contract](CLEANUP_SAFETY.md).
