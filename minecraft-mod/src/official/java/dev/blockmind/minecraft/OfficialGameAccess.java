package dev.blockmind.minecraft;

import com.google.gson.*;
import net.minecraft.world.level.block.*;
import net.minecraft.client.Minecraft;
import net.minecraft.world.item.*;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.level.block.state.properties.Property;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.phys.*;
import net.minecraft.core.*;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.ClipContext;

/** Official-name API family for unobfuscated Minecraft 26.x. */
final class OfficialGameAccess implements GameAccess {
    private final AudioSession audio = new AudioSession(() -> this.client.options.getSoundSourceVolume(net.minecraft.sounds.SoundSource.MASTER), value -> this.client.options.getSoundSourceOptionInstance(net.minecraft.sounds.SoundSource.MASTER).set(value));
    private long rotationNanos, selectionNanos;
    private int rotationCount, selectionCount;
    private final java.util.Map<String, Integer> materialSlots = new java.util.LinkedHashMap<>();
    @Override public boolean creative() { return client.player.getAbilities().instabuild; }
    private boolean flightRequested, flightOwned, previousFlight;
    private Object flightPlayer;
    @Override public boolean flying() { return ready() && client.player.getAbilities().flying; }
    @Override public boolean configureFlight(boolean enabled) {
        if (!enabled) flightRequested = false;
        if (!ready() || client.player != flightPlayer) { flightOwned = false; flightPlayer = null; }
        if (!ready()) return !enabled;
        if (enabled && (!creative() || !client.player.getAbilities().mayfly)) return false;
        flightRequested = enabled;
        if (enabled) {
            if (!flightOwned) { previousFlight = flying(); flightOwned = true; flightPlayer = client.player; }
            tickFlight();
        } else if (flightOwned && (previousFlight || client.player.onGround())) {
            client.player.getAbilities().flying = previousFlight;
            client.player.onUpdateAbilities(); flightOwned = false;
        }
        // On cancellation in midair, keep normal Creative hovering rather than
        // disabling the ability and causing an unrequested fall.
        return true;
    }
    @Override public void tickFlight() {
        if (!flightRequested || !ready() || client.player != flightPlayer || !creative() || flying()) return;
        if (client.player.onGround()) client.options.keyJump.setDown(true);
        else {
            client.player.getAbilities().flying = true; client.player.onUpdateAbilities();
            client.options.keyJump.setDown(false);
        }
    }
    @Override public String flightMove(Pos target) {
        if (!ready() || !creative() || !flightRequested) return "Creative flight unavailable";
        tickFlight();
        if (!flying()) return "moving";
        releaseMovement();
        double dx=target.x()+.5-client.player.getX(), dy=target.y()+.35-client.player.getY(), dz=target.z()+.5-client.player.getZ();
        Vec3 velocity=client.player.getDeltaMovement();
        if (dx*dx+dz*dz < .0225 && Math.abs(dy)<.1 && velocity.lengthSqr()<.0025) return "arrived";
        double steerX=dx-velocity.x*2.5, steerZ=dz-velocity.z*2.5, steerY=dy-velocity.y*2.5;
        if (steerX*steerX+steerZ*steerZ>.0225) {
            look((float)Math.toDegrees(Math.atan2(-steerX,steerZ)),0);
            client.options.keyUp.setDown(true);
        }
        client.options.keyJump.setDown(steerY>.1); client.options.keyShift.setDown(steerY<-.1);
        return "moving";
    }
    @Override public void configureAudio(boolean mute, boolean restore) { audio.begin(mute, restore); }
    @Override public void finishAudio() { audio.finish(); }
    @Override public JsonObject performance() {
        JsonObject value = new JsonObject(); value.addProperty("rotationSeconds", rotationNanos / 1e9);
        value.addProperty("selectionSeconds", selectionNanos / 1e9); value.addProperty("rotations", rotationCount);
        value.addProperty("selections", selectionCount); value.addProperty("masterVolume", client.options.getSoundSourceVolume(net.minecraft.sounds.SoundSource.MASTER)); return value;
    }
    @Override public String localMove(Pos target) {
        Pos here = playerPosition();
        if (!client.player.onGround() || here.y() != target.y() || Math.abs(here.x()-target.x()) + Math.abs(here.z()-target.z()) > 2) return "unsupported";
        for (int step = 1; step <= 3; step++) {
            Pos sample = new Pos((int)Math.floor(client.player.getX() + (target.x()+.5-client.player.getX())*step/3),
                target.y(), (int)Math.floor(client.player.getZ() + (target.z()+.5-client.player.getZ())*step/3));
            if (!unsafe(sample).isEmpty()) return "unsupported";
        }
        double dx = target.x()+.5-client.player.getX(), dz = target.z()+.5-client.player.getZ();
        if (dx*dx+dz*dz < .04) { releaseMovement(); return "arrived"; }
        releaseMovement(); look((float)Math.toDegrees(Math.atan2(-dx,dz)), client.player.getXRot());
        client.options.keyUp.setDown(true); return "moving";
    }
    private final Minecraft client = Minecraft.getInstance();
    private BlockPos pos(Pos p) { return new BlockPos(p.x(), p.y(), p.z()); }
    private Pos point(BlockPos p) { return new Pos(p.getX(), p.getY(), p.getZ()); }
    @Override public boolean ready() { return client.player != null && client.level != null && client.gameMode != null; }
    @Override public Pos playerPosition() { return client.player == null ? new Pos(0, 0, 0) : point(client.player.blockPosition()); }
    @Override public double[] precisePosition() { return new double[]{client.player.getX(), client.player.getY(), client.player.getZ()}; }
    @Override public String dimension() { return client.level.dimension().identifier().toString(); }
    private static <T extends Comparable<T>> String property(BlockState state, Property<T> property) { return property.getName(state.getValue(property)); }

