package dev.blockmind.minecraft;

import dev.blockmind.minecraft.navigation.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class LocalNavigationTest {
    @Test void backendArrivalIsCenteredBeforePlacementCanProceed() {
        var game = new ExecutorControlTest.Game() {
            int calls;
            public String localMove(GameAccess.Pos target) {
                return switch (++calls) { case 1 -> "unsupported"; case 2 -> "moving"; default -> "arrived"; };
            }
        };
        var backend = new ExecutorControlTest.Navigation() {
            public NavigationStatus poll() { return new NavigationStatus(NavigationStatus.State.SUCCEEDED,
                new GameAccess.Pos(1,64,0), "arrived at edge"); }
        };
        var navigation = new LocalNavigationProvider(game, backend);
        assertTrue(navigation.start(new GameAccess.Pos(1,64,0), true).accepted());
        assertEquals(NavigationProvider.NavigationStatus.State.RUNNING, navigation.poll().state());
        assertEquals(NavigationProvider.NavigationStatus.State.SUCCEEDED, navigation.poll().state());
    }
}
