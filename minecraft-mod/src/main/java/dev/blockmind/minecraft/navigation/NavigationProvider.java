package dev.blockmind.minecraft.navigation;

import net.minecraft.util.math.BlockPos;

/** Stable adapter boundary: Core goals do not expose Baritone implementation types. */
public interface NavigationProvider {
    StartResult start(BlockPos target, boolean avoidHazards);
    NavigationStatus poll();
    void cancel();
    boolean available();

    record StartResult(boolean accepted, BlockPos target, String reason, boolean usedAlternative) {}
    record NavigationStatus(State state, BlockPos position, String reason) {
        public enum State { IDLE, RUNNING, SUCCEEDED, FAILED, CANCELLED }
    }
}
