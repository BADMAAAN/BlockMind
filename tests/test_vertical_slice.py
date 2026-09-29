import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "ai-core" / "src"))

from blockmind.models import Bounds, BuildOperation, Hazard, HazardKind, OperationKind, PlayerState, Vec3i, WorldState
from blockmind.navigation import NavigationGoal, NavigationGoalKind, SafeSimulatedNavigationProvider
from blockmind.protocol import Envelope
from blockmind.runtime import BlockMindAgent, Builder, ControlState
from blockmind.simulation import SimulatedMinecraftPort


PROMPT = "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool."


class VerticalSliceTests(unittest.IsolatedAsyncioTestCase):
    async def test_acceptance_build_is_verified(self):
        origin = Vec3i(10, 64, 20)
        port = SimulatedMinecraftPort(origin.offset(dz=-2), {origin})
        project, report = await BlockMindAgent(port, SafeSimulatedNavigationProvider()).run(PROMPT, origin)
        self.assertTrue(report.verified)
        self.assertGreater(len(project.plan.operations), 500)
        self.assertIn("pool", {c.id for c in project.design.components})
        self.assertEqual(project.plan.materials["minecraft:white_concrete"] > 0, True)
        self.assertEqual(port.attempts[origin], 2, "failed placement must be observed and retried")

    async def test_navigation_rejects_hazardous_direct_position(self):
        target = Vec3i(3, 64, 3)
        world = WorldState(PlayerState(Vec3i(0, 64, 0)), hazards=[
            Hazard(HazardKind.LAVA, Bounds(target, target), 1.0)
        ])
        result = await SafeSimulatedNavigationProvider().navigate(
            NavigationGoal(NavigationGoalKind.GO_TO, target), world)
        self.assertTrue(result.success)
        self.assertTrue(result.used_alternative)
        self.assertNotEqual(result.position, target)

    async def test_destructive_operation_outside_approved_area_is_rejected(self):
        origin = Vec3i(0, 64, 0)
        port = SimulatedMinecraftPort(origin)
        agent = BlockMindAgent(port, SafeSimulatedNavigationProvider())
        project = agent.plan(PROMPT, origin)
        operation = BuildOperation(OperationKind.BREAK, Vec3i(500, 64, 500), None, "test", destructive=True)
        project.plan.operations = [operation]
        await Builder(port, SafeSimulatedNavigationProvider()).execute(project)
        self.assertEqual(operation.error, "destructive operation outside approved area")

    async def test_stop_cancels_queued_execution(self):
        origin = Vec3i(0, 64, 0)
        port = SimulatedMinecraftPort(origin)
        agent = BlockMindAgent(port, SafeSimulatedNavigationProvider())
        project = agent.plan(PROMPT, origin)
        control = ControlState()
        control.stop()
        await Builder(port, SafeSimulatedNavigationProvider(), control).execute(project)
        self.assertEqual(len(project.completed_operation_ids), 0)

    async def test_temporary_scaffold_is_installed_and_cleaned_up(self):
        origin = Vec3i(0, 64, 0)
        target = origin.offset(dy=3)
        port = SimulatedMinecraftPort(origin, {target})
        port.world.blocks[origin] = "minecraft:stone"
        agent = BlockMindAgent(port, SafeSimulatedNavigationProvider())
        project = agent.plan(PROMPT, origin)
        project.plan.operations = [BuildOperation(OperationKind.PLACE, target, "minecraft:white_concrete", "roof")]
        await Builder(port, SafeSimulatedNavigationProvider()).execute(project)
        self.assertEqual(await port.block_at(target), "minecraft:white_concrete")
        self.assertEqual(await port.block_at(origin.offset(dy=1)), "minecraft:air")
        self.assertTrue(any("temporary scaffold" in note for note in project.modifications))

    def test_protocol_envelope_is_versioned_ndjson(self):
        encoded = Envelope("action", {"kind": "observe_block"}, id="request-1").encode()
        self.assertTrue(encoded.endswith(b"\n"))
        value = json.loads(encoded)
        self.assertEqual(value["protocol"], "0.1.0")
        self.assertEqual(value["id"], "request-1")


if __name__ == "__main__":
    unittest.main()
