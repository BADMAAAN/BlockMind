package dev.blockmind.minecraft;

import com.google.gson.*;
import net.minecraft.block.*;
import net.minecraft.client.MinecraftClient;
import net.minecraft.item.*;
import net.minecraft.registry.Registries;
import net.minecraft.state.property.Property;
import net.minecraft.util.Hand;
import net.minecraft.util.hit.*;
import net.minecraft.util.math.*;
import net.minecraft.world.RaycastContext;

/** Yarn API family 1.20..1.21; only small API differences live in ApiCompat. */
final class YarnGameAccess implements GameAccess {
    private final AudioSession audio = new AudioSession(() -> this.client.options.getSoundVolume(net.minecraft.sound.SoundCategory.MASTER), value -> this.client.options.getSoundVolumeOption(net.minecraft.sound.SoundCategory.MASTER).setValue(value));
    private long rotationNanos, selectionNanos;
    private int rotationCount, selectionCount;
    private final java.util.Map<String, Integer> materialSlots = new java.util.LinkedHashMap<>();
    @Override public boolean creative() { return client.player.getAbilities().creativeMode; }
    private boolean flightRequested, flightOwned, previousFlight;
    private Object flightPlayer;
    @Override public boolean flying() { return ready() && client.player.getAbilities().flying; }
    @Override public boolean configureFlight(boolean enabled) {
        if (!enabled) flightRequested = false;
        if (!ready() || client.player != flightPlayer) { flightOwned = false; flightPlayer = null; }
        if (!ready()) return !enabled;
        if (enabled && (!creative() || !client.player.getAbilities().allowFlying)) return false;
        flightRequested = enabled;
        if (enabled) {
            if (!flightOwned) { previousFlight = flying(); flightOwned = true; flightPlayer = client.player; }
            tickFlight();
        } else if (flightOwned && (previousFlight || client.player.isOnGround())) {
            client.player.getAbilities().flying = previousFlight;
            client.player.sendAbilitiesUpdate(); flightOwned = false;
        }
        return true; // Preserve hovering on an airborne cancellation.
    }
    @Override public void tickFlight() {
        if (!flightRequested || !ready() || client.player != flightPlayer || !creative() || flying()) return;
        if (client.player.isOnGround()) client.options.jumpKey.setPressed(true);
        else {
            client.player.getAbilities().flying = true; client.player.sendAbilitiesUpdate();
            client.options.jumpKey.setPressed(false);
        }
    }
    @Override public String flightMove(Pos target) {
        if (!ready() || !creative() || !flightRequested) return "Creative flight unavailable";
        tickFlight();
        if (!flying()) return "moving";
        releaseMovement();
        double dx=target.x()+.5-client.player.getX(), dy=target.y()+.35-client.player.getY(), dz=target.z()+.5-client.player.getZ();
        Vec3d velocity=client.player.getVelocity();
        if (dx*dx+dz*dz < .0225 && Math.abs(dy)<.1 && velocity.lengthSquared()<.0025) return "arrived";
        double steerX=dx-velocity.x*2.5, steerZ=dz-velocity.z*2.5, steerY=dy-velocity.y*2.5;
        if (steerX*steerX+steerZ*steerZ>.0225) {
            look((float)Math.toDegrees(Math.atan2(-steerX,steerZ)),0);
            client.options.forwardKey.setPressed(true);
        }
        client.options.jumpKey.setPressed(steerY>.1); client.options.sneakKey.setPressed(steerY<-.1);
        return "moving";
    }
    @Override public void configureAudio(boolean mute, boolean restore) { audio.begin(mute, restore); }
    @Override public void finishAudio() { audio.finish(); }
    @Override public JsonObject performance() {
        JsonObject value = new JsonObject(); value.addProperty("rotationSeconds", rotationNanos / 1e9);
        value.addProperty("selectionSeconds", selectionNanos / 1e9); value.addProperty("rotations", rotationCount);
        value.addProperty("selections", selectionCount); value.addProperty("masterVolume", client.options.getSoundVolume(net.minecraft.sound.SoundCategory.MASTER)); return value;
    }
    @Override public String localMove(Pos target) {
        Pos here = playerPosition();
        if (!client.player.isOnGround() || here.y() != target.y() || Math.abs(here.x()-target.x()) + Math.abs(here.z()-target.z()) > 2) return "unsupported";
        for (int step = 1; step <= 3; step++) {
            Pos sample = new Pos((int)Math.floor(client.player.getX() + (target.x()+.5-client.player.getX())*step/3),
                target.y(), (int)Math.floor(client.player.getZ() + (target.z()+.5-client.player.getZ())*step/3));
            if (!unsafe(sample).isEmpty()) return "unsupported";
        }
        double dx = target.x()+.5-client.player.getX(), dz = target.z()+.5-client.player.getZ();
        if (dx*dx+dz*dz < .04) { releaseMovement(); return "arrived"; }
        releaseMovement(); look((float)Math.toDegrees(Math.atan2(-dx,dz)), client.player.getPitch());
        client.options.forwardKey.setPressed(true); return "moving";
    }
    private final MinecraftClient client = MinecraftClient.getInstance();
    private BlockPos pos(Pos p) { return new BlockPos(p.x(), p.y(), p.z()); }
    private Pos point(BlockPos p) { return new Pos(p.getX(), p.getY(), p.getZ()); }
    @Override public boolean ready() { return client.player != null && client.world != null && client.interactionManager != null; }
    @Override public Pos playerPosition() { return client.player == null ? new Pos(0, 0, 0) : point(client.player.getBlockPos()); }
    @Override public double[] precisePosition() { return new double[]{client.player.getX(), client.player.getY(), client.player.getZ()}; }
    @Override public String dimension() { return client.world.getRegistryKey().getValue().toString(); }
    private static <T extends Comparable<T>> String property(BlockState state, Property<T> property) { return property.name(state.get(property)); }

