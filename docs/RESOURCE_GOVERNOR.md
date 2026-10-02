# Resource Governor / Ограничение ресурсов

Status: **PLANNED policy/specification**, not a running multi-worker supervisor.
No capacity, pressure-transition tests or automatic OS actions are claimed implemented.
The current acceptance harness launches one disposable Minecraft client only.

Target host: 32 GiB, Ryzen 5 8400F, RTX 5060 Ti 16 GiB, Windows 11. Initial BALANCED
proposal: 10 GiB system/browser reserve, 16 GiB BlockMind aggregate budget, 3 GiB
measured per-worker working-set ceiling, CPU soft 75% / hard 90%, minimum free 4 GiB.
These are conservative configurable starting policies, **not benchmarked safe capacity**.
CONSERVATIVE increases reserves/reduces workers; PERFORMANCE may loosen soft policies
but never removes hard free-memory/safety limits; CUSTOM requires explicit valid values.

Sample physical/available RAM, Core RSS, each full worker-process-tree RSS (Java plus
native allocations), CPU, optional reliable GPU/VRAM. Missing samples fail closed for
new launches. Never estimate safe count from heap `-Xmx` alone. Account for Gradle/dev
helper costs during development; production launch has a distinct measured process tree.

Launch headroom is the minimum of aggregate budget remaining, physical RAM minus
reserve minus current BlockMind usage, and currently available RAM minus reserve.
Use measured peak worker cost plus safety margin; worker count 1/2/4/6/AUTO is a
requested cap, not a guarantee. A 16 GiB budget cannot promise six 3 GiB workers.

NORMAL allows a launch only with fresh adequate RAM/CPU samples. PRESSURE (reserve/soft
CPU crossed or worker growth) refuses new workers, avoids optional model/background
work and may lower supported background FPS/render distance/particles/audio. Never
reduce loaded visibility below observation needs. CRITICAL (hard budget/free RAM/CPU)
checkpoints and pauses a low-priority worker; optionally gracefully stops it after
acknowledgement. No blind process kills. Recovery needs hysteresis/fresh stable samples.

Required simulated cases: 32/10/16 GiB budget/reserve; browser opens; worker RSS grows;
soft/hard CPU crossing; PRESSURE/CRITICAL transitions; recovery hysteresis; unavailable
telemetry; launch refusal at budget; reserve never spent. Tests must never kill OS processes.
Future launcher lifecycle must wire these decisions to acknowledged checkpoint/pause/stop
before it can be called a working ResourceGovernor. No polished launcher UI is needed now.

## Русское резюме

Подготовлена спецификация, не работающий управляющий ресурсами модуль. По умолчанию
планируется BALANCED: резерв 10 ГиБ и бюджет BlockMind 16 ГиБ на машине с 32 ГиБ.
Учитываются реальные процессы и нативная память, не только Java heap. Браузер и Windows
должны сохранять запас; при давлении новые рабочие не запускаются, при критическом
состоянии сначала checkpoint и подтверждённая пауза/остановка. Шесть клиентов не обещаны.
