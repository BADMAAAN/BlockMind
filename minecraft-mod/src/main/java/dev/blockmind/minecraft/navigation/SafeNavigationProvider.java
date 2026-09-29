package dev.blockmind.minecraft.navigation;

import net.minecraft.block.BlockState;
import net.minecraft.block.Blocks;
import net.minecraft.client.MinecraftClient;
import net.minecraft.util.math.BlockPos;

/** Rejects obvious lethal targets before delegating to the selected pathfinder. */
public final class SafeNavigationProvider implements NavigationProvider {
    private final MinecraftClient client;
    private final NavigationProvider delegate;

    public SafeNavigationProvider(MinecraftClient client, NavigationProvider delegate) {
        this.client = client;
        this.delegate = delegate;
    }

    @Override
    public StartResult start(BlockPos target, boolean avoidHazards) {
        if (client.world == null || !avoidHazards) return delegate.start(target, avoidHazards);
        if (!hazardous(target)) return delegate.start(target, true);
        for (BlockPos candidate : new BlockPos[]{target.east(), target.west(), target.north(), target.south(),
                target.east(2), target.west(2), target.north(2), target.south(2)}) {
            if (!hazardous(candidate)) {
                StartResult result = delegate.start(candidate, true);
                return new StartResult(result.accepted(), result.target(),
                        result.accepted() ? "unsafe direct target rejected" : result.reason(), true);
            }
        }
        return new StartResult(false, target, "target and nearby alternatives are hazardous", false);
    }

    private boolean hazardous(BlockPos position) {
        BlockState feet = client.world.getBlockState(position);
        BlockState below = client.world.getBlockState(position.down());
        boolean lavaOrFire = feet.isOf(Blocks.LAVA) || feet.isOf(Blocks.FIRE) || below.isOf(Blocks.LAVA)
                || below.isOf(Blocks.FIRE) || below.isOf(Blocks.MAGMA_BLOCK);
        boolean voidRisk = position.getY() <= client.world.getBottomY() + 2;
        int fall = 0;
        BlockPos cursor = position.down();
        while (fall <= 4 && client.world.getBlockState(cursor).isAir()) {
            fall++;
            cursor = cursor.down();
        }
        return lavaOrFire || voidRisk || fall > 3;
    }

    @Override public NavigationStatus poll() { return delegate.poll(); }
    @Override public void cancel() { delegate.cancel(); }
    @Override public boolean available() { return delegate.available(); }
}