    @Override public JsonObject inspect(Pos p) {
        JsonObject value = new JsonObject(); value.add("position", p.json());
        boolean loaded = ready() && client.level.hasChunkAt(pos(p)); value.addProperty("loaded", loaded);
        if (!loaded) return value;
        BlockState state = client.level.getBlockState(pos(p));
        value.addProperty("block", BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString());
        JsonObject properties = new JsonObject();
        for (Property<?> property : state.getProperties()) properties.addProperty(property.getName(), property(state, property));
        value.add("properties", properties); value.addProperty("replaceable", state.canBeReplaced());
        value.addProperty("solid", !state.getCollisionShape(client.level, pos(p)).isEmpty());
        return value;
    }

    @Override public JsonObject observe(int radius, long tick) {
        JsonObject root = new JsonObject(); root.addProperty("tick", tick); root.addProperty("radius", radius);
        JsonObject player = new JsonObject(); player.add("position", playerPosition().json());
        player.addProperty("dimension", dimension()); player.addProperty("health", client.player.getHealth());
        player.addProperty("hunger", client.player.getFoodData().getFoodLevel());
        player.addProperty("creative", client.player.getAbilities().instabuild); player.addProperty("onGround", client.player.onGround());
        player.addProperty("flying", flying());
        JsonArray eye = new JsonArray(); eye.add(client.player.getEyePosition().x); eye.add(client.player.getEyePosition().y); eye.add(client.player.getEyePosition().z); player.add("eye", eye);
        JsonArray velocity = new JsonArray(); Vec3 v = client.player.getDeltaMovement(); velocity.add(v.x); velocity.add(v.y); velocity.add(v.z); player.add("velocity", velocity);
        JsonArray inventory = new JsonArray();
        for (int slot = 0; slot < client.player.getInventory().getContainerSize(); slot++) {
            ItemStack stack = client.player.getInventory().getItem(slot); if (stack.isEmpty()) continue;
            JsonObject entry = new JsonObject(); entry.addProperty("slot", slot);
            entry.addProperty("item", BuiltInRegistries.ITEM.getKey(stack.getItem()).toString()); entry.addProperty("count", stack.getCount()); inventory.add(entry);
        }
        player.add("inventory", inventory); root.add("player", player);
        JsonArray blocks = new JsonArray(); JsonArray hazards = new JsonArray(); BlockPos center = client.player.blockPosition();
        for (BlockPos p : BlockPos.betweenClosed(center.offset(-radius, -radius, -radius), center.offset(radius, radius, radius))) {
            BlockState state = client.level.getBlockState(p);
            if (!state.isAir()) blocks.add(inspect(point(p)));
            String hazard = hazard(state);
            if (!hazard.isEmpty()) {
                JsonObject h = new JsonObject(); h.add("position", point(p).json()); h.addProperty("kind", hazard); h.addProperty("severity", 1.0); hazards.add(h);
            }
        }
        root.add("blocks", blocks); root.add("hazards", hazards);
        JsonArray entities = new JsonArray();
        for (var entity : client.level.getEntities(client.player, client.player.getBoundingBox().inflate(radius))) {
            JsonObject e = new JsonObject(); e.addProperty("type", BuiltInRegistries.ENTITY_TYPE.getKey(entity.getType()).toString());
            e.add("position", point(entity.blockPosition()).json()); entities.add(e);
        }
        root.add("entities", entities); return root;
    }

