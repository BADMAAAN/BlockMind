package dev.blockmind.minecraft.navigation;

import net.minecraft.client.MinecraftClient;
import net.minecraft.util.math.BlockPos;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

/**
 * Optional LGPL Baritone integration through its public API, loaded reflectively.
 * BlockMind does not bundle Baritone; users install the official API Fabric jar separately.
 */
public final class BaritoneNavigationProvider implements NavigationProvider {
    private final MinecraftClient client;
    private Object baritone;
    private Object goalProcess;
    private Object pathingBehavior;
    private String error;
    private boolean started;
    private boolean cancelled;
    private BlockPos target;

    public BaritoneNavigationProvider(MinecraftClient client) {
        this.client = client;
        discover();
    }

    private void discover() {
        try {
            Class<?> api = Class.forName("baritone.api.BaritoneAPI");
            Object provider = api.getMethod("getProvider").invoke(null);
            baritone = Class.forName("baritone.api.IBaritoneProvider")
                    .getMethod("getPrimaryBaritone").invoke(provider);
            goalProcess = Class.forName("baritone.api.IBaritone")
                    .getMethod("getCustomGoalProcess").invoke(baritone);
            pathingBehavior = Class.forName("baritone.api.IBaritone")
                    .getMethod("getPathingBehavior").invoke(baritone);
        } catch (ReflectiveOperationException exception) {
            error = "Baritone API Fabric mod not installed or incompatible: " + exception.getClass().getSimpleName();
        }
    }

    @Override
    public StartResult start(BlockPos target, boolean avoidHazards) {
        if (!available()) return new StartResult(false, target, error, false);
        try {
            Class<?> goalClass = Class.forName("baritone.api.pathing.goals.GoalBlock");
            Constructor<?> constructor = goalClass.getConstructor(int.class, int.class, int.class);
            Object goal = constructor.newInstance(target.getX(), target.getY(), target.getZ());
            Method setter = findSingleArgumentMethod(Class.forName("baritone.api.process.ICustomGoalProcess"), "setGoalAndPath");
            setter.invoke(goalProcess, goal);
            started = true;
            cancelled = false;
            this.target = target;
            return new StartResult(true, target, "", false);
        } catch (ReflectiveOperationException exception) {
            error = "Baritone invocation failed: " + exception.getClass().getSimpleName();
            return new StartResult(false, target, error, false);
        }
    }

    private static Method findSingleArgumentMethod(Class<?> type, String name) throws NoSuchMethodException {
        for (Method method : type.getMethods()) {
            if (method.getName().equals(name) && method.getParameterCount() == 1) return method;
        }
        throw new NoSuchMethodException(name);
    }

    @Override
    public NavigationStatus poll() {
        BlockPos position = client.player == null ? BlockPos.ORIGIN : client.player.getBlockPos();
        if (cancelled) return new NavigationStatus(NavigationStatus.State.CANCELLED, position, "cancelled");
        if (!started) return new NavigationStatus(NavigationStatus.State.IDLE, position, error == null ? "" : error);
        try {
            boolean pathing = (boolean) Class.forName("baritone.api.behavior.IPathingBehavior")
                    .getMethod("isPathing").invoke(pathingBehavior);
            boolean active = (boolean) Class.forName("baritone.api.process.IBaritoneProcess")
                    .getMethod("isActive").invoke(goalProcess);
            if (pathing || active) return new NavigationStatus(NavigationStatus.State.RUNNING, position, "");
            started = false;
            if (target != null && position.equals(target)) {
                return new NavigationStatus(NavigationStatus.State.SUCCEEDED, position, "");
            }
            return new NavigationStatus(NavigationStatus.State.FAILED, position, "Baritone stopped before reaching target");
        } catch (ReflectiveOperationException exception) {
            return new NavigationStatus(NavigationStatus.State.FAILED, position, exception.getClass().getSimpleName());
        }
    }

    @Override
    public void cancel() {
        cancelled = true;
        started = false;
        if (baritone == null) return;
        try {
            Class.forName("baritone.api.behavior.IPathingBehavior")
                    .getMethod("cancelEverything").invoke(pathingBehavior);
        } catch (ReflectiveOperationException ignored) {
            // A disconnected or changing upstream API is reported through the next status poll.
        }
    }

    @Override
    public boolean available() {
        return baritone != null;
    }
}
