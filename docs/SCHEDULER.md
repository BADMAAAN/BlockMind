# Construction scheduler / Планировщик строительства

Status: **IMPLEMENTED + deterministic tests; live acceptance EXPERIMENTAL**.
The completed-house milestone remains gated by [live evidence](LIVE_TESTING.md).

## Why the old builder crossed the house

The `19db2c8` optimizer only regrouped contiguous simple placements at the same Y.
Glass panes, stateful properties and retries split those runs. The raw generator
interleaved facades, and execution repeatedly returned to them. SAFE used the raw
list. This is an ordering defect, not evidence that network latency caused the route.

`ConstructionScheduler` now sits between raw geometry and local interaction.
Each operation retains its ID, material, expected properties and explicit dependencies.
Project → component (floor) → subcomponent (facade/slab) → `WorkZone` identifies work.
Stateful verification is independent from route eligibility: glass remains strictly
observed, but no longer splits the global facade route.

## Deterministic constraints and continuity

- Unknown/cyclic dependencies fail before mutations. Placement below-cell edges
  enforce vertical support; destructive/interact/temporary operations are barriers.
- House phases: foundation, first slab/facades, next slab/facades, roof, pool shell,
  water. The entrance is part of the north facade; its upper half depends on the lower.
- LINEAR chooses the near end. SERPENTINE alternates surface rows. LAYERED orders
  vertical/support work. COMPONENT-FIRST groups named windows. Perimeters choose
  CLOCKWISE/COUNTER-CLOCKWISE using entry and bounded onward costs, then retain direction.
- Facade columns/windows finish bottom-to-top before moving along the facade.
- A ready active zone wins within the current phase. Partial completion has a strong
  bias; recent revisits incur a penalty. A dependency can require a justified switch.
- Lookahead is bounded to 32 local candidates for global selection, 64 operations
  and 32 interaction candidates for local execution. No per-tick LLM or TSP solver.
- The current score uses travel, phase, perimeter order, completion and revisit cost.
  Material is deliberately not globally grouped. Rotation/scaffold/search-cost models
  are **not yet** full inputs to the global score.

Only zone decisions/transitions/checkpoints are logged, not per-tick decisions.
Checkpoints retain algorithm/direction, recent zones/operations, active batch/goal,
observed progress, intended owned temporary blocks and bounded confirmed observations.
Write uses flush + file fsync + atomic replace. This protects replacement interruption;
it is not a universal power-loss guarantee for every filesystem.

## Access and recovery

Supported stairs use separate approach lanes per phase. Facades, upper slabs and roof
have connected exterior work rings. The builder enters the new landing before extending
the ring above older access; preservation of every possible exit is not proved.
Each temporary placement has at most three
observed attempts with alternative feet positions, not a single silent rejection.
Temporary positions cannot overlap permanent geometry, must stay within approval,
and are journaled before placement. Existing ground is support, not owned material.
Cleanup targets only matching owned blocks and excludes the block under the player's feet.
Before common cleanup the builder attempts to retreat to a verified landing. If retreat
fails while the player is inside the structure, cleanup is refused and owned temporary
blocks remain visible to final validation; this is a failure, not successful cleanup.
Final temporary counts reconcile observed air rather than counting unapplied journal
intents; occupied conflicts remain conservative failures and are never blindly removed.
These are bounded house-specific structures, **not a general robotics/access graph**.

Navigation records failure categories and excludes failed candidates during an operation.
The adapter cancels a route after 200 stationary client ticks; normal long routes can
continue while making progress. Alternate positions/access retries are bounded. Fewer
than ten navigation/access-dependent failures may be postponed until independent work
has progressed, then retried once. Ten consecutive failures halt; final mismatch repair
is also bounded. Large unresolvable projects remain FAILED, not silently complete.

Resume scans the relevant region, reconstructs actual correct/missing/wrong states,
reconciles owned temporary intents, clears stale active batch/goal, and replans. Stored
completion and observation history are not authoritative. The user must reconnect to
the original world; dimension checking is not a unique-world identity proof.

## Measurements

`python scripts/benchmark_scheduler.py` compares the frozen `19db2c8` algorithm with
the new scheduler on identical geometry. This reports **target-route proxies**, not
actual player distance or build time. Actual tick-sampled floating-point travel,
elevation transitions, rotations/material slots and provider counts come from the
adapter, with pre-run counters subtracted. Core route switches/backtracks count actual
zone entries, including repairs. Transport navigation requests are separate from
Core calls that can return without creating a new goal. Local goal counts may include
centering after a Baritone goal, so those provider counts must not simply be added.

Developer partial live fixtures support `--legacy-scheduler` for isolated ordering
A/B tests. It is rejected for an ordinary/full build. No stable release is created.

## Semantic reference access

Fixed semantic reference components may supply explicit phase and support order.
Descending arms and horizontal shell caps carry adjacent-cell dependencies; these
are not replaced by blanket below-cell edges. Exterior hollow volumes can exclude
all under-cap/interior feet positions for walls/caps of the same part, at any
height below the cap; a short margin did not prevent a live hover trap. Strict
placement rechecks actual arrival, not just a virtual candidate. This is an
experimental access constraint, still not a general sole-exit graph or proof.
An explicitly marked open head floor permits above-floor access during that
component only. Its closing walls do not inherit the exception: actual exterior
arrival is required before their next placement. Under-floor work remains banned.
Atomic checkpoints retry only transient permission-denied renames, up to six
attempts (0.62 s total delay); persistent errors preserve the previous file and
propagate. In-world actions are never replayed by this retry.

## Русское резюме

Причина переходов между противоположными сторонами найдена в коде: стекло разрывало
короткие оптимизируемые серии, а исходная очередь перемежала фасады. Новый глобальный
порядок завершает доступную рабочую зону, сохраняет направление обхода и зависимости;
строгая проверка стекла при этом остаётся. Колонка/окно строится снизу вверх, после чего
агент движется дальше по фасаду. SAFE также получает оптимизированный порядок.

Общие наружные площадки/лестницы, классификация отказов, ограниченный возврат к
отложенной работе и атомарные checkpoints реализованы экспериментально. Симуляция
не доказывает игровую физику. Resume сверяет реальный регион, а не доверяет сохранённым
флажкам; нужна исходная игра/мир. Полная живая приёмка и её итоговые количества указаны
отдельно. Прокси расстояния между целями нельзя называть пройденным игроком путём.
