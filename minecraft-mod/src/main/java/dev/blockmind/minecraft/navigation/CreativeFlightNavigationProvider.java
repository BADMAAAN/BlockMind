package dev.blockmind.minecraft.navigation;

import dev.blockmind.minecraft.GameAccess;
import dev.blockmind.minecraft.GameAccess.Pos;

/** Opt-in Creative ability + normal movement keys, never teleportation. */
public final class CreativeFlightNavigationProvider implements NavigationProvider {
    private final GameAccess game;
    private final NavigationProvider ground;
    private boolean enabled, active;
    private Pos target;
    private FlightRoutePlanner.Area area;
    private java.util.List<Pos> waypoints = java.util.List.of();
    private int waypoint;
    private int ticks, goals;
    private long activeNanos, started;

    public CreativeFlightNavigationProvider(GameAccess game, NavigationProvider ground) {
        this.game = game; this.ground = ground;
    }
    @Override public boolean configureFlight(boolean enabled) {
        cancel();
        boolean accepted = game.configureFlight(enabled);
        this.enabled = enabled && accepted;
        return accepted;
    }
    @Override public boolean available() { return ground.available() || game.ready() && game.creative(); }
    @Override public void approveFlightRegion(Pos minimum, Pos maximum) { area = new FlightRoutePlanner.Area(minimum,maximum); }
    @Override public void configureLocal(boolean enabled) { ground.configureLocal(enabled); }
    @Override public StartResult start(Pos target, boolean avoidHazards) {
        if (!enabled) return ground.start(target, avoidHazards);
        if (!game.creative()) return new StartResult(false,target,"Creative flight ability unavailable",false);
        String unsafe = game.unsafeFlight(target);
        if (!unsafe.isEmpty()) return new StartResult(false,target,unsafe,false);
        waypoints = FlightRoutePlanner.route(game.playerPosition(),target,area,p -> game.unsafeFlight(p).isEmpty(),4096);
        if (waypoints.isEmpty()) return new StartResult(false,target,"no loaded safe flight route in approved region",false);
        waypoint = 0;
        this.target = target; ticks = 0; active = true; goals++; started = System.nanoTime();
        return new StartResult(true,target,"Creative key steering",false);
    }
    @Override public NavigationStatus poll() {
        if (!enabled) return ground.poll();
        if (!active) return new NavigationStatus(NavigationStatus.State.IDLE,game.playerPosition(),"");
        Pos next = waypoints.get(waypoint);
        if (!FlightRoutePlanner.clear(game.playerPosition(),next,area,p -> game.unsafeFlight(p).isEmpty())) {
            finish(); return new NavigationStatus(NavigationStatus.State.FAILED,game.playerPosition(),"flight route blocked after planning");
        }
        String state = game.flightMove(next);
        if (state.equals("arrived")) {
            if (++waypoint < waypoints.size()) return new NavigationStatus(NavigationStatus.State.RUNNING,game.playerPosition(),"");
            finish();
            return new NavigationStatus(NavigationStatus.State.SUCCEEDED,game.playerPosition(),"Creative arrived");
        }
        if (!state.equals("moving") || ++ticks > 1200) {
            finish();
            return new NavigationStatus(NavigationStatus.State.FAILED,game.playerPosition(),state.equals("moving") ? "flight deadline" : state);
        }
        return new NavigationStatus(NavigationStatus.State.RUNNING,game.playerPosition(),"");
    }
    private void finish() {
        if (active) activeNanos += System.nanoTime()-started;
        active = false; waypoints = java.util.List.of(); game.releaseMovement();
    }
    @Override public void cancel() { finish(); ground.cancel(); }
    @Override public com.google.gson.JsonObject performance() {
        var value = ground.performance(); value.addProperty("flightGoals",goals);
        value.addProperty("flightActiveSeconds",(activeNanos+(active ? System.nanoTime()-started : 0))/1e9);
        return value;
    }
}