    @Override public void look(float yaw, float pitch) {
        if (Math.abs(client.player.getYRot()-yaw)<.01 && Math.abs(client.player.getXRot()-pitch)<.01) return;
        long start=System.nanoTime(); rotationCount++;
        client.player.setYRot(yaw); client.player.setXRot(Math.max(-90, Math.min(90, pitch)));
        client.player.connection.send(new net.minecraft.network.protocol.game.ServerboundMovePlayerPacket.Rot(
            client.player.getYRot(), client.player.getXRot(), client.player.onGround(), client.player.horizontalCollision));
        rotationNanos+=System.nanoTime()-start;
    }
    private void aim(Vec3 target) {
        Vec3 d = target.subtract(client.player.getEyePosition());
        look((float) Math.toDegrees(Math.atan2(-d.x, d.z)), (float) -Math.toDegrees(Math.atan2(d.y, Math.sqrt(d.x*d.x + d.z*d.z))));
    }
    @Override public boolean select(int slot) {
        if (slot < 0 || slot > 8) return false;
        if (client.player.getInventory().getSelectedSlot() == slot) return true;
        long start=System.nanoTime(); selectionCount++;
        client.player.getInventory().setSelectedSlot(slot); selectionNanos+=System.nanoTime()-start;
        return client.player.getInventory().getSelectedSlot() == slot;
    }
    @Override public boolean provision(String item) {
        if (!client.player.getAbilities().instabuild || !BuiltInRegistries.ITEM.containsKey(Identifier.parse(item))) return false;
        ItemStack stack = new ItemStack(BuiltInRegistries.ITEM.getValue(Identifier.parse(item))); if (stack.isEmpty()) return false;
        int slot = client.player.getInventory().getSelectedSlot();
        client.player.getInventory().setItem(slot, stack);
        client.gameMode.handleCreativeModeItemAdd(stack.copy(), 36 + slot); return true;
    }
    private boolean material(String block) {
        String item = block.equals("minecraft:water") ? "minecraft:water_bucket" : block;
        Integer cached = materialSlots.get(item);
        if (cached != null) {
            ItemStack stack = client.player.getInventory().getItem(cached);
            if (!stack.isEmpty() && BuiltInRegistries.ITEM.getKey(stack.getItem()).toString().equals(item)) return select(cached);
        }
        for (int slot = 0; slot < 9; slot++) {
            ItemStack stack = client.player.getInventory().getItem(slot);
            if (!stack.isEmpty() && BuiltInRegistries.ITEM.getKey(stack.getItem()).toString().equals(item)) { materialSlots.put(item,slot); return select(slot); }
        }
        int workingSlot = materialSlots.computeIfAbsent(item, key -> materialSlots.size() % 9);
        return select(workingSlot) && provision(item);
    }

