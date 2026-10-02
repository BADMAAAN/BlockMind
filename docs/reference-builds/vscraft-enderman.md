# VScraft / Goldrobin overgrown Enderman — authorized reconstruction

The user replaced the earlier mini-bear reference with this statue on 2026-10-02.
This is development-time source analysis, **not arbitrary-video ingestion**.

- Requested page: https://vscraft.ru/ogromnaya-statuya-ehndermena-v-minecraft/
- Tutorial linked by that page: https://www.youtube.com/watch?v=5sXPPNOcuZg
- Creator credited by the page: Goldrobin.
- The page and the 8:18 tutorial were successfully accessed in the browser.
- Reference photographs show an overgrown stone Enderman with purple/magenta
  eyes, long thin legs and arms, moss patches, plants, and trees on its head.
- The page identifies Minecraft 1.19 and default textures. The fixture must use
  the same named materials on the configured targets, not replace the eyes
  with luminous blocks suggested as an optional alteration by the article.

## Source evidence / Исходные данные

At **00:30**, the tutorial explicitly states that the legs are **28 blocks tall**.
At **02:00**, the upper-leg connection and a partly built torso are visible.
At **02:30**, the torso height is labelled **12**.
At **03:00**, the open torso and horizontal arm/shoulder connections are visible.
At **04:00**, the top-down construction view shows an **8 × 4** torso top.
At **04:15**, the head is visibly hollow during construction; the source suggests
optional interior use, not a requirement to fill it solid.
At **06:00**, the frontal head view shows eyes arranged `MPM__MPM` (M = magenta
wool, P = purple concrete) and mottled brick/basalt/mud/green upper layers.
At **06:40**, manually constructed oak foliage and trunks on the moss head are visible.
At **07:00**, the tutorial explicitly identifies Creative construction and mentions
temporary platforms only as the alternative for Survival.
At **07:10–07:35**, the arms extend down well below the torso, ending near the
lower legs. A fresh comparison rejected the original 22-total-height assumption:
it produced visibly short arms. Revision 2 uses 34 total height, ending six cells
above the feet. This is a proportional inference from these views, not a caption.
At **08:00–08:10**, the final decorations show a third, small tree on the left
shoulder. These observations do not establish an author's exact schematic.

The article's approximate material list totals 1,125 blocks:

| Material | Article count |
| --- | ---: |
| Green wool | 51 |
| Moss block | 75 |
| Deepslate bricks | 408 |
| Mud | 243 |
| Smooth basalt | 177 |
| Purple concrete | 2 |
| Magenta wool | 4 |
| Oak log | 15 |
| Oak leaves | 150 |

The article itself warns that quantities may vary and rarely used items are
omitted. **This list is not an exact geometry oracle or an acceptance count.**
**Important source correction:** the article's Russian material wording was
initially recorded as dirt. The actual **00:10** tutorial material card clearly
says **Mud (243)**. Use `minecraft:mud`, never substitute `minecraft:dirt`.
The video card additionally lists 4 tall grass items, 12 grass items and 4 rose
bush items; two-cell plants must be counted as physical cells, not just items.
Additional vegetation and orientation-sensitive leaf/log/vine states must be
derived from the construction sequence. Doors, windows and a house roof are
not relevant: the reference is a statue, not an inhabitable building.

## Fixed fixture and confidence / Образец и достоверность

The user explicitly approved building **by the example**, with reconstructed
stone mottling and tree crowns. `--reference vscraft-enderman` selects a fixed,
deterministic development-time fixture, not video-to-build software. No paid
schematic/world was obtained or redistributed.

| Part | Fixture geometry | Evidence/confidence |
| --- | --- | --- |
| Legs | two 2×2×28 pillars, two-cell gap | height caption, cross-section visible at 00:20 |
| Torso | 8×4×12 hollow shell | height caption, 04:00 top grid, open interior |
| Head | 8×8×8 hollow shell, four-cell forward projection | inferred from construction views; not an explicit dimension caption |
| Arms | two 2×2×34 pillars, descending from shoulders; bottoms at Y=6 | inferred from 07:10–07:35/final photographs; approximate materials are not a geometry oracle |
| Eyes | `MPM__MPM` on front, four magenta/two purple | frontal 06:00 view |
| Trees | two head trees and one left-shoulder tree; trunks 5/8/2 | positions visible; heights/crowns reconstructed with approval |

