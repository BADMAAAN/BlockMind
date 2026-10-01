package dev.blockmind.minecraft;

/** Mapping-independent projection; grounded gravity must not project the player into the floor. */
final class MovementSafety {
    static GameAccess.Pos projectedFeet(double x, double y, double z, double vx, double vy, double vz, boolean grounded) {
        double projectedY = grounded && vy <= 0 ? y : y + vy * 3;
        return new GameAccess.Pos((int) Math.floor(x + vx * 3), (int) Math.floor(projectedY), (int) Math.floor(z + vz * 3));
    }
}