    @Override public String place(Pos p, String block, JsonObject expected) {
        if (!client.level.hasChunkAt(pos(p))) return "target chunk unloaded";
        if (!client.level.getBlockState(pos(p)).canBeReplaced()) return "target occupied";
        if (client.player.getBoundingBox().intersects(new AABB(pos(p)))) return "player collision at target";
        if (flightRequested && flying() && MovementSafety.blocksFlightClearance(p,precisePosition()))
            return "placement would block owned flight clearance";
        if (!BuiltInRegistries.BLOCK.containsKey(Identifier.parse(block)) || !material(block)) return "material unavailable";
        for (Direction side : Direction.values()) {
            BlockPos support = pos(p).relative(side); BlockState supportState = client.level.getBlockState(support);
            if (supportState.isAir() || supportState.getShape(client.level, support).isEmpty()) continue;
            Direction face = side.getOpposite();
            Vec3 hitPoint = Vec3.atCenterOf(support).add(face.getStepX() * .4999, face.getStepY() * .4999, face.getStepZ() * .4999);
            if (face.getAxis().isHorizontal() && (expected.has("half") || expected.has("type"))) {
                String half = expected.has("half") ? expected.get("half").getAsString() : expected.get("type").getAsString();
                hitPoint = new Vec3(hitPoint.x, support.getY() + (half.equals("top") ? .75 : .25), hitPoint.z);
            }
            if (client.player.getEyePosition().distanceToSqr(hitPoint) > 4.5 * 4.5) continue;
            BlockHitResult ray = client.level.clip(new ClipContext(client.player.getEyePosition(), hitPoint,
                ClipContext.Block.OUTLINE, ClipContext.Fluid.NONE, client.player));
            if (ray.getType() != HitResult.Type.BLOCK || !ray.getBlockPos().equals(support) || ray.getDirection() != face) continue;
            aim(hitPoint);
            BlockHitResult hit = new BlockHitResult(ray.getLocation(), face, support, false);
            if (block.equals("minecraft:water")) {
                aim(hitPoint);
                if (client.gameMode.useItem(client.player, InteractionHand.MAIN_HAND).consumesAction()) return "";
                continue;
            }
            for (float yaw : new float[]{client.player.getYRot(), 0, 90, 180, -90}) {
            look(yaw, client.player.getXRot());
            BlockState predicted = BuiltInRegistries.BLOCK.getValue(Identifier.parse(block)).getStateForPlacement(new BlockPlaceContext(
                client.player, InteractionHand.MAIN_HAND, client.player.getMainHandItem(), hit));
            if (predicted == null) continue;
            JsonObject prediction = new JsonObject(); prediction.addProperty("loaded", true); prediction.addProperty("block", block);
            JsonObject properties = new JsonObject();
            for (Property<?> property : predicted.getProperties()) properties.addProperty(property.getName(), property(predicted, property));
            prediction.add("properties", properties);
            JsonObject required = new JsonObject(); required.addProperty("block", block); required.add("properties", expected);
            if (!ActionExecutor.matches(prediction, required)) continue;
            if (client.gameMode.useItemOn(client.player, InteractionHand.MAIN_HAND, hit).consumesAction()) return "";
            }
        }
        return "no visible reachable face with the requested placement state";
    }

