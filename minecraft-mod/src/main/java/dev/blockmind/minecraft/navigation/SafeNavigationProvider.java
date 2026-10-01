package dev.blockmind.minecraft.navigation;

import dev.blockmind.minecraft.GameAccess;
import dev.blockmind.minecraft.GameAccess.Pos;

/** Complements backend pathfinding with target and immediate fall/hazard guards. */
public final class SafeNavigationProvider implements NavigationProvider {
    private final GameAccess game;
    private final NavigationProvider delegate;
    public SafeNavigationProvider(GameAccess game, NavigationProvider delegate) { this.game = game; this.delegate = delegate; }
    @Override public StartResult start(Pos target, boolean avoidHazards) {
        String reason = game.unsafe(target);
        if (!reason.isEmpty()) return new StartResult(false, target, reason, false);
        return delegate.start(target, true);
    }
    @Override public NavigationStatus poll() {
        String reason = game.immediateDanger();
        if (!reason.isEmpty()) {
            delegate.cancel();
            return new NavigationStatus(NavigationStatus.State.FAILED, game.playerPosition(), "movement aborted: " + reason);
        }
        return delegate.poll();
    }
    @Override public void cancel() { delegate.cancel(); }
    @Override public boolean available() { return delegate.available(); }
    @Override public void configureLocal(boolean enabled) { delegate.configureLocal(enabled); }
    @Override public com.google.gson.JsonObject performance() { return delegate.performance(); }
}
