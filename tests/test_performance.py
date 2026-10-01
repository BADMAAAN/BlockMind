import asyncio
import tempfile
import unittest
from pathlib import Path
from blockmind.execution import ExecutionConfig, OperationClass, BuildPlanOptimizer, classify
from blockmind.models import BuildOperation, OperationKind, Vec3i, ProjectStatus
from blockmind.runtime import BlockMindAgent, Builder, Validator, ControlState
from blockmind.navigation import SafeSimulatedNavigationProvider
from blockmind.simulation import SimulatedMinecraftPort

PROMPT = "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool."


class PerformanceTests(unittest.IsolatedAsyncioTestCase):
    def setup_project(self, count=16):
        class FastPort(SimulatedMinecraftPort): supports_fast = True
        port = FastPort()
        project = BlockMindAgent(port, SafeSimulatedNavigationProvider()).plan(PROMPT, Vec3i(0,64,0))
        project.plan.operations = [BuildOperation(OperationKind.PLACE, Vec3i(i%4,64,i//4), "minecraft:stone", "foundation") for i in range(count)]
        return port, project

    def test_profiles_and_configuration(self):
        self.assertEqual([ExecutionConfig(speed_profile=p, max_action_batch=32).batch_size for p in ("safe","normal","fast","max")], [1,4,16,32])
        with self.assertRaises(ValueError): ExecutionConfig(max_action_batch=100)
        with self.assertRaises(ValueError): ExecutionConfig(placement_radius=8)
        with self.assertRaises(ValueError): ExecutionConfig(max_action_batch=True)
        with self.assertRaises(ValueError): ExecutionConfig(max_action_batch=2.5)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"settings.toml"
            path.write_text('[execution]\nspeed_profile="max"\n[audio]\nmute_game_audio=false\n',encoding="utf-8")
            self.assertEqual(ExecutionConfig.load(path).speed_profile,"max")
            self.assertFalse(ExecutionConfig.load(path).mute_game_audio)

    def test_sensitive_operations_never_use_simple_policy(self):
        self.assertEqual(classify(BuildOperation(OperationKind.PLACE,Vec3i(0,64,0),"minecraft:stone","test")),OperationClass.SIMPLE)
        for block in ("oak_stairs","oak_door","oak_log","oak_slab","oak_trapdoor","lever","repeater","comparator","observer","piston"):
            self.assertNotEqual(classify(BuildOperation(OperationKind.PLACE,Vec3i(0,64,0),"minecraft:"+block,"test")),OperationClass.SIMPLE)
        self.assertEqual(classify(BuildOperation(OperationKind.BREAK,Vec3i(0,64,0),None,"test")),OperationClass.DESTRUCTIVE)

    def test_optimizer_keeps_geometry_dependencies_and_groups_component_layers(self):
        port, project=self.setup_project()
        raw=list(project.plan.operations)
        ordered=BuildPlanOptimizer().optimize(project.plan)
        self.assertEqual(project.plan.operations,raw)
        self.assertEqual({op.id for op in raw},{op.id for op in ordered})
        self.assertEqual([op.position.x for op in ordered[:8]],[0,1,2,3,3,2,1,0])
        raw[-1].depends_on=[raw[0].id]
        self.assertLess(ordered.index(raw[0]),ordered.index(raw[-1]))
        raw[0].depends_on=[raw[-1].id]
        with self.assertRaises(ValueError): BuildPlanOptimizer().optimize(project.plan)

    async def test_batched_failure_is_detected_and_locally_repaired(self):
        port, project=self.setup_project()
        original=port.place_batch
        dropped=project.plan.operations[0]
        calls=[]
        async def batch(operations):
            calls.append(len(operations))
            return await original([op for op in operations if op.id != dropped.id])
        port.place_batch=batch
        builder=Builder(port,SafeSimulatedNavigationProvider(),config=ExecutionConfig())
        await builder.execute(project)
        self.assertTrue((await Validator().validate(project,port)).verified)
        self.assertGreater(builder.metrics.counts["repair_operations"],0)
        self.assertTrue(any(size>1 for size in calls))
        self.assertEqual(builder.metrics.counts["blocks_placed"],len(project.plan.operations))

    async def test_stop_prevents_subsequent_batches(self):
        port, project=self.setup_project(32)
        entered=asyncio.Event(); release=asyncio.Event(); calls=[]
        async def batch(operations):
            calls.append(len(operations)); entered.set(); await release.wait(); return []
        port.place_batch=batch
        control=ControlState()
        task=asyncio.create_task(Builder(port,SafeSimulatedNavigationProvider(),control,config=ExecutionConfig(speed_profile="max")).execute(project))
        await entered.wait(); control.stop(); release.set(); await task
        self.assertEqual(len(calls),1)
        self.assertEqual(project.status,ProjectStatus.STOPPED)

    async def test_survival_uses_strict_execution_even_in_max(self):
        port, project=self.setup_project(4)
        port.world.player.creative=False
        async def forbidden(_): raise AssertionError("Survival must not batch")
        port.place_batch=forbidden
        await Builder(port,SafeSimulatedNavigationProvider(),config=ExecutionConfig(speed_profile="max")).execute(project)
        self.assertTrue((await Validator().validate(project,port)).verified)

    async def test_final_scan_detects_late_damage_and_triggers_strict_repair(self):
        port, project = self.setup_project(4)
        original = port.scan_region
        calls = 0
        async def damaged_scan(bounds):
            nonlocal calls
            calls += 1
            if calls == 2:  # Baseline, then authoritative final scan.
                port.world.blocks.pop(project.plan.operations[0].position, None)
            return await original(bounds)
        port.scan_region = damaged_scan
        agent = BlockMindAgent(port, SafeSimulatedNavigationProvider())
        project, report = await agent.run_project(project)
        self.assertTrue(report.verified)
        self.assertEqual(project.status, ProjectStatus.COMPLETE)
        self.assertEqual(project.performance["counts"]["final_repair_operations"], 1)
        self.assertGreaterEqual(calls, 3)

    async def test_interaction_reuse_reduces_navigation_and_preserves_materials(self):
        port, project = self.setup_project(16)
        class CountingNavigation(SafeSimulatedNavigationProvider):
            calls = 0
            async def navigate(self, goal, world):
                self.calls += 1
                return await super().navigate(goal, world)
        navigation = CountingNavigation()
        builder = Builder(port, navigation, config=ExecutionConfig())
        await builder.execute(project)
        self.assertTrue((await Validator().validate(project, port)).verified)
        self.assertLess(navigation.calls, 16)
        self.assertEqual({op.block for op in project.plan.operations}, {"minecraft:stone"})

    async def test_pending_configuration_does_not_block_reading_emergency_stop(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from blockmind.cli import interactive
        queue = asyncio.Queue()
        entered, stopped, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()
        class Port:
            async def configure_execution(self, config):
                entered.set()
                try: await asyncio.Event().wait()
                finally: cancelled.set()
        async def control(kind):
            self.assertEqual(kind, "emergency_stop")
            stopped.set()
        agent = SimpleNamespace(config=ExecutionConfig(), port=Port(), send_control=control)
        with patch("blockmind.cli.asyncio.Queue", return_value=queue), patch("blockmind.cli.threading.Thread"):
            task = asyncio.create_task(interactive(agent, None))
            try:
                await queue.put("speed max")
                await asyncio.wait_for(entered.wait(), 1)
                await queue.put("emergency-stop")
                await asyncio.wait_for(stopped.wait(), 1)
                self.assertTrue(cancelled.is_set())
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
