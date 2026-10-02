import unittest
from blockmind.models import Vec3i
from blockmind.reference_builds import ENDERMAN_LEGS
from blockmind.scheduler import ConstructionScheduler
from blockmind.execution import classify, OperationClass


class ReferenceBuildTests(unittest.TestCase):
    def test_open_head_floor_allows_above_access_but_not_underneath_or_closing_walls(self):
        from blockmind.reference_builds import enderman_project
        from blockmind.runtime import Builder
        project=enderman_project(Vec3i(0,64,0))
        floor=next(op for op in project.plan.operations if op.component_id=='statue.head_base')
        wall=next(op for op in project.plan.operations if op.component_id=='statue.head_front')
        self.assertTrue(Builder._construction_feet_allowed(floor,Vec3i(3,105,3),project))
        self.assertFalse(Builder._construction_feet_allowed(floor,Vec3i(3,104,3),project))
        self.assertFalse(Builder._construction_feet_allowed(floor,Vec3i(3,101,3),project))
        self.assertFalse(Builder._construction_feet_allowed(wall,Vec3i(3,105,3),project))

    def test_shell_access_excludes_whole_hollow_volume_not_just_one_wall_plane(self):
        from blockmind.reference_builds import enderman_project
        from blockmind.runtime import Builder
        project=enderman_project(Vec3i(0,64,0))
        torso=next(op for op in project.plan.operations if op.component_id=='statue.torso_north')
        head=next(op for op in project.plan.operations if op.component_id=='statue.head_front')
        self.assertFalse(Builder._construction_feet_allowed(torso,Vec3i(3,95,5),project))
        self.assertTrue(Builder._construction_feet_allowed(torso,Vec3i(3,95,3),project))
        self.assertFalse(Builder._construction_feet_allowed(head,Vec3i(3,107,3),project))
        self.assertFalse(Builder._construction_feet_allowed(head,Vec3i(3,102,3),project))  # avoid under-cap hover trap
        self.assertFalse(Builder._construction_feet_allowed(head,Vec3i(3,101,3),project))  # margin alone permits upward drift
        self.assertTrue(Builder._construction_feet_allowed(head,Vec3i(3,112,3),project))

    def test_legacy_grass_alias_preserves_geometry_and_invalid_alias_fails(self):
        from blockmind.reference_builds import enderman_project
        modern=enderman_project(Vec3i(0,64,0)); legacy=enderman_project(Vec3i(0,64,0),'minecraft:grass')
        self.assertEqual([op.position for op in modern.plan.operations],[op.position for op in legacy.plan.operations])
        self.assertEqual(legacy.plan.materials['minecraft:grass'],12)
        with self.assertRaises(ValueError): enderman_project(Vec3i(0,64,0),'minecraft:fern')

    def test_whole_reconstruction_has_hollow_body_and_explicit_support_dependencies(self):
        from blockmind.reference_builds import enderman_project
        project=enderman_project(Vec3i(0,64,0))
        repeat=enderman_project(Vec3i(0,64,0))
        self.assertEqual(len(project.plan.operations),1243)
        self.assertEqual([op.id for op in project.plan.operations],[op.id for op in repeat.plan.operations])
        self.assertEqual(len({op.position for op in project.plan.operations}),1243)
        self.assertFalse(project.design.parameters['partial_reference'])
        self.assertTrue(project.design.parameters['approximation_authorized'])
        self.assertEqual(project.design.parameters['dimensions'],{'width':14,'depth':8,'height':58})
        positions={op.position for op in project.plan.operations}
        self.assertNotIn(Vec3i(3,95,5),positions)  # hollow torso
        self.assertNotIn(Vec3i(3,107,3),positions)  # hollow head
        ordered=ConstructionScheduler().optimize(project.plan)
        seen={}
        for op in ordered:
            for dependency in op.depends_on:
                self.assertIn(dependency,seen)
                self.assertEqual(op.position.distance_squared(seen[dependency]),1)
            seen[op.id]=op.position
        self.assertEqual(sum(op.verify_only for op in ordered),8)
        self.assertEqual(project.plan.materials['minecraft:oak_log'],15)
        self.assertEqual(project.plan.materials['minecraft:oak_leaves'],144)
        arms=[op.position for op in ordered if op.component_id.startswith('statue.arm_')]
        self.assertEqual(len(arms),272)
        self.assertEqual((min(p.y for p in arms),max(p.y for p in arms)),(70,103))

    def test_partial_legs_are_deterministic_source_sized_not_whole_acceptance(self):
        first=ENDERMAN_LEGS.legs_probe(Vec3i(0,64,0)); second=ENDERMAN_LEGS.legs_probe(Vec3i(0,64,0))
        self.assertEqual(len(first.plan.operations),224)
        self.assertEqual([op.id for op in first.plan.operations],[op.id for op in second.plan.operations])
        self.assertEqual(len({op.position for op in first.plan.operations}),224)
        self.assertTrue(first.design.parameters["partial_reference"])
        self.assertEqual(first.design.parameters["dimensions"],{"width":6,"depth":2,"height":28})
        ordered=ConstructionScheduler().optimize(first.plan)
        for previous,current in zip(ordered,ordered[1:]):
            if previous.component_id==current.component_id:
                self.assertLessEqual(previous.position.y,current.position.y)

    def test_mud_and_leaf_states_never_enter_full_cube_bursts(self):
        from blockmind.models import BuildOperation,OperationKind
        for block,properties in (("minecraft:mud",{}),("minecraft:oak_leaves",{"persistent":"true"})):
            op=BuildOperation(OperationKind.PLACE,Vec3i(0,64,0),block,"head",properties=properties)
            self.assertNotEqual(classify(op),OperationClass.SIMPLE)
