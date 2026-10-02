package dev.blockmind.minecraft;

import dev.blockmind.minecraft.GameAccess.Pos;
import dev.blockmind.minecraft.navigation.FlightRoutePlanner;
import org.junit.jupiter.api.Test;
import java.util.function.Predicate;
import static org.junit.jupiter.api.Assertions.*;

class FlightRouteTest {
    final FlightRoutePlanner.Area area = new FlightRoutePlanner.Area(new Pos(-3,64,-3),new Pos(8,72,3));
    @Test void loadedClearRouteIsOneGoalWithoutChangingTarget() {
        var target = new Pos(6,68,0);
        assertEquals(java.util.List.of(target),FlightRoutePlanner.route(new Pos(0,64,0),target,area,p -> true,4096));
    }
    @Test void obstacleIsDetouredInsideApprovalAndEverySegmentIsClear() {
        var from=new Pos(0,64,0); var to=new Pos(6,64,0);
        Predicate<Pos> safe=p -> p.x()!=3 || p.y()>67 || Math.abs(p.z())>1;
        var route=FlightRoutePlanner.route(from,to,area,safe,4096);
        assertFalse(route.isEmpty()); assertEquals(to,route.get(route.size()-1));
        assertEquals(route,FlightRoutePlanner.route(from,to,area,safe,4096));
        var cursor=from;
        for (var point:route) {
            assertTrue(area.contains(point)); assertTrue(FlightRoutePlanner.clear(cursor,point,area,safe)); cursor=point;
        }
    }
    @Test void unloadedBarrierUnapprovedTargetAndSearchBudgetFailClosed() {
        var from=new Pos(0,64,0); var to=new Pos(6,64,0);
        assertTrue(FlightRoutePlanner.route(from,to,area,p -> p.x()!=3,4096).isEmpty());
        assertTrue(FlightRoutePlanner.route(from,new Pos(10,64,0),area,p -> true,4096).isEmpty());
        assertTrue(FlightRoutePlanner.route(from,to,area,p -> p.x()!=3 || p.y()>67,1).isEmpty());
    }
    @Test void diagonalCannotClipCornerWithBodyEvenWhenCentreIsClear() {
        var from=new Pos(0,64,0); var to=new Pos(2,64,2);
        assertFalse(FlightRoutePlanner.clear(from,to,area,p -> !(p.x()==1 && p.z()==0)));
    }
}
