package dev.blockmind.minecraft;

import com.google.gson.JsonObject;
import net.minecraft.block.BlockState;
import net.minecraft.client.MinecraftClient;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.util.Identifier;
import net.minecraft.util.ActionResult;
import net.minecraft.util.Hand;
import net.minecraft.util.hit.BlockHitResult;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.Direction;
import net.minecraft.util.math.Vec3d;
import dev.blockmind.minecraft.navigation.NavigationProvider;

import java.util.ArrayDeque;
import java.util.Queue;

final class ActionExecutor {
    private final MinecraftClient client;
    private final TcpBridge bridge;
    private final NavigationProvider navigation;
    private final Queue<JsonObject> queue = new ArrayDeque<>();
    private final Queue<JsonObject> controls = new ArrayDeque<>();
    private Pending pending;
    private boolean paused;
    private boolean stopped;

    private record Pending(String id, String kind, BlockPos target, String expected, long deadline, boolean usedAlternative) {}

    ActionExecutor(MinecraftClient client, TcpBridge bridge, NavigationProvider navigation) {
        this.client = client;
        this.bridge = bridge;
        this.navigation = navigation;
    }

    void enqueue(JsonObject envelope) {
        if (envelope.get("type").getAsString().equals("control")) controls.add(envelope);
        else if (!stopped) queue.add(envelope);
        else result(envelope.get("id").getAsString(), false, "executor stopped", null, false);
    }

    void tick(long tick) {
        if (client.player == null || client.world == null || client.interactionManager == null) return;
        JsonObject controlEnvelope;
        while ((controlEnvelope = controls.poll()) != null) {
            String id = controlEnvelope.get("id").getAsString();
            control(controlEnvelope.getAsJsonObject("payload").get("kind").getAsString());
            result(id, true, "", null, false);
        }
        if (pending != null) {
            pollPending(tick);
            if (pending != null) return;
        }
        if (paused || stopped) return;
        JsonObject envelope = queue.poll();
        if (envelope == null) return;
        String type = envelope.get("type").getAsString();
        String id = envelope.get("id").getAsString();
        JsonObject payload = envelope.getAsJsonObject("payload");
        execute(id, payload, tick);
    }

    private void execute(String id, JsonObject action, long tick) {
        String kind = action.get("kind").getAsString();
        switch (kind) {
            case "observe_block" -> {
                BlockPos target = position(action.getAsJsonObject("position"));
                result(id, true, "", target, false);
            }
            case "navigate" -> {
                BlockPos target = position(action.getAsJsonObject("target"));
                boolean avoid = !action.has("avoidHazards") || action.get("avoidHazards").getAsBoolean();
                NavigationProvider.StartResult started = navigation.start(target, avoid);
                if (!started.accepted()) result(id, false, started.reason(), started.target(), started.usedAlternative());
                else pending = new Pending(id, kind, started.target(), null, tick + 20L * 120L, started.usedAlternative());
            }
            case "cancel_navigation" -> {
                navigation.cancel();
                result(id, true, "cancelled", client.player.getBlockPos(), false);
            }
            case "place_block" -> startPlace(id, action, tick);
            case "break_block" -> startBreak(id, action, tick);
            case "look" -> {
                client.player.setYaw(action.get("yaw").getAsFloat());
                client.player.setPitch(action.get("pitch").getAsFloat());
                result(id, true, "", client.player.getBlockPos(), false);
            }
            default -> result(id, false, "unsupported action: " + kind, client.player.getBlockPos(), false);
        }
    }

    private void startPlace(String id, JsonObject action, long tick) {
        BlockPos target = position(action.getAsJsonObject("position"));
        String blockId = action.get("block").getAsString();
        if (blockAt(target).equals(blockId)) {
            result(id, true, "already satisfied", target, false);
            return;
        }
        int slot = findHotbarItem(blockId);
        if (slot < 0 && client.player.getAbilities().creativeMode) {
            slot = provisionCreativeItem(blockId);
        }
        if (slot < 0) {
            result(id, false, "required block not in hotbar", target, false);
            return;
        }
        client.player.getInventory().setSelectedSlot(slot);
        for (Direction offset : Direction.values()) {
            BlockPos support = target.offset(offset);
            if (!client.world.getBlockState(support).isAir()) {
                Direction face = offset.getOpposite();
                BlockHitResult hit = new BlockHitResult(Vec3d.ofCenter(support), face, support, false);
                ActionResult response = client.interactionManager.interactBlock(client.player, Hand.MAIN_HAND, hit);
                if (response.isAccepted()) {
                    pending = new Pending(id, "place_block", target, blockId, tick + 20, false);
                    return;
                }
            }
        }
        result(id, false, "no reachable support face; scaffold/reposition required", target, false);
    }

