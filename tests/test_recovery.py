import asyncio
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "ai-core" / "src"))

from blockmind.interaction import candidates, orientation
from blockmind.models import Bounds, BuildOperation, OperationKind, ProjectStatus, Vec3i
from blockmind.navigation import SafeSimulatedNavigationProvider, NavigationResult
from blockmind.runtime import BlockMindAgent, Builder, ControlState, ProjectStore, Validator
from blockmind.simulation import SimulatedMinecraftPort

PROMPT = "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool."


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    def project(self, operations):
        port = SimulatedMinecraftPort()
        project = BlockMindAgent(port, SafeSimulatedNavigationProvider()).plan(PROMPT, Vec3i(0, 64, 0))
        project.plan.operations = operations
        return port, project

    async def test_resume_reconciles_world_instead_of_replaying_completed_flags(self):
        ops = [BuildOperation(OperationKind.PLACE, Vec3i(i, 64, 0), "minecraft:stone", "test") for i in range(3)]
        port, project = self.project(ops)
        port.world.blocks[ops[0].position] = ops[0].block
        project.completed_operation_ids = [ops[1].id, ops[1].id]
        with tempfile.TemporaryDirectory() as folder:
            store = ProjectStore(Path(folder))
            loaded = store.load(store.save(project))
            builder = Builder(port, SafeSimulatedNavigationProvider())
            await builder.reconcile(loaded)
            self.assertEqual(loaded.completed_operation_ids, [ops[0].id])
            await builder.execute(loaded)
            self.assertEqual(loaded.progress, 1)
            self.assertNotIn(ops[0].position, port.attempts)
            self.assertEqual(loaded.status, ProjectStatus.COMPLETE)

    async def test_state_properties_are_verified_not_only_block_id(self):
        op = BuildOperation(OperationKind.PLACE, Vec3i(1, 64, 0), "minecraft:oak_log", "test", properties={"axis": "x"})
        port, project = self.project([op])
        port.world.blocks[op.position] = op.block
        port.world.properties[op.position] = {"axis": "y"}
        self.assertFalse((await Validator().validate(project, port)).verified)
        self.assertFalse(await Builder(port, SafeSimulatedNavigationProvider())._already_satisfied(op))

    async def test_natural_baseline_change_is_not_an_extra_new_block(self):
        op = BuildOperation(OperationKind.PLACE, Vec3i(1,64,0), "minecraft:stone", "test")
        port, project = self.project([op])
        ground = Vec3i(1,63,0)
        project.baseline = [{"position": ground.to_dict(), "block": "minecraft:grass_block"}]
        port.world.blocks[ground] = "minecraft:dirt"
        port.world.blocks[op.position] = op.block
        self.assertTrue((await Validator().validate(project,port)).verified)
        port.world.blocks[Vec3i(2,64,0)] = "minecraft:gold_block"
        self.assertEqual((await Validator().validate(project,port)).extra_permanent,1)

    async def test_stop_during_navigation_prevents_placement(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        class WaitingNavigation(SafeSimulatedNavigationProvider):
            async def navigate(self, goal, world):
                entered.set()
                await release.wait()
                return NavigationResult(True, goal.target)
        op = BuildOperation(OperationKind.PLACE, Vec3i(1, 64, 0), "minecraft:stone", "test")
        port, project = self.project([op])
        control = ControlState()
        task = asyncio.create_task(Builder(port, WaitingNavigation(), control).execute(project))
        await entered.wait()
        control.stop()
        release.set()
        await task
        self.assertFalse(port.attempts)
        self.assertEqual(project.status, ProjectStatus.STOPPED)

    async def test_pause_during_navigation_waits_before_mutating(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        class WaitingNavigation(SafeSimulatedNavigationProvider):
            async def navigate(self, goal, world):
                entered.set(); await release.wait(); return NavigationResult(True, goal.target)
        op = BuildOperation(OperationKind.PLACE, Vec3i(1, 64, 0), "minecraft:stone", "test")
        port, project = self.project([op])
        control = ControlState()
        task = asyncio.create_task(Builder(port, WaitingNavigation(), control).execute(project))
        await entered.wait(); control.pause(); release.set(); await asyncio.sleep(.02)
        self.assertFalse(port.attempts)
        control.resume(); await task
        self.assertEqual(port.attempts[op.position], 1)

    async def test_retry_limit_provider_failure_and_local_repair(self):
        class FailingNavigation(SafeSimulatedNavigationProvider):
            async def navigate(self, goal, world): return NavigationResult(False, world.player.position, "unreachable")
        op = BuildOperation(OperationKind.PLACE, Vec3i(1, 64, 0), "minecraft:stone", "test")
        port, project = self.project([op])
        await Builder(port, FailingNavigation(), max_attempts=2).execute(project)
        self.assertEqual(op.attempts, 2)
        self.assertFalse(port.attempts)
        self.assertEqual(project.status, ProjectStatus.FAILED)
        project.failures.clear()
        project.baseline_captured = True
        port.world.blocks[op.position] = "minecraft:dirt"
        await Builder(port, SafeSimulatedNavigationProvider()).execute(project)
        self.assertEqual(port.world.blocks[op.position], op.block)

    async def test_existing_world_conflict_is_not_destroyed(self):
        op = BuildOperation(OperationKind.PLACE, Vec3i(1, 64, 0), "minecraft:stone", "test")
        port, project = self.project([op])
        port.world.blocks[op.position] = "minecraft:diamond_block"
        project.baseline = [{"position": op.position.to_dict(), "block": "minecraft:diamond_block"}]
        await Builder(port, SafeSimulatedNavigationProvider()).execute(project)
        self.assertEqual(port.world.blocks[op.position], "minecraft:diamond_block")

    async def test_legacy_project_without_baseline_does_not_clear_unknown_blocks(self):
        op = BuildOperation(OperationKind.PLACE, Vec3i(1,64,0), "minecraft:stone", "test")
        port, project = self.project([op])
        port.world.blocks[op.position] = "minecraft:diamond_block"
        self.assertFalse(project.baseline_captured)
        await Builder(port, SafeSimulatedNavigationProvider()).execute(project)
        self.assertEqual(await port.block_at(op.position), "minecraft:diamond_block")
        self.assertEqual(project.status, ProjectStatus.FAILED)

    async def test_temporary_intent_is_checkpointed_before_unknown_mutation(self):
        op = BuildOperation(OperationKind.PLACE, Vec3i(1, 65, 0), "minecraft:scaffolding", "_temporary", temporary=True)
        port, project = self.project([op])
        builder = Builder(port, SafeSimulatedNavigationProvider())
        snapshots = []
        builder.checkpoint = lambda p: snapshots.append(p.to_dict())
        builder._remember_temporary(project, op)
        self.assertEqual(len(snapshots[0]["temporary_blocks"]), 1)
        self.assertNotIn(op.position, port.world.blocks)
        await builder._remove_scaffold([op.position], project)
        self.assertFalse(project.temporary_blocks, "an intended-but-never-applied temporary block is reconciled as air")

    async def test_repeated_failures_halt_without_thousands_of_retries(self):
        class FailingNavigation(SafeSimulatedNavigationProvider):
            async def navigate(self, goal, world): return NavigationResult(False, world.player.position, "unreachable")
        ops = [BuildOperation(OperationKind.PLACE, Vec3i(i, 64, 0), "minecraft:stone", "test") for i in range(30)]
        port, project = self.project(ops)
        await Builder(port, FailingNavigation(), max_attempts=1).execute(project)
        self.assertEqual(sum(op.attempts for op in ops), 10)
        self.assertEqual(project.status, ProjectStatus.FAILED)

    async def test_explicit_resume_allows_new_goals_after_navigation_cancel(self):
        port, project = self.project([BuildOperation(OperationKind.PLACE, Vec3i(1, 64, 0), "minecraft:stone", "test")])
        nav = SafeSimulatedNavigationProvider()
        agent = BlockMindAgent(port, nav)
        await agent.send_control("pause")
        self.assertTrue(nav.cancelled)
        await agent.send_control("resume")
        await Builder(port, nav, agent.control).execute(project)
        self.assertEqual(project.status, ProjectStatus.COMPLETE)

    def test_candidates_exclude_collision_hazard_unknown_ground_and_occlusion(self):
        op = BuildOperation(OperationKind.PLACE, Vec3i(0, 65, 0), "minecraft:stone", "test")
        port, _ = self.project([op])
        world = port.world
        world.observed_bounds = Bounds(Vec3i(-4, 60, -4), Vec3i(4, 70, 4))
        self.assertFalse(candidates(op, world), "unknown support must not be assumed solid")
        for x in range(-4, 5):
            for z in range(-4, 5):
                p = Vec3i(x, 63, z); world.blocks[p] = "minecraft:stone"; world.solid.add(p)
        support = op.position.offset(dy=-1)
        world.blocks[support] = "minecraft:stone"; world.solid.add(support)
        options = candidates(op, world)
        self.assertTrue(options)
        blocked = options[0].feet
        world.blocks[blocked] = "minecraft:stone"
        self.assertNotIn(blocked, [candidate.feet for candidate in candidates(op, world)])
        first = candidates(op, world)[0]
        penalized = next(c for c in candidates(op, world, reserved={first.feet}) if c.feet == first.feet)
        self.assertEqual(penalized.cost, first.cost + 8)

    def test_orientation_and_door_companion_geometry(self):
        self.assertEqual(orientation({"facing": "north"})[0], 0)
        self.assertEqual(orientation({"half": "top"})[1], -80)
        port = SimulatedMinecraftPort()
        project = BlockMindAgent(port, SafeSimulatedNavigationProvider()).plan(PROMPT, Vec3i(0, 64, 0))
        doors = [op for op in project.plan.operations if op.component_id == "entrance"]
        self.assertEqual(len(doors), 2)
        self.assertEqual(sum(op.verify_only for op in doors), 1)
        pool = [op for op in project.plan.operations if op.component_id == "pool"]
        self.assertGreater(min(project.plan.operations.index(op) for op in pool if op.block == "minecraft:water"),
                           max(project.plan.operations.index(op) for op in pool if op.block != "minecraft:water"))

    def test_break_candidates_allow_a_floating_block_without_placement_support(self):
        op = BuildOperation(OperationKind.BREAK, Vec3i(0,65,0), None, "temporary", temporary=True)
        port, _ = self.project([op])
        port.world.observed_bounds = Bounds(Vec3i(-4,60,-4), Vec3i(4,70,4))
        for x in range(-4,5):
            for z in range(-4,5):
                point = Vec3i(x,63,z)
                port.world.blocks[point] = "minecraft:stone"
                port.world.solid.add(point)
        port.world.blocks[op.position] = "minecraft:cobblestone"
        port.world.solid.add(op.position)
        self.assertTrue(candidates(op, port.world))

    async def test_access_ramp_connects_to_floor_without_parkour_gap(self):
        op = BuildOperation(OperationKind.PLACE, Vec3i(0,66,0), "minecraft:stone", "wall")
        port, project = self.project([op])
        builder = Builder(port, SafeSimulatedNavigationProvider())
        for x in range(-5, 1):
            for z in range(-1, 2):
                port.world.blocks[Vec3i(x,63,z)] = "minecraft:stone"
        original_place = port.place_block
        async def supported_place(operation):
            if operation.temporary:
                neighbors = [operation.position.offset(dx,dy,dz) for dx,dy,dz in
                    ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))]
                self.assertTrue(any(port.world.block_at(p) != "minecraft:air" for p in neighbors),
                    "each access block needs an actual adjacent support, not diagonal contact")
            return await original_place(operation)
        port.place_block = supported_place
        await builder._install_access(op, project)
        bridge = Vec3i(-1,65,0)
        self.assertEqual(await port.block_at(bridge), "minecraft:cobblestone")
        self.assertTrue(any(Vec3i(**entry["position"]) == bridge for entry in project.temporary_blocks))
        await builder._remove_scaffold([Vec3i(**entry["position"]) for entry in list(project.temporary_blocks)], project)
        self.assertFalse(project.temporary_blocks)
