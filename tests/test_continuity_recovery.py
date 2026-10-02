import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

from blockmind.execution import ExecutionConfig
from blockmind.models import BuildOperation, OperationKind, Vec3i, Bounds
from blockmind.network import FabricMinecraftPort
from blockmind.navigation import NavigationResult, SafeSimulatedNavigationProvider, failure_kind
from blockmind.runtime import BlockMindAgent, Builder, ControlState, ProjectStore, Validator
from blockmind.simulation import SimulatedMinecraftPort
from blockmind.interaction import can_interact, candidates

PROMPT = "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool."


class ContinuityRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_eight_wide_head_floor_finishes_with_strict_interaction_geometry(self):
        from blockmind.reference_builds import enderman_project
        from blockmind.models import OperationStatus
        project=enderman_project(Vec3i(0,64,0))
        port=SimulatedMinecraftPort(Vec3i(-1,105,0))
        port.world.player.creative=True; port.world.player.flying=True
        port.world.observed_bounds=project.plan.approved_area
        phases={component.id:component.metadata.get('phase',100) for component in project.design.components}
        for op in project.plan.operations:
            if phases[op.component_id]<5:
                port.world.blocks[op.position]=op.block
                port.world.solid.add(op.position)
                project.completed_operation_ids.append(op.id)
        original_place=port.place_block
        async def place(op):
            success=await original_place(op)
            if success: port.world.solid.add(op.position)
            return success
        async def terrain(target): return port.world
        port.place_block=place; port.interaction_world=terrain
        floor=[op for op in project.plan.operations if op.component_id=='statue.head_base']
        builder=Builder(port,SafeSimulatedNavigationProvider(),config=ExecutionConfig(creative_flight=True))
        await builder._execute_strict(project,operations=floor,cleanup=False)
        self.assertEqual(len(floor),64)
        self.assertTrue(all(op.status==OperationStatus.COMPLETE for op in floor),project.failures)
        self.assertEqual(project.failures,[])
        self.assertEqual(len(port.attempts),64)

    async def test_strict_mutation_rechecks_actual_arrival_pose_not_only_virtual_candidate(self):
        port=SimulatedMinecraftPort(Vec3i(-5,64,0))
        port.world.player.flying=True
        port.world.observed_bounds=Bounds(Vec3i(-5,55,-5),Vec3i(5,75,5))
        target=Vec3i(1,65,0); support=target.offset(dy=-1)
        port.world.blocks[support]='minecraft:stone'; port.world.solid.add(support)
        async def terrain(position): return port.world
        port.interaction_world=terrain
        agent=BlockMindAgent(port,SafeSimulatedNavigationProvider())
        project=agent.plan(PROMPT,Vec3i(0,64,0))
        operation=BuildOperation(OperationKind.PLACE,target,'minecraft:stone','foundation')
        project.plan.operations=[operation]
        class WrongArrival(SafeSimulatedNavigationProvider):
            async def navigate(self,goal,world):
                world.player.position=target.offset(dy=-2)
                world.player.eye=(1.5,64.27,.5)
                return NavigationResult(True,world.player.position,'test claimed arrival')
        builder=Builder(port,WrongArrival(),config=ExecutionConfig(creative_flight=True))
        await builder._execute_strict(project,operations=[operation],cleanup=False)
        self.assertEqual(port.attempts,{})
        self.assertEqual(builder.metrics.counts['operation_attempts'],0)
        self.assertIn('actual arrival pose',operation.error)

    async def test_stop_during_live_read_ends_project_without_replay_or_final_scan(self):
        from blockmind.runtime import ExecutionStopped
        from blockmind.models import ProjectStatus
        control=ControlState(); calls=[]
        async def request(kind,payload,**options):
            calls.append(kind); control.stop()
            return {'success':False,'reason':'stop'}
        live=FabricMinecraftPort(SimpleNamespace(request=request)); live.control_state=control
        with self.assertRaises(ExecutionStopped): await live._read_request('observe',{})
        with self.assertRaises(ExecutionStopped): await live._read_request('observe',{})
        self.assertEqual(calls,['observe'])
        port=SimulatedMinecraftPort(); agent=BlockMindAgent(port,SafeSimulatedNavigationProvider())
        project=agent.plan(PROMPT,Vec3i(0,64,0))
        async def interrupted(builder,project,on_progress=None):
            agent.control.stop(); raise ExecutionStopped('stop')
        with patch.object(Builder,'execute',new=interrupted), patch.object(Validator,'validate',new_callable=AsyncMock) as scan:
            _,report=await agent.run_project(project)
            scan.assert_not_awaited()
        self.assertEqual(project.status,ProjectStatus.STOPPED)
        self.assertFalse(report.verified)
        self.assertEqual(project.validation['reason'],'stopped; final scan not performed')

    async def test_failed_burst_support_is_repaired_before_dependent_descendants(self):
        port=SimulatedMinecraftPort()
        port.supports_fast=True
        port.world.player.creative=True
        agent=BlockMindAgent(port,SafeSimulatedNavigationProvider(),config=ExecutionConfig(speed_profile='fast'))
        project=agent.plan(PROMPT,Vec3i(0,64,0))
        root=BuildOperation(OperationKind.PLACE,Vec3i(0,64,0),'minecraft:stone','beam',id='root')
        descendants=[BuildOperation(OperationKind.PLACE,Vec3i(x,64,0),'minecraft:stone','beam',
                                    id=f'child{x}',depends_on=['root']) for x in range(1,12)]
        project.plan.operations=[root]+descendants
        original=port.place_batch
        first=True
        async def reject_first(operations):
            nonlocal first
            if first:
                first=False
                return [{'id':op.id,'issued':False,'reason':'controlled support rejection'} for op in operations]
            return await original(operations)
        port.place_batch=reject_first
        builder=Builder(port,agent.navigation,config=agent.config)
        await builder.execute(project)
        self.assertEqual(set(project.completed_operation_ids),{'root'}|{op.id for op in descendants})
        self.assertFalse(project.failures)
        self.assertGreater(builder.metrics.counts['repair_operations'],0)

    async def test_enclosed_cleanup_failure_keeps_final_scan_without_more_mutations(self):
        from blockmind.models import ProjectStatus
        port = SimulatedMinecraftPort()
        agent = BlockMindAgent(port,SafeSimulatedNavigationProvider())
        project = agent.plan(PROMPT,Vec3i(0,64,0))
        project.plan.operations = [BuildOperation(OperationKind.PLACE,Vec3i(0,64,0),"minecraft:stone","beam")]
        async def enclosed(builder, project, on_progress=None):
            project.scheduler["cleanup_deferred"] = "outside retreat unreachable"
            project.status = ProjectStatus.FAILED
        with patch.object(Builder,"execute",new=enclosed), patch.object(Builder,"_execute_strict",new_callable=AsyncMock) as repair:
            _, report = await agent.run_project(project)
            repair.assert_not_awaited()
        self.assertEqual(report.missing,1)
        self.assertFalse(report.verified)
        self.assertEqual(project.performance["counts"]["final_repair_refused_unsafe_retreat"],1)

    async def test_house_phase_feet_prevent_lower_floor_and_interior_facade_work(self):
        project = BlockMindAgent(SimulatedMinecraftPort(),SafeSimulatedNavigationProvider()).plan(PROMPT,Vec3i(0,64,0))
        slab = BuildOperation(OperationKind.PLACE,Vec3i(1,68,1),"minecraft:stone","floor_2.slab")
        wall = BuildOperation(OperationKind.PLACE,Vec3i(0,66,1),"minecraft:stone","floor_1.wall_west")
        upper = BuildOperation(OperationKind.PLACE,Vec3i(0,70,1),"minecraft:stone","floor_2.wall_west")
        self.assertFalse(Builder._construction_feet_allowed(slab,Vec3i(1,66,1),project))
        self.assertTrue(Builder._construction_feet_allowed(slab,Vec3i(-1,69,1),project))
        self.assertFalse(Builder._construction_feet_allowed(wall,Vec3i(1,66,1),project))
        self.assertTrue(Builder._construction_feet_allowed(wall,Vec3i(-1,64,1),project))
        self.assertFalse(Builder._construction_feet_allowed(upper,Vec3i(-1,66,1),project))
        self.assertTrue(Builder._construction_feet_allowed(upper,Vec3i(-1,71,1),project))

    async def test_final_temporary_count_observes_world_not_unapplied_intents(self):
        port = SimulatedMinecraftPort()
        project = BlockMindAgent(port, SafeSimulatedNavigationProvider()).plan(PROMPT, Vec3i(0,64,0))
        project.plan.operations = []
        absent, present = Vec3i(-2,64,0), Vec3i(-3,64,0)
        project.temporary_blocks = [{"position":p.to_dict(),"block":"minecraft:cobblestone"} for p in (absent,present)]
        port.world.blocks[present] = "minecraft:cobblestone"
        report = await Validator().validate(project,port)
        self.assertEqual(report.temporary_remaining,1)
        self.assertEqual(project.temporary_blocks,[{"position":present.to_dict(),"block":"minecraft:cobblestone"}])
        self.assertFalse(report.verified)

    async def test_pause_aborts_read_then_resume_retries_read_only(self):
        control = ControlState()
        entered = asyncio.Event()
        calls = []
        async def request(kind, payload, **options):
            calls.append(kind)
            if len(calls)==1:
                control.pause(); entered.set()
                return {"success":False, "reason":"paused"}
            return {"success":True}
        port = FabricMinecraftPort(SimpleNamespace(request=request))
        port.control_state = control
        task = asyncio.create_task(port._read_request("observe", {}))
        await entered.wait(); await asyncio.sleep(.01)
        self.assertEqual(calls, ["observe"])
        control.resume()
        self.assertTrue((await task)["success"])
        self.assertEqual(calls, ["observe","observe"])

    async def test_unreachable_operation_is_postponed_other_work_then_return(self):
        port = SimulatedMinecraftPort()
        project = BlockMindAgent(port, SafeSimulatedNavigationProvider()).plan(PROMPT, Vec3i(0,64,0))
        project.plan.operations = [BuildOperation(OperationKind.PLACE,Vec3i(i,64,0),"minecraft:stone","beam") for i in range(3)]
        class RecoveryNavigation(SafeSimulatedNavigationProvider):
            calls=0
            async def navigate(self, goal, world):
                self.calls+=1
                if self.calls<=3: return NavigationResult(False,world.player.position,"unreachable")
                return await super().navigate(goal,world)
        builder = Builder(port, RecoveryNavigation())
        await builder.execute(project)
        self.assertTrue((await Validator().validate(project,port)).verified)
        self.assertEqual(builder.metrics.counts["postponed_operations"],1)
        self.assertFalse(project.failures)

    async def test_fast_stateful_work_zone_halts_after_ten_failed_operations(self):
        class FastPort(SimulatedMinecraftPort): supports_fast=True
        class FailingNavigation(SafeSimulatedNavigationProvider):
            async def navigate(self, goal, world):
                return NavigationResult(False,world.player.position,"unreachable")
        port=FastPort()
        project=BlockMindAgent(port,FailingNavigation()).plan(PROMPT,Vec3i(0,64,0))
        project.plan.operations=[BuildOperation(OperationKind.PLACE,Vec3i(i,64,0),
            "minecraft:glass_pane","window") for i in range(64)]
        builder=Builder(port,FailingNavigation(),config=ExecutionConfig())
        await builder.execute(project)
        self.assertEqual(sum(op.attempts for op in project.plan.operations),30)
        self.assertEqual(len(project.failures),10)
        self.assertFalse(any(op.attempts for op in project.plan.operations[10:]))
        self.assertFalse(port.attempts)

    async def test_resume_partial_window_and_owned_temporary_reconciles_actual_world(self):
        port = SimulatedMinecraftPort()
        agent = BlockMindAgent(port, SafeSimulatedNavigationProvider())
        project = agent.plan(PROMPT,Vec3i(0,64,0))
        project.plan.operations = [BuildOperation(OperationKind.PLACE,Vec3i(i,64,0),"minecraft:glass_pane","window") for i in range(3)]
        project.completed_operation_ids = [op.id for op in project.plan.operations]
        port.world.blocks[project.plan.operations[0].position] = "minecraft:glass_pane"
        temporary = Vec3i(-2,64,0)
        port.world.blocks[temporary] = "minecraft:cobblestone"
        project.temporary_blocks = [{"position":temporary.to_dict(),"block":"minecraft:cobblestone"}]
        project.scheduler = {"active_zone":"window", "active_batch":[project.plan.operations[1].id]}
        with tempfile.TemporaryDirectory() as folder:
            store = ProjectStore(Path(folder))
            loaded = store.load(store.save(project))
            loaded, report = await agent.run_project(loaded, store=store, reconcile=True)
        self.assertTrue(report.verified)
        self.assertEqual(loaded.scheduler["reconciliation"]["missing"],2)
        self.assertEqual(loaded.scheduler["reconciliation"]["owned_temporary"],1)
        self.assertFalse(loaded.temporary_blocks)

    def test_navigation_failure_taxonomy(self):
        for reason, expected in (("stale route","stale_route"),("unsafe drop","unsafe_drop"),
                                 ("terrain unloaded","unloaded_region"),("API error","provider_failure")):
            self.assertEqual(failure_kind(reason),expected)

    def test_high_horizontal_extension_can_use_ground_and_visible_side_face(self):
        port = SimulatedMinecraftPort(Vec3i(-1,64,0))
        world = port.world
        world.observed_bounds = Bounds(Vec3i(-5,58,-5),Vec3i(5,70,5))
        for x in range(-5,6):
            for z in range(-5,6):
                point = Vec3i(x,63,z); world.blocks[point]="minecraft:stone"; world.solid.add(point)
        adjacent = Vec3i(1,68,0)
        world.blocks[adjacent]="minecraft:white_concrete"; world.solid.add(adjacent)
        operation = BuildOperation(OperationKind.PLACE,Vec3i(0,68,0),"minecraft:white_concrete","wall")
        self.assertTrue(any(candidate.feet.y==64 for candidate in candidates(operation,world,reach=3.8)))

    def test_cleanup_cannot_break_the_only_block_under_current_feet(self):
        port = SimulatedMinecraftPort(Vec3i(0,65,0))
        operation = BuildOperation(OperationKind.BREAK,Vec3i(0,64,0),None,"access",temporary=True)
        self.assertFalse(can_interact(operation,port.world,port.world.player.position))

    async def test_cleanup_refuses_to_dismantle_access_when_enclosed_and_retreat_failed(self):
        class FailingNavigation(SafeSimulatedNavigationProvider):
            async def navigate(self,goal,world): return NavigationResult(False,world.player.position,"unreachable")
        port=SimulatedMinecraftPort(Vec3i(0,64,0))
        project=BlockMindAgent(port,FailingNavigation()).plan(PROMPT,Vec3i(0,64,0))
        point=Vec3i(-2,64,0)
        port.world.blocks[point]="minecraft:cobblestone"
        project.temporary_blocks=[{"position":point.to_dict(),"block":"minecraft:cobblestone"}]
        project.scheduler["access_landings"]=[point.offset(dy=1).to_dict()]
        builder=Builder(port,FailingNavigation())
        await builder._safe_cleanup(project)
        self.assertEqual(await port.block_at(point),"minecraft:cobblestone")
        self.assertEqual(len(project.temporary_blocks),1)
        self.assertEqual(builder.metrics.counts["cleanup_refused_unsafe_retreat"],1)

    async def test_shared_access_levels_are_supported_reused_and_cleaned(self):
        # Geometric/ownership test only: simulation is not a physics/live proof.
        for component in ("floor_1.wall_north", "floor_2.wall_north", "roof"):
            with self.subTest(component=component):
                port = SimulatedMinecraftPort(Vec3i(-3,64,0))
                agent = BlockMindAgent(port,SafeSimulatedNavigationProvider())
                project = agent.plan(PROMPT,Vec3i(0,64,0))
                project.design.parameters.update(width=3,depth=3)
                project.plan.operations=[]
                for x in range(-14,6):
                    for z in range(-2,6): port.world.blocks[Vec3i(x,63,z)]="minecraft:stone"
                for x in range(3):
                    for z in range(3):
                        for y in (65,69): port.world.blocks[Vec3i(x,y,z)]="minecraft:dark_oak_planks"
                original = port.place_block
                async def supported(operation):
                    self.assertTrue(any(port.world.block_at(operation.position.offset(dx,dy,dz))!="minecraft:air"
                        for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))))
                    return await original(operation)
                port.place_block=supported
                builder = Builder(port,SafeSimulatedNavigationProvider())
                op = BuildOperation(OperationKind.PLACE,Vec3i(0,70,0),"minecraft:stone",component)
                await builder._prepare_zone_access(op,project)
                count=len(project.temporary_blocks)
                self.assertGreater(count,0)
                await builder._prepare_zone_access(op,project)
                self.assertEqual(len(project.temporary_blocks),count)
                await builder._remove_scaffold([Vec3i(**entry["position"]) for entry in list(project.temporary_blocks)],project)
                self.assertFalse(project.temporary_blocks)

    async def test_shared_access_retries_one_rejected_placement_from_another_position(self):
        port=SimulatedMinecraftPort(Vec3i(-3,64,0))
        project=BlockMindAgent(port,SafeSimulatedNavigationProvider()).plan(PROMPT,Vec3i(0,64,0))
        project.design.parameters.update(width=3,depth=3)
        project.plan.operations=[]
        for x in range(-14,6):
            for z in range(-2,6): port.world.blocks[Vec3i(x,63,z)]="minecraft:stone"
        original=port.place_block
        calls=0
        async def rejected_once(operation):
            nonlocal calls
            calls+=1
            return False if calls==1 else await original(operation)
        port.place_block=rejected_once
        builder=Builder(port,SafeSimulatedNavigationProvider())
        op=BuildOperation(OperationKind.PLACE,Vec3i(0,66,0),"minecraft:stone","floor_1.wall_north")
        await builder._prepare_zone_access(op,project)
        self.assertIn(66,builder._access_levels)
        for entry in project.temporary_blocks:
            self.assertEqual(await port.block_at(Vec3i(**entry["position"])), entry["block"])

    async def test_interruption_in_component_scaffold_window_and_validation_resumes(self):
        for phase in ("component", "scaffold", "window", "validation"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                class FastPort(SimulatedMinecraftPort): supports_fast=True
                port=FastPort(Vec3i(-3,64,0))
                agent=BlockMindAgent(port,SafeSimulatedNavigationProvider())
                project=agent.plan(PROMPT,Vec3i(0,64,0))
                project.plan.operations=[BuildOperation(OperationKind.PLACE,Vec3i(x,64,0),
                    "minecraft:glass_pane" if phase=="window" else "minecraft:stone", "window" if phase=="window" else "foundation") for x in range(4)]
                if phase=="scaffold":
                    temporary=Vec3i(-2,64,2)
                    project.temporary_blocks=[{"position":temporary.to_dict(),"block":"minecraft:cobblestone"}]
                    port.world.blocks[temporary]="minecraft:cobblestone"
                store=ProjectStore(Path(directory))
                original_place, original_batch, original_validate=port.place_block,port.place_batch,port.validate_operations
                if phase=="window":
                    async def interrupted_place(op):
                        await original_place(op)
                        raise ConnectionError("controlled interruption after mutation")
                    port.place_block=interrupted_place
                elif phase=="validation":
                    async def interrupted_validate(ops): raise ConnectionError("controlled component-validation interruption")
                    port.validate_operations=interrupted_validate
                else:
                    async def interrupted_batch(ops):
                        await original_batch(ops[:1])
                        raise ConnectionError("controlled batch interruption")
                    port.place_batch=interrupted_batch
                with self.assertRaises(ConnectionError): await agent.run_project(project,store=store)
                loaded=store.load(next(Path(directory).glob("*.json")))
                port.place_block,port.place_batch,port.validate_operations=original_place,original_batch,original_validate
                before=port.attempts.get(loaded.plan.operations[0].position,0)
                resumed=BlockMindAgent(port,SafeSimulatedNavigationProvider())
                loaded,report=await resumed.run_project(loaded,store=store,reconcile=True)
                self.assertTrue(report.verified)
                self.assertEqual(port.attempts.get(loaded.plan.operations[0].position,0),before,
                    "confirmed actual mutation is not replayed after interruption")


if __name__ == "__main__": unittest.main()
