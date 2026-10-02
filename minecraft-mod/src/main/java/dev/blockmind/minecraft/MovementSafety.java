package dev.blockmind.minecraft;

/** Mapping-independent projection; grounded gravity must not project the player into the floor. */
final class MovementSafety {
    static boolean blocksFlightClearance(GameAccess.Pos target, double[] position) {
        int feetY=(int)Math.floor(position[1]);
        return target.y()>=feetY && target.y()<=feetY+2
            && target.x()<position[0]+.31 && target.x()+1>position[0]-.31
            && target.z()<position[2]+.31 && target.z()+1>position[2]-.31;
    }
    static GameAccess.Pos projectedFeet(double x, double y, double z, double vx, double vy, double vz, boolean grounded) {
        double projectedY = grounded && vy <= 0 ? y : y + vy * 3;
        return new GameAccess.Pos((int) Math.floor(x + vx * 3), (int) Math.floor(projectedY), (int) Math.floor(z + vz * 3));
    }
    static GameAccess.Pos clipDescendingToSupport(GameAccess.Pos projected, double currentY,
            java.util.function.Predicate<GameAccess.Pos> collision) {
        // Three-tick velocity extrapolation must not tunnel through known ground.
        // Actual drop/hazard checks still run before this bounded projection clip.
        int start = (int)Math.floor(currentY)-1;
        for (int y=start; y>=projected.y()-1 && start-y<16; y--) {
            if (collision.test(new GameAccess.Pos(projected.x(), y, projected.z())))
                return new GameAccess.Pos(projected.x(), y+1, projected.z());
        }
        return projected;
    }
}
