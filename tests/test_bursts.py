import unittest
from blockmind.bursts import AdaptiveBurstController, BuildBurst
from blockmind.models import Bounds, BuildOperation, OperationKind, Vec3i


class BurstTests(unittest.TestCase):
    def test_explicit_support_must_be_verified_outside_the_same_burst(self):
        area=Bounds(Vec3i(0,64,0),Vec3i(2,65,0))
        child=BuildOperation(OperationKind.PLACE,Vec3i(0,65,0),'minecraft:stone','leg',id='child',depends_on=['support'])
        with self.assertRaises(ValueError): BuildBurst((child,),Vec3i(-1,65,0),'leg',area)
        BuildBurst((child,),Vec3i(-1,65,0),'leg',area,frozenset({'support'}))
        support=BuildOperation(OperationKind.PLACE,Vec3i(0,64,0),'minecraft:stone','leg',id='support')
        with self.assertRaises(ValueError):
            BuildBurst((support,child),Vec3i(-1,65,0),'leg',area,frozenset({'support'}))

    def test_bounded_homogeneous_approved_local_run(self):
        area = Bounds(Vec3i(0,0,0),Vec3i(7,1,0))
        ops = tuple(BuildOperation(OperationKind.PLACE,Vec3i(x,0,0),"minecraft:stone","wall") for x in range(8))
        burst = BuildBurst(ops,Vec3i(0,1,-1),"wall",area)
        self.assertEqual(len(burst.operations),8)
        for invalid in ((), ops*5, (ops[0],ops[0])):
            with self.assertRaises(ValueError): BuildBurst(invalid,burst.feet,"wall",area)
        for changes in ({"block":"minecraft:glass"},{"component_id":"other"},
                        {"position":Vec3i(20,0,0)},{"properties":{"axis":"x"}},
                        {"temporary":True},{"depends_on":[ops[0].id]}):
            other = BuildOperation(OperationKind.PLACE,Vec3i(1,0,0),"minecraft:stone","wall",**{
                k:v for k,v in changes.items() if k not in ("block","component_id","position")})
            for key,value in changes.items(): setattr(other,key,value)
            with self.assertRaises(ValueError): BuildBurst((ops[0],other),burst.feet,"wall",area)

    def test_growth_requires_full_verified_runs_and_mismatch_reduces(self):
        control = AdaptiveBurstController(16)
        for _ in range(5): control.feedback(attempted=2,issued=2,verified=2)
        self.assertEqual(control.size,8)
        for _ in range(2): control.feedback(attempted=8,issued=8,verified=8)
        self.assertEqual(control.size,10)
        control.feedback(attempted=10,issued=10,verified=8)
        self.assertEqual(control.size,5)
        self.assertEqual(control.snapshot()["mismatches"],2)
        self.assertGreater(control.snapshot()["mismatch_rate"],0)
        for _ in range(50):
            control.feedback(attempted=control.size,issued=control.size,verified=control.size)
        self.assertEqual(control.size,16)

    def test_issued_ack_is_not_verification_and_repair_cost_reduces_size(self):
        control = AdaptiveBurstController(32)
        control.feedback(attempted=8,issued=8,verified=0)
        self.assertEqual(control.size,4)
        control.feedback(attempted=4,issued=4,verified=4,repairs=2)
        self.assertEqual(control.size,2)
        self.assertEqual(control.snapshot()["repair_operations"],2)
        with self.assertRaises(ValueError): control.feedback(attempted=2,issued=2,verified=3)
