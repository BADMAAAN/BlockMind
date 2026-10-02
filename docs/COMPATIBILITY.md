# Compatibility and evidence

Metadata checked **2026-10-01**. Experimental adapters, not stable releases.
`minecraft-mod/targets.json` is the build configuration source of truth. Each target gets its own JAR; installing a different target's JAR is unsupported.

## Status definitions

- **SUPPORTED + TESTED:** completed the required runtime acceptance suite on that exact version, not just one fixed reference. **No version currently has this status.**
- **BUILDS / BUILD VERIFIED:** actual compilation, packaging and deterministic Java tests passed; not proof of in-game behavior.
- **EXPERIMENTAL:** runtime path exists but complete acceptance is unverified.
- **NOT CURRENTLY SUPPORTED:** no configured, verified adapter target. This includes unlisted patch versions and snapshots.

## Exact target matrix

All rows use Fabric Loader **0.19.5**, Loom **1.17.21**, Gradle **9.6.0**, protocol **0.1.0**, adapter **0.1.1-dev**. Run Gradle with **JDK 25**; the game/runtime and bytecode minimum varies by target.

| Minecraft | Fabric API | Mappings | Game Java | Source family | Optional Baritone | Local build | Runtime |
|---|---|---|---:|---|---|---|---|
| 1.20.1 | 0.92.12+1.20.1 | Yarn 1.20.1+build.10 | 17 | legacy | 1.10.5 | PASS | EXPERIMENTAL, unverified |
| 1.20.4 | 0.97.3+1.20.4 | Yarn 1.20.4+build.3 | 17 | legacy | 1.10.7 | PASS | EXPERIMENTAL, unverified |
| 1.20.6 | 0.100.8+1.20.6 | Yarn 1.20.6+build.3 | 21 | legacy | 1.10.8 | PASS | EXPERIMENTAL, unverified |
| 1.21.1 | 0.116.17+1.21.1 | Yarn 1.21.1+build.3 | 21 | intermediate | 1.11.3 | PASS | EXPERIMENTAL, unverified |
| 1.21.11 | 0.141.6+1.21.11 | Yarn 1.21.11+build.6 | 21 | modern | 1.17.0 | PASS | Enderman world + saved-world inspection PASS; house FAILED; broader runtime suite pending |
| 26.3 | 0.161.0+26.3 | Official unobfuscated names; no Yarn | 25 | official | 1.20.0 | PASS | EXPERIMENTAL, unverified |

Artifacts: `minecraft-mod/build/<minecraft>/libs/blockmind-minecraft-mc<minecraft>-0.1.1-dev.jar` (not `-sources.jar`). Build results are generated in `build/adapter-build-results.json`.

Clean build/test rerun on **2026-10-02**: all six targets PASS, **25 Java tests**
per target, zero failures/errors, including flight renewals, bounded routing and
client-thread flight-clearance placement guard. `minecraft:grass` is the 1.20.1
alias of modern `minecraft:short_grass` in the fixed Enderman; geometry and counts
do not change. Only 1.21.11 has live evidence; other targets remain build-only.

Cleanup-hardening continuation on **2026-10-02 Moscow**: final clean matrix PASS
for the same six targets, **36 Java tests per target**, zero failures/errors.
New adapters advertise `GUARDED_BREAK`. Projects with temporary access require
this capability before approval; update Core and its matching JAR together.
This does not upgrade any version to SUPPORTED + TESTED.

The shared executor, transport, safety/provider interfaces and protocol contain no Minecraft mapping types. Yarn targets share the main binding; tiny `ApiCompat` classes handle identifier, inventory and packet changes. The latest target uses an official-name binding because Minecraft is no longer obfuscated. CI runs separate target builds; it does **not** run the graphical acceptance world.

## Official metadata sources

- [Mojang version manifest](https://launchermeta.mojang.com/mc/game/version_manifest_v2.json): latest stable Java release was 26.3 at inspection.
- [Fabric game metadata](https://meta.fabricmc.net/v2/versions/game), [loader metadata](https://meta.fabricmc.net/v2/versions/loader), [Yarn metadata](https://meta.fabricmc.net/v2/versions/yarn).
- [Fabric API Maven metadata](https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/maven-metadata.xml).
- [Fabric 26.3 development guidance](https://fabricmc.net/2026/09/15/263.html), [26.1 unobfuscated-code transition](https://fabricmc.net/2026/03/14/261.html).
- [Official Baritone releases](https://github.com/cabaletta/baritone/releases); matching upstream artifacts are not BlockMind runtime verification.

## Русское резюме

Шесть точных версий выше действительно собираются. Это **не** подтверждение работы агента в игре. Ни одна версия пока не имеет статуса «SUPPORTED + TESTED»: для него требуется полный набор игровых приёмочных проверок, а не один фиксированный образец. Эндермен проверен на 1.21.11; дом и более широкая надёжность остаются нерешёнными. Для каждой версии устанавливайте её собственный JAR, подходящий Fabric API и отдельный Baritone. Неуказанные версии и снимки не поддерживаются. Подробности запуска и свидетельства испытаний: [SETUP.md](SETUP.md), [LIVE_TESTING.md](LIVE_TESTING.md).
