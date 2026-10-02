# Guarded temporary cleanup / Безопасная уборка опор

This is bounded cleanup hardening, not a general scaffold/sole-exit planner and
not proof that the old full-house acceptance now passes.

## Core and adapter contract

1. Only journaled positions inside the permitted temporary region are considered.
2. An observed absent block removes an unapplied/stale intent; a different material
   is preserved, remains unresolved and increments `cleanup_block_conflicts`.
3. After navigation, Core observes the **actual** player/terrain again. Invalid
   reach, body clearance, hazards or own footing refuse the mutation. Rejected
   candidate positions are excluded within bounded retries; they are not retried forever.
   A rejected breaking stance cannot be immediately reused. Core applies the same
   conservative fractional footprint as the adapter, rather than treating an integer
   feet cell as proof of clearance at its edge.
4. The block id in a temporary BREAK operation is the pre-mutation condition. Core
   sends it as `expected.block`, with any explicit state properties.
5. On the game thread the adapter checks loaded state and that precondition before
   the first break and every subsequent breaking tick. It also protects the player's
   actual conservative horizontal footprint/body/support and checks immediate danger.
   A change cancels breaking progress and fails the action. All three air variants
   finish without another mutation.
6. Core checkpoints reconciled/removal ownership immediately after confirmation.
   A lost response never causes a blind mutation replay: keep the intent and reconcile
   actual terrain after reconnect. STOP/dimension changes still prevent later actions.

Projects permitting temporary access require the negotiated `GUARDED_BREAK`
capability **before approval**. Older adapters are rejected, not given an unguarded
fallback. Update Core and the version-matching Fabric JAR together. Protocol remains
`0.1.0`; ordinary unguarded permanent BREAK keeps its previous format. Guarded breaks
are strict single actions, not part of placement bursts.

Shared-access retreat no longer trusts a navigation success label alone: observed
feet must reach the expected outside landing, with clear body cells, retained
cobblestone support and no observed local hazards. If enclosed retreat fails, preserve
access and the final failed scan instead of dismantling it.

## Verification

Verification on 2026-10-02 Moscow: 116 Python tests, 36 Java tests per each of six
configured targets and the 1,243-cell reference simulation passed. Actual 1.21.11
ground access/cleanup repeat `20261002T190812` passed **28/28**, zero discrepancies
or remaining temporary cells and client exit 0. It exercised an actual guarded
footprint rejection followed by an alternate cleanup stance. The earlier same-fixture
attempt `20261002T190211` remains FAILED (two temporary cells and native shutdown
fast-fail). [Full evidence and limits](LIVE_TESTING.md).

## Limits

- Matching material/properties is not an unforgeable ownership identity. Another
  actor replacing an owned block with the identical state cannot be distinguished.
  Use an owned/authorized world and retain the intent journal and region approval.
- Local retreat is not an escape connectivity proof. Other routes, sole exits,
  falling blocks/attachments and general scaffold topology are not modelled.
- Conservative footprint refusal can leave temporary blocks; that makes final
  acceptance fail honestly, rather than authorizing unsafe cleanup.
- Real player actions and adapter checks still apply; no direct world writes,
  navigation teleport, disabled hazards or Windows audio changes are introduced.

## Русское резюме

Перед уборкой повторно проверяются фактические ноги игрока, доступность блока и
принадлежность опоры по журналу. Мод сверяет ожидаемый исходный блок перед каждым
шагом разрушения, защищает опору под ногами и отменяет действие при изменении
блока, выгрузке участка или непосредственной опасности. Подтверждённая уборка сразу
сохраняется; неизвестный результат после обрыва связи не повторяется вслепую.

Успешный ответ навигации сам по себе не доказывает безопасный выход из постройки.
Старый адаптер без `GUARDED_BREAK` отклоняется до одобрения проекта; обновляйте
Core и мод вместе. Это усиление защиты, не доказательство полной приёмки дома,
не общий планировщик лесов и не гарантия защиты от чужой замены идентичным блоком.