    private BlockHitResult hit(Pos target) {
        Vec3 center = Vec3.atCenterOf(pos(target));
        if (client.player.getEyePosition().distanceToSqr(center) > 4.5 * 4.5) return null;
        BlockHitResult ray = client.level.clip(new ClipContext(client.player.getEyePosition(), center,
            ClipContext.Block.OUTLINE, ClipContext.Fluid.NONE, client.player));
        if (ray.getType() != HitResult.Type.BLOCK || !ray.getBlockPos().equals(pos(target))) return null;
        aim(ray.getLocation()); return ray;
    }
    @Override public String breakBlock(Pos target) {
        if (client.level.getBlockState(pos(target)).isAir()) return "";
        BlockHitResult hit = hit(target); if (hit == null) return "break target out of reach or occluded";
        client.gameMode.startDestroyBlock(pos(target), hit.getDirection());
        client.gameMode.continueDestroyBlock(pos(target), hit.getDirection()); return "";
    }
    @Override public String interact(Pos target) {
        BlockHitResult hit = hit(target); if (hit == null) return "interaction target out of reach or occluded";
        return client.gameMode.useItemOn(client.player, InteractionHand.MAIN_HAND, hit).consumesAction() ? "" : "interaction rejected";
    }
    @Override public void releaseMovement() {
        client.options.keyUp.setDown(false); client.options.keyDown.setDown(false);
        client.options.keyLeft.setDown(false); client.options.keyRight.setDown(false);
        client.options.keyJump.setDown(false); client.options.keyShift.setDown(false); client.options.keySprint.setDown(false);
        if (client.gameMode != null) client.gameMode.stopDestroyBlock();
    }
    private static String hazard(BlockState state) {
        if (state.is(Blocks.LAVA)) return "lava";
        if (state.is(Blocks.FIRE) || state.is(Blocks.SOUL_FIRE)) return "fire";
        if (state.is(Blocks.MAGMA_BLOCK)) return "hot_surface";
        return "";
    }
    @Override public String unsafeFlight(Pos feet) {
        if (!ready() || !creative() || !client.level.hasChunkAt(pos(feet))) return "unloaded or non-Creative flight";
        if (feet.y()<=client.level.getMinY()+2) return "void risk";
        for (int y=0;y<=2;y++) {
            BlockState state=client.level.getBlockState(pos(feet.add(0,y,0)));
            if (!hazard(state).isEmpty()) return "hazard: "+hazard(state);
            if (state.is(Blocks.WATER)) return "water flight rejected";
            if (!state.getCollisionShape(client.level,pos(feet.add(0,y,0))).isEmpty()) return "flight collision";
        }
        return "";
    }
    @Override public String unsafe(Pos feet) {
        if (!ready() || !client.level.hasChunkAt(pos(feet))) return "unloaded terrain";
        if (feet.y() <= client.level.getMinY() + 2) return "void risk";
        for (int y = -1; y <= 1; y++) {
            BlockState state = client.level.getBlockState(pos(feet.add(0, y, 0)));
            if (!hazard(state).isEmpty()) return "hazard: " + hazard(state);
            if (state.is(Blocks.WATER)) return "water route requires drowning policy";
            if (y >= 0 && !state.getCollisionShape(client.level, pos(feet.add(0, y, 0))).isEmpty()) return "feet/head collision";
        }
        int drop = 0;
        while (drop < 5 && client.level.getBlockState(pos(feet.add(0, -drop - 1, 0))).getCollisionShape(client.level, pos(feet.add(0, -drop - 1, 0))).isEmpty()) drop++;
        return drop > 3 ? "unsafe drop" : "";
    }
    @Override public String immediateDanger() {
        if (!ready()) return "world unavailable";
        if (client.player.getHealth() <= 6) return "low health";
        Vec3 velocity = client.player.getDeltaMovement();
        Pos next = MovementSafety.projectedFeet(client.player.getX(), client.player.getY(), client.player.getZ(),
            velocity.x, velocity.y, velocity.z, client.player.onGround());
        if (flying() && creative()) {
            if (velocity.y < 0) next = MovementSafety.clipDescendingToSupport(next, client.player.getY(), p ->
                !client.level.getBlockState(pos(p)).getCollisionShape(client.level, pos(p)).isEmpty());
            return unsafeFlight(next);
        }
          if (velocity.y < 0) {
              String actualDanger = unsafe(playerPosition());
              if (!actualDanger.isEmpty() && !actualDanger.equals("feet/head collision")) return actualDanger;
              next = MovementSafety.clipDescendingToSupport(next, client.player.getY(), p ->
                  !client.level.getBlockState(pos(p)).getCollisionShape(client.level, pos(p)).isEmpty());
          }
        // Guard immediate predicted movement, including a falling Creative player.
        String danger = unsafe(next);
        if (danger.equals("feet/head collision")) return client.player.isInWall() ? "suffocation" : "";
        return danger;
    }
}
