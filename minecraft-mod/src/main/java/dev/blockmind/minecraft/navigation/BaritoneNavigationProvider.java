package dev.blockmind.minecraft.navigation;

import dev.blockmind.minecraft.GameAccess;
import dev.blockmind.minecraft.GameAccess.Pos;
import java.util.LinkedHashMap;
import java.util.Map;

/** Uses only public baritone.api; no Baritone binary or sources are bundled. */
public final class BaritoneNavigationProvider implements NavigationProvider {
    private final GameAccess game;
    private Object goalProcess;
    private Object pathing;
    private String error = "Baritone public API unavailable";
    private boolean running;
    private Pos target;
    private int grace;
    private long activeStart, activeNanos, startNanos;
    private int goals;
    @Override public com.google.gson.JsonObject performance() {
        var value = new com.google.gson.JsonObject(); value.addProperty("baritoneGoals", goals);
        value.addProperty("baritoneStartSeconds", startNanos / 1e9);
        value.addProperty("baritoneActiveSeconds", (activeNanos + (running ? System.nanoTime()-activeStart : 0)) / 1e9); return value;
    }
    private final Map<Object, Object> previousSettings = new LinkedHashMap<>();

    public BaritoneNavigationProvider(GameAccess game) { this.game = game; }

    private boolean discover() {
        if (goalProcess != null && pathing != null) return true;
        try {
            Class<?> api = Class.forName("baritone.api.BaritoneAPI");
            Object provider = api.getMethod("getProvider").invoke(null);
            Object baritone = Class.forName("baritone.api.IBaritoneProvider").getMethod("getPrimaryBaritone").invoke(provider);
            Class<?> type = Class.forName("baritone.api.IBaritone");
            goalProcess = type.getMethod("getCustomGoalProcess").invoke(baritone);
            pathing = type.getMethod("getPathingBehavior").invoke(baritone);
            return true;
        } catch (ReflectiveOperationException | LinkageError exc) {
            error = "Baritone API unavailable: " + exc.getClass().getSimpleName();
            goalProcess = null; pathing = null;
            return false;
        }
    }

    @Override public boolean available() { return discover(); }

    @Override public StartResult start(Pos target, boolean avoidHazards) {
        if (!discover()) return new StartResult(false, target, error, false);
        cancel();
        long start=System.nanoTime();
        try {
            // Avoid collateral pathfinding edits and dangerous shortcut policies.
            Object settings = Class.forName("baritone.api.BaritoneAPI").getMethod("getSettings").invoke(null);
            set(settings, "allowBreak", false); set(settings, "allowPlace", false);
            set(settings, "allowParkour", false); set(settings, "allowSprint", false);
            set(settings, "maxFallHeightNoWater", 3);
            Object goal = Class.forName("baritone.api.pathing.goals.GoalBlock")
                .getConstructor(int.class, int.class, int.class).newInstance(target.x(), target.y(), target.z());
            Class.forName("baritone.api.process.ICustomGoalProcess")
                .getMethod("setGoalAndPath", Class.forName("baritone.api.pathing.goals.Goal")).invoke(goalProcess, goal);
            this.target = target; running = true; grace = 10;
            goals++; activeStart=System.nanoTime(); startNanos+=activeStart-start;
            return new StartResult(true, target, "", false);
        } catch (ReflectiveOperationException | LinkageError exc) {
            cancel();
            return new StartResult(false, target, "Baritone invocation failed: " + exc.getClass().getSimpleName(), false);
        }
    }

    private void set(Object settings, String key, Object value) throws ReflectiveOperationException {
        Object setting = settings.getClass().getField(key).get(settings);
        previousSettings.putIfAbsent(setting, setting.getClass().getField("value").get(setting));
        setting.getClass().getField("value").set(setting, value);
    }

    @Override public NavigationStatus poll() {
        Pos position = game.playerPosition();
        if (!running) return new NavigationStatus(NavigationStatus.State.CANCELLED, position, "cancelled");
        if (position.equals(target)) { cancel(); return new NavigationStatus(NavigationStatus.State.SUCCEEDED, position, "arrived"); }
        try {
            boolean active = (boolean) Class.forName("baritone.api.process.IBaritoneProcess").getMethod("isActive").invoke(goalProcess);
            boolean moving = (boolean) Class.forName("baritone.api.behavior.IPathingBehavior").getMethod("isPathing").invoke(pathing);
            if (active || moving || grace-- > 0) return new NavigationStatus(NavigationStatus.State.RUNNING, position, "");
            cancel();
            return new NavigationStatus(NavigationStatus.State.FAILED, position, "Baritone stopped before reaching target");
        } catch (ReflectiveOperationException exc) {
            cancel();
            return new NavigationStatus(NavigationStatus.State.FAILED, position, exc.getClass().getSimpleName());
        }
    }

    @Override public void cancel() {
        if (running) activeNanos+=System.nanoTime()-activeStart;
        running = false;
        if (pathing != null) {
            try { Class.forName("baritone.api.behavior.IPathingBehavior").getMethod("cancelEverything").invoke(pathing); }
            catch (ReflectiveOperationException ignored) { }
        }
        for (var entry : previousSettings.entrySet()) {
            try { entry.getKey().getClass().getField("value").set(entry.getKey(), entry.getValue()); }
            catch (ReflectiveOperationException ignored) { }
        }
        previousSettings.clear();
        game.releaseMovement();
    }
}