    @Override public JsonObject inspect(Pos p) {
        JsonObject value = new JsonObject(); value.add("position", p.json());
        boolean loaded = ready() && client.world.isChunkLoaded(pos(p)); value.addProperty("loaded", loaded);
        if (!loaded) return value;
        BlockState state = client.world.getBlockState(pos(p));
        value.addProperty("block", Registries.BLOCK.getId(state.getBlock()).toString());
        JsonObject properties = new JsonObject();
        for (Property<?> property : state.getProperties()) properties.addProperty(property.getName(), property(state, property));
        value.add("properties", properties); value.addProperty("replaceable", state.isReplaceable());
        value.addProperty("solid", !state.getCollisionShape(client.world, pos(p)).isEmpty());
        return value;
    }

    @Override public JsonObject observe(int radius, long tick) {
        JsonObject root = new JsonObject(); root.addProperty("tick", tick); root.addProperty("radius", radius);
        JsonObject player = new JsonObject(); player.add("position", playerPosition().json());
        player.addProperty("dimension", dimension()); player.addProperty("health", client.player.getHealth());
        player.addProperty("hunger", client.player.getHungerManager().getFoodLevel());
        player.addProperty("creative", client.player.getAbilities().creativeMode); player.addProperty("onGround", client.player.isOnGround());
        player.addProperty("flying", flying());
        JsonArray eye = new JsonArray(); eye.add(client.player.getEyePos().x); eye.add(client.player.getEyePos().y); eye.add(client.player.getEyePos().z); player.add("eye", eye);
        JsonArray velocity = new JsonArray(); Vec3d v = client.player.getVelocity(); velocity.add(v.x); velocity.add(v.y); velocity.add(v.z); player.add("velocity", velocity);
        JsonArray inventory = new JsonArray();
        for (int slot = 0; slot < client.player.getInventory().size(); slot++) {
            ItemStack stack = client.player.getInventory().getStack(slot); if (stack.isEmpty()) continue;
            JsonObject entry = new JsonObject(); entry.addProperty("slot", slot);
            entry.addProperty("item", Registries.ITEM.getId(stack.getItem()).toString()); entry.addProperty("count", stack.getCount()); inventory.add(entry);
        }
        player.add("inventory", inventory); root.add("player", player);
        JsonArray blocks = new JsonArray(); JsonArray hazards = new JsonArray(); BlockPos center = client.player.getBlockPos();
        for (BlockPos p : BlockPos.iterate(center.add(-radius, -radius, -radius), center.add(radius, radius, radius))) {
            BlockState state = client.world.getBlockState(p);
            if (!state.isAir()) blocks.add(inspect(point(p)));
            String hazard = hazard(state);
            if (!hazard.isEmpty()) {
                JsonObject h = new JsonObject(); h.add("position", point(p).json()); h.addProperty("kind", hazard); h.addProperty("severity", 1.0); hazards.add(h);
            }
        }
        root.add("blocks", blocks); root.add("hazards", hazards);
        JsonArray entities = new JsonArray();
        for (var entity : client.world.getOtherEntities(client.player, client.player.getBoundingBox().expand(radius))) {
            JsonObject e = new JsonObject(); e.addProperty("type", Registries.ENTITY_TYPE.getId(entity.getType()).toString());
            e.add("position", point(entity.getBlockPos()).json()); entities.add(e);
        }
        root.add("entities", entities); return root;
    }

