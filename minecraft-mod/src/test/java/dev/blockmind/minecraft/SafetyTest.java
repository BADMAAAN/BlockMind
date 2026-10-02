package dev.blockmind.minecraft;

import dev.blockmind.minecraft.GameAccess.Pos;
import dev.blockmind.minecraft.navigation.NavigationProvider;
import dev.blockmind.minecraft.navigation.SafeNavigationProvider;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class SafetyTest {
    @Test void placementPreservesFlightClearanceWithNegativeHeightAndNeighbourEdge() {
        double[] player={105.9,-21.65,103.5};
        assertTrue(MovementSafety.blocksFlightClearance(new Pos(105,-20,103),player));
        assertTrue(MovementSafety.blocksFlightClearance(new Pos(106,-20,103),player));
        assertFalse(MovementSafety.blocksFlightClearance(new Pos(107,-20,103),player));
        assertFalse(MovementSafety.blocksFlightClearance(new Pos(105,-19,103),player));
        assertFalse(MovementSafety.blocksFlightClearance(new Pos(105,-23,103),player));
    }
    @Test void stationaryRouteIsCancelledWithBoundedRetriesAtCoreBoundary() {
        var backend = new ExecutorControlTest.Navigation();
        var safe = new SafeNavigationProvider(new ExecutorControlTest.Game(), backend);
        safe.start(new Pos(10, 64, 0), true);
        for (int i=0; i<199; i++) assertEquals(NavigationProvider.NavigationStatus.State.RUNNING, safe.poll().state());
        assertEquals(NavigationProvider.NavigationStatus.State.FAILED, safe.poll().state());
        assertTrue(backend.cancelled);
    }
    @Test void groundedGravityDoesNotProjectIntoFloorButActualFallDoes() {
        assertEquals(new Pos(2, -60, 0), MovementSafety.projectedFeet(.5, -60, .5, .5, -.0784, 0, true));
        assertEquals(new Pos(2, -61, 0), MovementSafety.projectedFeet(.5, -60, .5, .5, -.0784, 0, false));
        assertEquals(new Pos(0, -59, 0), MovementSafety.projectedFeet(.5, -60, .5, 0, .42, 0, true));
    }
    @Test void descendingProjectionCannotTunnelThroughKnownGround() {
        Pos predicted = new Pos(0,-62,0);
        assertEquals(new Pos(0,-60,0), MovementSafety.clipDescendingToSupport(predicted,-59.2,p -> p.y()==-61));
        assertEquals(predicted, MovementSafety.clipDescendingToSupport(predicted,-59.2,p -> false));
        assertEquals(new Pos(0,-57,0), MovementSafety.clipDescendingToSupport(new Pos(0,-59,0),-56.2,p -> p.y()==-58));
    }
    @Test void hazardousTargetIsNotSubstitutedOrSentToBackend() {
        var backend = new ExecutorControlTest.Navigation();
        var game = new ExecutorControlTest.Game() { public String unsafe(Pos p) { return "lava"; } };
        var safe = new SafeNavigationProvider(game, backend);
        var result = safe.start(new Pos(1, 64, 0), true);
        assertFalse(result.accepted()); assertEquals("lava", result.reason()); assertFalse(result.usedAlternative());
    }
    @Test void ImmediateFallRiskCancelsBackendWhileMoving() {
        var backend = new ExecutorControlTest.Navigation();
        var game = new ExecutorControlTest.Game() { public String immediateDanger() { return "unsafe drop"; } };
        var safe = new SafeNavigationProvider(game, backend);
        assertTrue(safe.start(new Pos(1, 64, 0), true).accepted());
        assertEquals(NavigationProvider.NavigationStatus.State.FAILED, safe.poll().state());
        assertTrue(backend.cancelled);
    }
}