Body bounds are 12×8×48. Including recreated foliage, fixture bounds are
**14×8×58**. Revision 2 has **1,243 physical expected cells**: 1,056 structural cells,
15 logs, 144 persistent leaves, and 28 plant cells (20 placed items, eight
automatically-created upper companions). The reference material card has 150
leaves; our reconstructed crowns have six fewer. Surface quantities also differ:
204 smooth basalt, 392 deepslate bricks, 294 mud, 42 green wool, 118 moss,
four magenta wool and two purple concrete. This is not a claim of exact texture.

Every cell has a deterministic `vscraft-enderman-v2` coordinate ID. Existing
saved revision-1 plans retain their old geometry on resume; no silent migration.
Semantic components carry phase,
exterior access constraints and explicit adjacent-support dependencies. Caps
grow from supported edges; arms grow down from shoulders. Leaves preserve
`persistent=true`, logs request `axis=y`; plant lower/upper states are verified
separately. Leaf distance is allowed to update naturally. Plant distribution is
recreated on the roof and differs from shoulder plants in the source.

The separate `--reference vscraft-enderman-legs` probe contains only 224 uniform
deepslate cells and must never be reported as whole-reference acceptance.
First probe `20261002T004805`: **28/224**, 196 missing, no incorrect/extra/temporary
cells. It exposed Creative ability toggling during jump-key braking.
Second probe `20261002T005533`: **223/224**, one missing, zero incorrect/extra/temporary;
pause/resume acknowledged with attempts 43/43. Neither probe passed.
Both failed assertion/shutdown paths reproduced the existing native OpenAL fast-fail.

The following historical runs used the **obsolete 1,147-cell revision 1**, with
shorter arms. They do not constitute acceptance of current revision 2.
Run `20261002T010535` exercised STOP at 160 cells and same-world
Core-session reconnect, but finished **678/1,147**, 469 missing, zero incorrect,
extra or temporary cells. It is **FAILED**, not a successful full reference.
Repeat `20261002T012731` stopped during an observation with 160 checkpoint IDs;
it has no final world scan and did not reconnect. Typed STOP handling was then
corrected and regression-tested. Run `20261002T013447` exercised STOP/reconnect,
but finished **697/1,147**, 450 missing, zero incorrect/extra/temporary cells.
Its head floor could invalidate the player's own three-cell flight clearance.
Repeat `20261002T014601` again ended 697/1,147 with 450 missing and zero other
discrepancies: the pre-navigation placement guard alone was insufficient.
Current code also checks actual arrival before strict mutations, rejects under-
shell approaches regardless of starting height, and enforces flight-clearance
preservation on the client thread. Revision-2 run `20261002T020357` reached a
pre-repair scan of 781 correct / 462 missing / zero other discrepancies, but its
final scan was interrupted by a Windows checkpoint rename error: final counts
NOT VERIFIED. Its open head floor exposed over-conservative future-shell access.
Above-floor access is now allowed for the open floor only; closing walls still
require exterior arrival. Full construction `20261002T021814` subsequently
validated **1,243/1,243**, zero missing/incorrect/extra/temporary. Its camera
harness failed after construction because GameAccess was created off the client
thread; that original client run is still FAILED. After correcting the harness,
read-only reopening of the saved owned world (`20261002T025558`) independently
validated the same 1,243 cells, issued zero mutations, reached all three normal-
flight camera viewpoints and exited successfully. The screenshots were visually
inspected against the source: long limbs, projecting head/eyes and three trees
are present; texture/crown/plant-distribution differences remain as disclosed.
Repeat `20261002T025938` passed the same checks with an elevated quarter view.
Our head trees have separated crowns and exposed vertical trunks rather than
the broad merged canopy visible in the source photograph; vegetation is an
approved reconstruction, not a visually exact copy. No numerical image-similarity
or author's exact-schematic claim is made.
Whole-reference status: **REFERENCE LIVE ACCEPTANCE: PASS**, via construction
world validation plus successful saved-world inspection, not an uninterrupted
crash-free original client run. Broader stability and the house regression remain
unresolved.
Simulation and live physics are reported separately.

Разрешена реконструкция по образцу, а не поблочная копия неизвестной схемы.
Ноги и корпус измерены по видео; размеры головы и рук восстановлены с явно
отмеченной неопределённостью. Кроны и рисунок материалов воссозданы. Полная
приёмка требует проверки всех 1 243 ячеек и отсутствия лишних/временных блоков.
После сверки финальных видов укороченные руки старого варианта исправлены;
их общая высота 34 и зазор над стопами 6 — отмеченные оценки, не подпись автора.
Мир проверен: 1 243 верных ячейки и нули во всех категориях расхождений.
Исходный клиент упал на модуле снимков после постройки; отдельно пройдены
повторное открытие сохранённого мира, проверка без изменений и три ракурса.
