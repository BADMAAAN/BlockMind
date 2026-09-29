# Local setup and execution

## Pinned target

| Component | Version |
|---|---:|
| Minecraft Java Edition | 1.21.11 |
| Java | 21 |
| Fabric Loader | 0.19.5 |
| Yarn mappings | 1.21.11+build.6 |
| Fabric API | 0.141.6+1.21.11 |
| Fabric Loom | 1.14.10 |
| Gradle wrapper | 9.2.1 |
| Baritone (optional) | 1.17.0 API Fabric |
| BlockMind protocol | 0.1.0 |

The pinned coordinates came from the official [Fabric metadata/development service](https://fabricmc.net/develop/) and the official [Baritone 1.21.11 release line](https://github.com/cabaletta/baritone/tree/1.21.11). See [BARITONE.md](BARITONE.md) for the integration decision.

## 1. Install the core

```powershell
cd blockmind
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
```

## 2. Build the mod

Point `JAVA_HOME` at a Java 21 JDK, then:

```powershell
cd minecraft-mod
.\gradlew.bat clean build
```

The remapped mod is `minecraft-mod/build/libs/blockmind-minecraft-0.1.0.jar` (not the `-sources` jar).

## 3. Install Minecraft dependencies

Create a Minecraft 1.21.11 Fabric profile with Fabric Loader 0.19.5. Put these files in that profile's `mods` folder:

1. Fabric API `0.141.6+1.21.11`.
2. The built BlockMind jar.
3. Recommended: official `baritone-api-fabric-1.17.0.jar` from the [Baritone v1.17.0 release](https://github.com/cabaletta/baritone/releases/tag/v1.17.0).

Use the API Fabric artifact, not the standalone artifact, because BlockMind calls the public API. BlockMind does not download or bundle Baritone.

## 4. Run the live experimental path

Create or open a Creative world. Choose a clear, flat area large enough for the approved bounds (the default house and pool need roughly 21 × 23 blocks plus access space). Treat `--origin X Y Z` as the first build layer: normally one block above flat ground.

Start Core before entering the world:

```powershell
blockmind "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool." --origin 100 65 100
```

Then enter the Creative world near the origin. The Fabric adapter connects only to `127.0.0.1:8765`, sends structured observations, and executes the plan. Runtime logs and the final report show explicit failures; no failure is silently treated as success.

## Controls

The core API exposes `pause()`, `resume()`, `stop()`, and `emergency_stop()`. STOP is terminal for the queued builder loop. The adapter also accepts `pause`, `resume`, `stop`, and `emergency_stop` control envelopes; emergency stop clears queued actions, cancels navigation, and releases movement keys. A polished in-game/CLI control surface is still planned.

## Known setup caveats

- This pass compiled the mod and ran automated simulation tests but did not launch a graphical Minecraft session.
- Without Baritone, navigation requests fail explicitly; placement never falls back to teleporting.
- Live placement assumes the origin/build volume is clear and reachable. Short vertical scaffold fallback exists, but general access planning does not.
- The unauthenticated protocol is for loopback only.
- Some sandboxed Windows desktop runners break Java NIO's internal AF_UNIX selector pipe. That is an execution-environment issue, not a project requirement. A short `TEMP`/`TMP` path (for example `C:\jtmp`) allowed the build here; ordinary terminals generally do not need it.
