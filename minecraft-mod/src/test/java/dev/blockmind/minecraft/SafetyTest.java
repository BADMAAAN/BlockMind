package dev.blockmind.minecraft;

import dev.blockmind.minecraft.GameAccess.Pos;
import dev.blockmind.minecraft.navigation.NavigationProvider;
import dev.blockmind.minecraft.navigation.SafeNavigationProvider;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class SafetyTest {
    @Test void groundedGravityDoesNotProjectIntoFloorButActualFallDoes() {
        assertEquals(new Pos(2, -60, 0), MovementSafety.projectedFeet(.5, -60, .5, .5, -.0784, 0, true));
        assertEquals(new Pos(2, -61, 0), MovementSafety.projectedFeet(.5, -60, .5, .5, -.0784, 0, false));
        assertEquals(new Pos(0, -59, 0), MovementSafety.projectedFeet(.5, -60, .5, 0, .42, 0, true));
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
