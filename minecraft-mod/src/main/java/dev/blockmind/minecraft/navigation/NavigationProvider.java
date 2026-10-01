package dev.blockmind.minecraft.navigation;

import dev.blockmind.minecraft.GameAccess.Pos;

/** Core goals never expose Minecraft mappings or Baritone types. */
public interface NavigationProvider {
    StartResult start(Pos target, boolean avoidHazards);
    NavigationStatus poll();
    void cancel();
    boolean available();
    default void configureLocal(boolean enabled) { }
    default com.google.gson.JsonObject performance() { return new com.google.gson.JsonObject(); }
    record StartResult(boolean accepted, Pos target, String reason, boolean usedAlternative) {}
    record NavigationStatus(State state, Pos position, String reason) {
        public enum State { IDLE, RUNNING, SUCCEEDED, FAILED, CANCELLED }
    }
}