    @Override public void look(float yaw, float pitch) {
        if (Math.abs(client.player.getYaw()-yaw)<.01 && Math.abs(client.player.getPitch()-pitch)<.01) return;
        long start=System.nanoTime(); rotationCount++;
        client.player.setYaw(yaw); client.player.setPitch(Math.max(-90, Math.min(90, pitch))); ApiCompat.syncLook(client);
        rotationNanos+=System.nanoTime()-start;
    }
    private void aim(Vec3d target) {
        Vec3d d = target.subtract(client.player.getEyePos());
        look((float) Math.toDegrees(Math.atan2(-d.x, d.z)), (float) -Math.toDegrees(Math.atan2(d.y, Math.sqrt(d.x*d.x + d.z*d.z))));
    }
    @Override public boolean select(int slot) {
        if (slot < 0 || slot > 8) return false;
        if (ApiCompat.selected(client.player.getInventory()) == slot) return true;
        long start=System.nanoTime(); selectionCount++;
        ApiCompat.select(client.player.getInventory(), slot); selectionNanos+=System.nanoTime()-start;
        return ApiCompat.selected(client.player.getInventory()) == slot;
    }
    @Override public boolean provision(String item) {
        if (!client.player.getAbilities().creativeMode || !Registries.ITEM.containsId(ApiCompat.id(item))) return false;
        ItemStack stack = Registries.ITEM.get(ApiCompat.id(item)).getDefaultStack(); if (stack.isEmpty()) return false;
        int slot = ApiCompat.selected(client.player.getInventory());
        client.player.getInventory().setStack(slot, stack);
        client.interactionManager.clickCreativeStack(stack.copy(), 36 + slot); return true;
    }
    private boolean material(String block) {
        String item = block.equals("minecraft:water") ? "minecraft:water_bucket" : block;
        Integer cached = materialSlots.get(item);
        if (cached != null) {
            ItemStack stack = client.player.getInventory().getStack(cached);
            if (!stack.isEmpty() && Registries.ITEM.getId(stack.getItem()).toString().equals(item)) return select(cached);
        }
        for (int slot = 0; slot < 9; slot++) {
            ItemStack stack = client.player.getInventory().getStack(slot);
            if (!stack.isEmpty() && Registries.ITEM.getId(stack.getItem()).toString().equals(item)) { materialSlots.put(item,slot); return select(slot); }
        }
        int workingSlot = materialSlots.computeIfAbsent(item, key -> materialSlots.size() % 9);
        return select(workingSlot) && provision(item);
    }

