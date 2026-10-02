package dev.blockmind.minecraft.navigation;

import dev.blockmind.minecraft.GameAccess;
import dev.blockmind.minecraft.GameAccess.Pos;

/** Complements backend pathfinding with target and immediate fall/hazard guards. */
public final class SafeNavigationProvider implements NavigationProvider {
    private final GameAccess game;
    private final NavigationProvider delegate;
    private double[] lastProgress;
    private int stationaryTicks;
    private boolean flight;
    public SafeNavigationProvider(GameAccess game, NavigationProvider delegate) { this.game = game; this.delegate = delegate; }
    @Override public StartResult start(Pos target, boolean avoidHazards) {
        lastProgress = game.precisePosition(); stationaryTicks = 0;
        String reason = flight ? game.unsafeFlight(target) : game.unsafe(target);
        if (!reason.isEmpty()) return new StartResult(false, target, reason, false);
        return delegate.start(target, true);
    }
    @Override public NavigationStatus poll() {
        // Vanilla jump-key edges can toggle Creative flying during vertical
        // braking. Renew the owned opt-in ability only while navigation polls;
        // paused/stopped work never polls and never initiates another takeoff.
        if (flight) game.tickFlight();
        String reason = game.immediateDanger();
        if (!reason.isEmpty()) {
            delegate.cancel();
            return new NavigationStatus(NavigationStatus.State.FAILED, game.playerPosition(), "movement aborted: " + reason);
        }
        var status = delegate.poll();
        double[] position = game.precisePosition();
        if (status.state() == NavigationStatus.State.RUNNING && lastProgress != null) {
            double distance = 0;
            for (int i=0; i<3; i++) distance += Math.pow(position[i]-lastProgress[i], 2);
            if (distance > .0625) { lastProgress = position; stationaryTicks = 0; }
            else if (++stationaryTicks >= 200) {
                delegate.cancel();
                return new NavigationStatus(NavigationStatus.State.FAILED, game.playerPosition(), "stale route: no movement for 200 client ticks");
            }
        }
        return status;
    }
    @Override public void cancel() { delegate.cancel(); }
    @Override public boolean available() { return delegate.available(); }
    @Override public void configureLocal(boolean enabled) { delegate.configureLocal(enabled); }
    @Override public boolean configureFlight(boolean enabled) {
        boolean accepted = delegate.configureFlight(enabled);
        flight = enabled && accepted;
        return accepted;
    }
    @Override public com.google.gson.JsonObject performance() { return delegate.performance(); }
    @Override public void approveFlightRegion(Pos minimum, Pos maximum) { delegate.approveFlightRegion(minimum,maximum); }
}