    private void startBreak(String id, JsonObject action, long tick) {
        BlockPos target = position(action.getAsJsonObject("position"));
        if (client.world.getBlockState(target).isAir()) {
            result(id, true, "already air", target, false);
            return;
        }
        client.interactionManager.attackBlock(target, Direction.UP);
        pending = new Pending(id, "break_block", target, "minecraft:air", tick + 80, false);
    }

    private void pollPending(long tick) {
        if (pending.kind.equals("navigate")) {
            NavigationProvider.NavigationStatus status = navigation.poll();
            if (status.state() == NavigationProvider.NavigationStatus.State.RUNNING) return;
            boolean success = status.state() == NavigationProvider.NavigationStatus.State.SUCCEEDED;
            result(pending.id, success, status.reason(), status.position(), pending.usedAlternative);
            pending = null;
            return;
        }
        if (pending.kind.equals("break_block") && !client.world.getBlockState(pending.target).isAir()) {
            client.interactionManager.updateBlockBreakingProgress(pending.target, Direction.UP);
        }
        if (blockAt(pending.target).equals(pending.expected)) {
            result(pending.id, true, "verified", pending.target, false);
            pending = null;
        } else if (tick >= pending.deadline) {
            result(pending.id, false, "world did not reach expected state", pending.target, false);
            pending = null;
        }
    }

    void emergencyStop() {
        queue.clear();
        pending = null;
        navigation.cancel();
        client.options.forwardKey.setPressed(false);
        client.options.backKey.setPressed(false);
        client.options.leftKey.setPressed(false);
        client.options.rightKey.setPressed(false);
        client.options.jumpKey.setPressed(false);
        client.options.sneakKey.setPressed(false);
        client.options.sprintKey.setPressed(false);
    }

    private void control(String kind) {
        switch (kind) {
            case "pause" -> paused = true;
            case "resume" -> paused = false;
            case "stop", "emergency_stop" -> {
                emergencyStop();
                stopped = true;
            }
            default -> { }
        }
    }

    private int findHotbarItem(String blockId) {
        String itemId = blockId.equals("minecraft:water") ? "minecraft:water_bucket" : blockId;
        for (int slot = 0; slot < 9; slot++) {
            ItemStack stack = client.player.getInventory().getStack(slot);
            if (Registries.ITEM.getId(stack.getItem()).toString().equals(itemId)) return slot;
        }
        return -1;
    }

    private int provisionCreativeItem(String blockId) {
        String itemId = blockId.equals("minecraft:water") ? "minecraft:water_bucket" : blockId;
        ItemStack stack = Registries.ITEM.get(Identifier.of(itemId)).getDefaultStack();
        if (stack.isEmpty()) return -1;
        int slot = client.player.getInventory().getSelectedSlot();
        client.interactionManager.clickCreativeStack(stack, 36 + slot);
        return slot;
    }

    private String blockAt(BlockPos position) {
        BlockState state = client.world.getBlockState(position);
        return Registries.BLOCK.getId(state.getBlock()).toString();
    }

    private void result(String id, boolean success, String reason, BlockPos observed, boolean alternative) {
        JsonObject payload = new JsonObject();
        payload.addProperty("success", success);
        payload.addProperty("reason", reason);
        payload.addProperty("usedAlternative", alternative);
        BlockPos position = observed == null ? client.player.getBlockPos() : observed;
        payload.add("position", ObservationCollector.position(position));
        if (observed != null) payload.addProperty("observedBlock", blockAt(observed));
        bridge.send("action_result", id, payload);
    }

    private static BlockPos position(JsonObject value) {
        return new BlockPos(value.get("x").getAsInt(), value.get("y").getAsInt(), value.get("z").getAsInt());
    }
}