    @Override public String place(Pos p, String block, JsonObject expected) {
        if (!client.world.isChunkLoaded(pos(p))) return "target chunk unloaded";
        if (!client.world.getBlockState(pos(p)).isReplaceable()) return "target occupied";
        if (client.player.getBoundingBox().intersects(new Box(pos(p)))) return "player collision at target";
        if (flightRequested && flying() && MovementSafety.blocksFlightClearance(p,precisePosition()))
            return "placement would block owned flight clearance";
        if (!Registries.BLOCK.containsId(ApiCompat.id(block)) || !material(block)) return "material unavailable";
        for (Direction side : Direction.values()) {
            BlockPos support = pos(p).offset(side); BlockState supportState = client.world.getBlockState(support);
            if (supportState.isAir() || supportState.getOutlineShape(client.world, support).isEmpty()) continue;
            Direction face = side.getOpposite();
            Vec3d hitPoint = Vec3d.ofCenter(support).add(face.getOffsetX() * .4999, face.getOffsetY() * .4999, face.getOffsetZ() * .4999);
            if (face.getAxis().isHorizontal() && (expected.has("half") || expected.has("type"))) {
                String half = expected.has("half") ? expected.get("half").getAsString() : expected.get("type").getAsString();
                hitPoint = new Vec3d(hitPoint.x, support.getY() + (half.equals("top") ? .75 : .25), hitPoint.z);
            }
            if (client.player.getEyePos().squaredDistanceTo(hitPoint) > 4.5 * 4.5) continue;
            BlockHitResult ray = client.world.raycast(new RaycastContext(client.player.getEyePos(), hitPoint,
                RaycastContext.ShapeType.OUTLINE, RaycastContext.FluidHandling.NONE, client.player));
            if (ray.getType() != HitResult.Type.BLOCK || !ray.getBlockPos().equals(support) || ray.getSide() != face) continue;
            aim(hitPoint);
            BlockHitResult hit = new BlockHitResult(ray.getPos(), face, support, false);
            if (block.equals("minecraft:water")) {
                aim(hitPoint);
                if (client.interactionManager.interactItem(client.player, Hand.MAIN_HAND).isAccepted()) return "";
                continue;
            }
            for (float yaw : new float[]{client.player.getYaw(), 0, 90, 180, -90}) {
            look(yaw, client.player.getPitch());
            BlockState predicted = Registries.BLOCK.get(ApiCompat.id(block)).getPlacementState(new ItemPlacementContext(
                client.player, Hand.MAIN_HAND, client.player.getMainHandStack(), hit));
            if (predicted == null) continue;
            JsonObject prediction = new JsonObject(); prediction.addProperty("loaded", true); prediction.addProperty("block", block);
            JsonObject properties = new JsonObject();
            for (Property<?> property : predicted.getProperties()) properties.addProperty(property.getName(), property(predicted, property));
            prediction.add("properties", properties);
            JsonObject required = new JsonObject(); required.addProperty("block", block); required.add("properties", expected);
            if (!ActionExecutor.matches(prediction, required)) continue;
            if (client.interactionManager.interactBlock(client.player, Hand.MAIN_HAND, hit).isAccepted()) return "";
            }
        }
        return "no visible reachable face with the requested placement state";
    }

