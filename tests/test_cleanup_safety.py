"""Cleanup races are deterministic model tests, not Minecraft physics evidence."""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from blockmind.models import Bounds, BuildOperation, OperationKind, Vec3i
from blockmind.navigation import NavigationResult, SafeSimulatedNavigationProvider
from blockmind.network import FabricMinecraftPort
from blockmind.protocol import AdapterMetadata, CapabilityError
from blockmind.runtime import BlockMindAgent, Builder, ProjectStore
from blockmind.simulation import SimulatedMinecraftPort
from blockmind.interaction import can_interact


class CleanupSafetyTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self, hook=None):
        port = SimulatedMinecraftPort(Vec3i(-8, 64, 0))
        world = port.world
        world.observed_bounds = Bounds(Vec3i(-10, 60, -10), Vec3i(10, 72, 10))
        for x in range(-10, 11):
            for z in range(-10, 11):
                point = Vec3i(x, 63, z)
                world.blocks[point] = "minecraft:stone"
                world.solid.add(point)
        target = Vec3i(0, 66, 0)
        world.blocks[target] = "minecraft:cobblestone"
        world.solid.add(target)
        class Navigation(SafeSimulatedNavigationProvider):
            async def navigate(self, goal, state):
                if hook:
                    return hook(goal, state, target)
                return await super().navigate(goal, state)
        navigation = Navigation()
        project = BlockMindAgent(port, navigation).plan("Build a modern house", Vec3i(0, 64, 0))
        project.dimension = world.player.dimension
        project.temporary_blocks = [{"position": target.to_dict(), "block": "minecraft:cobblestone"}]
        builder = Builder(port, navigation)
        port.break_block = AsyncMock(wraps=port.break_block)
        return port, project, builder, target

    async def test_navigation_claim_without_actual_arrival_never_breaks(self):
        def hook(goal, world, target):
            return NavigationResult(True, goal.target)
        port, project, builder, target = self.fixture(hook)
        await builder._remove_scaffold([target], project)
        port.break_block.assert_not_awaited()
        self.assertEqual(len(project.temporary_blocks), 1)
        self.assertGreater(builder.metrics.counts["cleanup_unsafe_arrivals"], 0)

    async def test_arrival_on_owned_footing_does_not_remove_it(self):
        def hook(goal, world, target):
            world.player.position = target.offset(dy=1)
            return NavigationResult(True, goal.target)
        port, project, builder, target = self.fixture(hook)
        await builder._remove_scaffold([target], project)
        port.break_block.assert_not_awaited()
        self.assertEqual(await port.block_at(target), "minecraft:cobblestone")

    async def test_replacement_during_approach_is_preserved(self):
        def hook(goal, world, target):
            world.player.position = goal.target
            world.blocks[target] = "minecraft:diamond_block"
            return NavigationResult(True, goal.target)
        port, project, builder, target = self.fixture(hook)
        await builder._remove_scaffold([target], project)
        port.break_block.assert_not_awaited()
        self.assertEqual(await port.block_at(target), "minecraft:diamond_block")
        self.assertEqual(len(project.temporary_blocks), 1)
        self.assertEqual(builder.metrics.counts["cleanup_block_conflicts"], 1)

    async def test_disappeared_block_reconciles_and_checkpoints_without_break(self):
        def hook(goal, world, target):
            world.player.position = goal.target
            world.blocks.pop(target)
            world.solid.discard(target)
            return NavigationResult(True, goal.target)
        port, project, builder, target = self.fixture(hook)
        snapshots = []
        builder.checkpoint = lambda state: snapshots.append(len(state.temporary_blocks))
        await builder._remove_scaffold([target], project)
        port.break_block.assert_not_awaited()
        self.assertEqual(snapshots, [0])
        self.assertFalse(project.temporary_blocks)

    async def test_successful_cleanup_carries_guard_and_checkpoints(self):
        port, project, builder, target = self.fixture()
        snapshots = []
        builder.checkpoint = lambda state: snapshots.append(len(state.temporary_blocks))
        await builder._remove_scaffold([target], project)
        self.assertEqual(port.break_block.await_count, 1)
        operation = port.break_block.await_args.args[0]
        self.assertEqual(operation.block, "minecraft:cobblestone")
        self.assertEqual(snapshots, [0])
        self.assertFalse(project.temporary_blocks)

    async def test_unknown_break_outcome_preserves_intent_until_read_only_reconciliation(self):
        port, project, builder, target = self.fixture()
        project.plan.operations = []
        original = port.break_block
        async def interrupted(operation):
            await original(operation)
            raise ConnectionError("connection lost after applied break")
        port.break_block = AsyncMock(side_effect=interrupted)
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectStore(Path(directory))
            checkpoint = store.save(project)
            builder.checkpoint = store.save
            with self.assertRaises(ConnectionError):
                await builder._remove_scaffold([target], project)
            self.assertEqual(len(project.temporary_blocks), 1)
            self.assertEqual(port.break_block.await_count, 1, "unknown mutation is never replayed")
            resumed = store.load(checkpoint)
            await builder.reconcile(resumed)
            self.assertFalse(resumed.temporary_blocks)
            self.assertEqual(port.break_block.await_count, 1, "reconciliation is read-only")

    async def test_rejected_break_retains_owned_intent_for_later_recovery(self):
        port, project, builder, target = self.fixture()
        port.break_block = AsyncMock(return_value=False)
        await builder._remove_scaffold([target], project)
        self.assertEqual(await port.block_at(target), "minecraft:cobblestone")
        self.assertEqual(len(project.temporary_blocks), 1)
        self.assertLessEqual(port.break_block.await_count, builder.max_attempts)

    async def test_rejected_cleanup_stance_is_not_reused_on_the_next_attempt(self):
        port, project, builder, target = self.fixture()
        target = Vec3i(0, 64, 0)
        port.world.blocks[target] = "minecraft:cobblestone"
        port.world.solid.add(target)
        project.temporary_blocks = [{"position": target.to_dict(), "block": "minecraft:cobblestone"}]
        original = port.break_block
        positions = []
        async def reject_first(operation):
            positions.append(port.world.player.position)
            return False if len(positions) == 1 else await original(operation)
        port.break_block = AsyncMock(side_effect=reject_first)
        await builder._remove_scaffold([target], project)
        self.assertEqual(len(positions), 2)
        self.assertNotEqual(positions[0], positions[1])
        self.assertFalse(project.temporary_blocks)

    def test_fractional_break_pose_matches_adapter_footprint_guard(self):
        port, _, _, _ = self.fixture()
        port.world.player.position = Vec3i(-1, 64, 0)
        port.world.player.eye = (-.29, 65.62, .5)
        target = Vec3i(0, 64, 0)
        port.world.blocks[target] = "minecraft:cobblestone"
        port.world.solid.add(target)
        operation = BuildOperation(OperationKind.BREAK, target, "minecraft:cobblestone", "access", temporary=True)
        self.assertFalse(can_interact(operation, port.world, port.world.player.position))
        port.world.player.eye = (-.5, 65.62, .5)
        self.assertTrue(can_interact(operation, port.world, port.world.player.position))

    async def test_stop_during_approach_leaves_owned_intent(self):
        port, project, builder, target = self.fixture()
        async def navigate(goal, world):
            world.player.position = goal.target
            builder.control.stop()
            return NavigationResult(True, goal.target)
        builder.navigation.navigate = navigate
        await builder._remove_scaffold([target], project)
        port.break_block.assert_not_awaited()
        self.assertEqual(len(project.temporary_blocks), 1)

    async def test_dimension_change_during_approach_never_breaks(self):
        def hook(goal, world, target):
            world.player.position = goal.target
            world.player.dimension = "minecraft:the_nether"
            return NavigationResult(True, goal.target)
        port, project, builder, target = self.fixture(hook)
        with self.assertRaisesRegex(RuntimeError, "dimension changed"):
            await builder._remove_scaffold([target], project)
        port.break_block.assert_not_awaited()

    async def test_false_retreat_success_is_not_accepted(self):
        def hook(goal, world, target):
            return NavigationResult(True, goal.target)
        port, project, builder, target = self.fixture(hook)
        port.world.player.position = Vec3i(0, 64, 0)
        landing = Vec3i(-2, 66, 0)
        port.world.blocks[landing.offset(dy=-1)] = "minecraft:cobblestone"
        port.world.solid.add(landing.offset(dy=-1))
        project.scheduler["access_landings"] = [landing.to_dict()]
        await builder._safe_cleanup(project)
        port.break_block.assert_not_awaited()
        self.assertIn("cleanup_deferred", project.scheduler)

    async def test_wire_guard_requires_negotiated_capability(self):
        server = SimpleNamespace(metadata=AdapterMetadata("1.21.11", "dev", frozenset({"BREAK_BLOCK"}), {}),
                                 request=AsyncMock(return_value={"success": True}))
        port = FabricMinecraftPort(server)
        op = BuildOperation(OperationKind.BREAK, Vec3i(0, 64, 0), "minecraft:cobblestone", "access", temporary=True)
        with self.assertRaises(CapabilityError):
            await port.break_block(op)
        server.request.assert_not_awaited()
        server.metadata = AdapterMetadata("1.21.11", "dev", frozenset({"BREAK_BLOCK", "GUARDED_BREAK"}), {})
        self.assertTrue(await port.break_block(op))
        self.assertEqual(server.request.await_args.args[1]["expected"], {"block": "minecraft:cobblestone", "properties": {}})

    async def test_old_adapter_is_rejected_before_project_approval(self):
        _, project, _, _ = self.fixture()
        server = SimpleNamespace(metadata=AdapterMetadata("1.21.11", "old", frozenset({"BREAK_BLOCK"}), {}),
                                 request=AsyncMock())
        with self.assertRaises(CapabilityError):
            await FabricMinecraftPort(server).approve(project)
        server.request.assert_not_awaited()

    async def test_unguarded_temporary_break_is_rejected_before_transport(self):
        server = SimpleNamespace(request=AsyncMock())
        port = FabricMinecraftPort(server)
        op = BuildOperation(OperationKind.BREAK, Vec3i(0, 64, 0), None, "access", temporary=True)
        with self.assertRaisesRegex(ValueError, "precondition"):
            await port.break_block(op)
        server.request.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
