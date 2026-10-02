# Survival foundation / Основа Survival

Status: **PLANNED architecture, not autonomous Survival**. Phase A single-worker
Creative acceptance has priority. No eating, chest transfer, defensive combat or
Elytra automation is advertised as implemented by this design document.

Subsystem boundaries: `SurvivalManager` owns task interruption/resume;
`NeedsManager` selects deterministic priorities; `InventoryManager` owns stack/container
transactions; `EquipmentManager` owns slots/durability; `CombatManager` owns defensive
threat response; `ResourceManager` owns acquisition and reservations.

`PlayerNeeds` will contain observed health/hunger, optional saturation, armor slots,
weapon/shield, edible stacks, golden apples/totems, Elytra durability/fireworks, and
environmental/hostile threats. Unknown fields stay unknown, never fabricated as safe.
Current observations already contain health/hunger, inventory and environmental hazards;
they do not imply these future policies/actions work.

Priority order: emergency escape/death prevention, critical heal, immediate defense,
critical eating, equipment recovery, logistics, build, cosmetics. Critical actions
checkpoint and pause the build, acknowledge the interrupt, perform bounded verified
actions, re-observe safety and reconcile before resuming. An LLM is not called every tick.
Food selection avoids unnecessary eating; golden-apple HP threshold and rare-item reserve
are configurable policies. Preserve the build zone/material/access state across interruptions.

Future types: `StorageLocation(world, dimension, position)`, `ContainerInventory(slot,
item, count, revision)`, `ResourceRequest(task, item, quantity)`, `ResourceReservation`
with ownership/expiry. Transfers require server-confirmed inventory revisions and close
the container even on cancellation. Never fragile screen-coordinate automation.

`ElytraFlightSkill` stays a separate capability: equipment/durability/fuel preflight,
safe takeoff, heading/altitude, obstacle-aware glide, rocket policy, landing and abort.
It requires isolated live tests before any long-range autonomous flight claim.
Combat is defensive survival against hostile mobs; no PvP cheating or anti-cheat bypass.

## Русское резюме

Это проектирование будущих подсистем, не работающий автономный Survival. Еда, сундуки,
экипировка, защита и полёт требуют отдельных действий адаптера и живых испытаний после
надёжного Creative-строителя. Опасность должна прерывать работу с сохранением состояния,
а безопасное продолжение — начинаться с нового наблюдения. Редкие предметы сохраняются
по политике; неизвестные данные не подменяются безопасными значениями.
