import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from blockmind.models import BuildOperation, OperationKind, Vec3i
from blockmind.navigation import SafeSimulatedNavigationProvider
from blockmind.runtime import BlockMindAgent, ProjectStore
from blockmind.scheduler import ConstructionScheduler, Traversal, route_quality, zone_id
from blockmind.simulation import SimulatedMinecraftPort

PROMPT = "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool."


def fixture():
    project = BlockMindAgent(SimulatedMinecraftPort(), SafeSimulatedNavigationProvider()).plan(PROMPT, Vec3i(0,64,0))
    operations = []
    for i in range(4):
        for side, position in (("north", Vec3i(2+i,66,0)), ("south", Vec3i(2+i,66,12)),
                               ("east", Vec3i(16,66,2+i)), ("west", Vec3i(0,66,2+i))):
            operations.append(BuildOperation(OperationKind.PLACE, position, "minecraft:glass_pane", "floor_1.wall_"+side))
    project.plan.operations = operations
    return project


class SchedulerTests(unittest.TestCase):
    def test_semantic_phase_and_top_down_floating_arm_support(self):
        from blockmind.models import StructureComponent, Bounds
        project = fixture()
        arm = [BuildOperation(OperationKind.PLACE,Vec3i(0,y,0),"minecraft:stone","arm") for y in (64,66,65)]
        shoulder = BuildOperation(OperationKind.PLACE,Vec3i(0,67,0),"minecraft:stone","shoulder")
        project.plan.operations = arm+[shoulder]
        bounds = Bounds(Vec3i(0,64,0),Vec3i(0,67,0))
        project.design.components = [StructureComponent("arm","limb",bounds,metadata={"phase":1,"support_order":"above"}),
                                     StructureComponent("shoulder","support",bounds,metadata={"phase":0,"support_order":"explicit"})]
        ordered = ConstructionScheduler().optimize(project.plan)
        self.assertEqual([op.position.y for op in ordered],[67,66,65,64])
        project.design.components[0].metadata["phase"] = True
        with self.assertRaises(ValueError): ConstructionScheduler().optimize(project.plan)

    def test_four_sides_ping_pong_regression_equal_geometry_less_backtracking(self):
        project = fixture()
        raw = list(project.plan.operations)
        ordered = ConstructionScheduler().optimize(project.plan)
        self.assertEqual(project.plan.operations, raw)
        self.assertEqual({op.id for op in ordered}, {op.id for op in raw})
        self.assertEqual(route_quality(ordered)["region_switches"], 3)
        self.assertEqual(route_quality(ordered)["backtracks"], 0)
        self.assertGreater(route_quality(raw)["backtracks"], 0)
        self.assertLess(route_quality(ordered)["target_route_distance_blocks"], route_quality(raw)["target_route_distance_blocks"])

    def test_clockwise_and_counter_clockwise_keep_direction(self):
        project = fixture()
        for direction, expected in ((Traversal.CLOCKWISE, ["north","east","south","west"]),
                                    (Traversal.COUNTER_CLOCKWISE, ["north","west","south","east"])):
            ordered = ConstructionScheduler().optimize(project.plan, start=Vec3i(3,66,-1), direction=direction)
            self.assertEqual(list(dict.fromkeys(zone_id(op).split("wall_")[-1] for op in ordered)), expected)

    def test_direction_selected_from_initial_position(self):
        project = fixture()
        left, right = ConstructionScheduler(), ConstructionScheduler()
        # Symmetric full facades isolate entry cost from remaining-route cost.
        for op in project.plan.operations:
            if op.component_id.endswith(("north", "south")):
                op.position = Vec3i(2+(op.position.x-2)*4, 66, op.position.z)
        left.optimize(project.plan, start=Vec3i(2,66,-1))
        right.optimize(project.plan, start=Vec3i(14,66,-1))
        self.assertEqual(left.direction, "clockwise")
        self.assertEqual(right.direction, "counter_clockwise")

    def test_linear_walk_does_not_reverse_at_every_material_switch(self):
        project = fixture()
        project.plan.operations = [BuildOperation(OperationKind.PLACE, Vec3i(x,64,0),
            "minecraft:glass_pane" if x%2 else "minecraft:stone", "beam") for x in range(10)]
        ordered = ConstructionScheduler().optimize(project.plan, start=Vec3i(12,64,0))
        self.assertEqual([op.position.x for op in ordered], list(range(9,-1,-1)))

    def test_serpentine_floor(self):
        project = fixture()
        project.plan.operations = [BuildOperation(OperationKind.PLACE, Vec3i(x,64,z), "minecraft:stone", "floor")
                                   for z in range(3) for x in range(4)]
        ordered = ConstructionScheduler().optimize(project.plan)
        self.assertEqual([op.position.x for op in ordered], [0,1,2,3,3,2,1,0,0,1,2,3])

    def test_tower_layers_and_vertical_support(self):
        project = fixture()
        project.plan.operations = [BuildOperation(OperationKind.PLACE, Vec3i(0,y,0), "minecraft:stone", "tower") for y in (67,65,66,64)]
        self.assertEqual([op.position.y for op in ConstructionScheduler().optimize(project.plan)], [64,65,66,67])

    def test_active_component_finishes_before_slightly_closer_region(self):
        project = fixture()
        ordered = ConstructionScheduler().optimize(project.plan, active_zone="floor_1.wall_south", start=Vec3i(2,66,-1))
        self.assertEqual(zone_id(ordered[0]), "floor_1.wall_south")
        self.assertEqual(len([op for op in ordered[:4] if zone_id(op)=="floor_1.wall_south"]), 4)

    def test_dependency_override_postpones_zone_and_returns(self):
        project = fixture()
        north = [op for op in project.plan.operations if zone_id(op).endswith("north")]
        east = next(op for op in project.plan.operations if zone_id(op).endswith("east"))
        for op in north: op.depends_on = [east.id]
        ordered = ConstructionScheduler().optimize(project.plan, active_zone="floor_1.wall_north")
        self.assertLess(ordered.index(east), min(ordered.index(op) for op in north))

    def test_unknown_or_cyclic_dependencies_rejected(self):
        project = fixture()
        project.plan.operations[0].depends_on = ["missing"]
        with self.assertRaises(ValueError): ConstructionScheduler().optimize(project.plan)
        project.plan.operations[0].depends_on = [project.plan.operations[1].id]
        project.plan.operations[1].depends_on = [project.plan.operations[0].id]
        with self.assertRaises(ValueError): ConstructionScheduler().optimize(project.plan)

    def test_house_phases_do_not_return_to_lower_walls_after_roof(self):
        project = BlockMindAgent(SimulatedMinecraftPort(), SafeSimulatedNavigationProvider()).plan(PROMPT, Vec3i(0,64,0))
        ordered = ConstructionScheduler().optimize(project.plan)
        positions = {op.id:i for i,op in enumerate(ordered)}
        for op in ordered:
            self.assertTrue(all(positions[dep] < positions[op.id] for dep in op.depends_on))
        components = list(dict.fromkeys(zone_id(op) for op in ordered))
        self.assertLess(components.index("floor_1.wall_west"), components.index("floor_2.slab"))
        self.assertLess(components.index("floor_2.wall_west"), components.index("roof"))

    def test_transient_checkpoint_permission_error_retries_only_rename(self):
        project=fixture()
        with tempfile.TemporaryDirectory() as folder:
            store=ProjectStore(Path(folder)); path=store.save(project)
            project.scheduler={'active_zone':'north'}
            real_replace=os.replace
            attempts=[]
            def transient(source,target):
                attempts.append((source,target))
                if len(attempts)<3: raise PermissionError('controlled transient reader')
                real_replace(source,target)
            with patch('blockmind.runtime.os.replace',side_effect=transient), patch('blockmind.runtime.sleep') as delay:
                store.save(project)
            self.assertEqual(len(attempts),3)
            self.assertEqual(delay.call_count,2)
            self.assertEqual(store.load(path).scheduler,project.scheduler)

    def test_persistent_checkpoint_permission_error_is_bounded_and_preserves_old(self):
        project=fixture()
        with tempfile.TemporaryDirectory() as folder:
            store=ProjectStore(Path(folder)); path=store.save(project); old=path.read_bytes()
            project.scheduler={'active_zone':'north'}
            with patch('blockmind.runtime.os.replace',side_effect=PermissionError('controlled persistent failure')) as rename, patch('blockmind.runtime.sleep'):
                with self.assertRaises(PermissionError): store.save(project)
            self.assertEqual(rename.call_count,6)
            self.assertEqual(path.read_bytes(),old)

    def test_interrupted_atomic_replace_preserves_old_checkpoint(self):
        project = fixture()
        with tempfile.TemporaryDirectory() as folder:
            store = ProjectStore(Path(folder))
            path = store.save(project)
            old = path.read_bytes()
            project.scheduler = {"active_zone":"north", "active_batch":[project.plan.operations[0].id]}
            with patch("blockmind.runtime.os.replace", side_effect=OSError("controlled interruption")):
                with self.assertRaises(OSError): store.save(project)
            self.assertEqual(path.read_bytes(), old)
            loaded = store.load(store.save(project))
            self.assertEqual(loaded.scheduler, project.scheduler)


if __name__ == "__main__": unittest.main()