    private BlockHitResult hit(Pos target) {
        Vec3d center = Vec3d.ofCenter(pos(target));
        if (client.player.getEyePos().squaredDistanceTo(center) > 4.5 * 4.5) return null;
        BlockHitResult ray = client.world.raycast(new RaycastContext(client.player.getEyePos(), center,
            RaycastContext.ShapeType.OUTLINE, RaycastContext.FluidHandling.NONE, client.player));
        if (ray.getType() != HitResult.Type.BLOCK || !ray.getBlockPos().equals(pos(target))) return null;
        aim(ray.getPos()); return ray;
    }
    @Override public String breakBlock(Pos target) {
        if (client.world.getBlockState(pos(target)).isAir()) return "";
        BlockHitResult hit = hit(target); if (hit == null) return "break target out of reach or occluded";
        client.interactionManager.attackBlock(pos(target), hit.getSide());
        client.interactionManager.updateBlockBreakingProgress(pos(target), hit.getSide()); return "";
    }
    @Override public String interact(Pos target) {
        BlockHitResult hit = hit(target); if (hit == null) return "interaction target out of reach or occluded";
        return client.interactionManager.interactBlock(client.player, Hand.MAIN_HAND, hit).isAccepted() ? "" : "interaction rejected";
    }
    @Override public void releaseMovement() {
        client.options.forwardKey.setPressed(false); client.options.backKey.setPressed(false);
        client.options.leftKey.setPressed(false); client.options.rightKey.setPressed(false);
        client.options.jumpKey.setPressed(false); client.options.sneakKey.setPressed(false); client.options.sprintKey.setPressed(false);
        if (client.interactionManager != null) client.interactionManager.cancelBlockBreaking();
    }
    private static String hazard(BlockState state) {
        if (state.isOf(Blocks.LAVA)) return "lava";
        if (state.isOf(Blocks.FIRE) || state.isOf(Blocks.SOUL_FIRE)) return "fire";
        if (state.isOf(Blocks.MAGMA_BLOCK)) return "hot_surface";
        return "";
    }
    @Override public String unsafeFlight(Pos feet) {
        if (!ready() || !creative() || !client.world.isChunkLoaded(pos(feet))) return "unloaded or non-Creative flight";
        if (feet.y()<=client.world.getBottomY()+2) return "void risk";
        for (int y=0;y<=2;y++) {
            BlockState state=client.world.getBlockState(pos(feet.add(0,y,0)));
            if (!hazard(state).isEmpty()) return "hazard: "+hazard(state);
            if (state.isOf(Blocks.WATER)) return "water flight rejected";
            if (!state.getCollisionShape(client.world,pos(feet.add(0,y,0))).isEmpty()) return "flight collision";
        }
        return "";
    }
    @Override public String unsafe(Pos feet) {
        if (!ready() || !client.world.isChunkLoaded(pos(feet))) return "unloaded terrain";
        if (feet.y() <= client.world.getBottomY() + 2) return "void risk";
        for (int y = -1; y <= 1; y++) {
            BlockState state = client.world.getBlockState(pos(feet.add(0, y, 0)));
            if (!hazard(state).isEmpty()) return "hazard: " + hazard(state);
            if (state.isOf(Blocks.WATER)) return "water route requires drowning policy";
            if (y >= 0 && !state.getCollisionShape(client.world, pos(feet.add(0, y, 0))).isEmpty()) return "feet/head collision";
        }
        int drop = 0;
        while (drop < 5 && client.world.getBlockState(pos(feet.add(0, -drop - 1, 0))).getCollisionShape(client.world, pos(feet.add(0, -drop - 1, 0))).isEmpty()) drop++;
        return drop > 3 ? "unsafe drop" : "";
    }
    @Override public String immediateDanger() {
        if (!ready()) return "world unavailable";
        if (client.player.getHealth() <= 6) return "low health";
        Vec3d velocity = client.player.getVelocity();
        Pos next = MovementSafety.projectedFeet(client.player.getX(), client.player.getY(), client.player.getZ(),
            velocity.x, velocity.y, velocity.z, client.player.isOnGround());
        if (flying() && creative()) {
            if (velocity.y < 0) next = MovementSafety.clipDescendingToSupport(next, client.player.getY(), p ->
                !client.world.getBlockState(pos(p)).getCollisionShape(client.world, pos(p)).isEmpty());
            return unsafeFlight(next);
        }
          if (velocity.y < 0) {
              String actualDanger = unsafe(playerPosition());
              if (!actualDanger.isEmpty() && !actualDanger.equals("feet/head collision")) return actualDanger;
              next = MovementSafety.clipDescendingToSupport(next, client.player.getY(), p ->
                  !client.world.getBlockState(pos(p)).getCollisionShape(client.world, pos(p)).isEmpty());
          }
        // Guard immediate predicted movement, including a falling Creative player.
        String danger = unsafe(next);
        // Projected contact with a stair/one-block step is normal pathfinding, not suffocation.
        if (danger.equals("feet/head collision")) return client.player.isInsideWall() ? "suffocation" : "";
        return danger;
    }
}
