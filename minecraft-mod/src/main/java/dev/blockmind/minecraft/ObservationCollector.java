package dev.blockmind.minecraft;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import net.minecraft.block.BlockState;
import net.minecraft.block.Blocks;
import net.minecraft.client.MinecraftClient;
import net.minecraft.entity.Entity;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.util.Identifier;
import net.minecraft.util.math.BlockPos;

final class ObservationCollector {
    private final MinecraftClient client;

    ObservationCollector(MinecraftClient client) { this.client = client; }

    JsonObject collect(long tick, int radius) {
        JsonObject root = new JsonObject();
        root.addProperty("tick", tick);
        root.addProperty("radius", radius);
        JsonObject player = new JsonObject();
        BlockPos center = client.player.getBlockPos();
        player.add("position", position(center));
        player.addProperty("dimension", client.world.getRegistryKey().getValue().toString());
        player.addProperty("health", client.player.getHealth());
        player.addProperty("hunger", client.player.getHungerManager().getFoodLevel());
        player.addProperty("creative", client.player.getAbilities().creativeMode);
        player.addProperty("onGround", client.player.isOnGround());
        JsonArray inventory = new JsonArray();
        for (int i = 0; i < client.player.getInventory().size(); i++) {
            ItemStack stack = client.player.getInventory().getStack(i);
            if (stack.isEmpty()) continue;
            JsonObject entry = new JsonObject();
            entry.addProperty("slot", i);
            entry.addProperty("item", Registries.ITEM.getId(stack.getItem()).toString());
            entry.addProperty("count", stack.getCount());
            inventory.add(entry);
        }
        player.add("inventory", inventory);
        root.add("player", player);

        JsonArray blocks = new JsonArray();
        JsonArray hazards = new JsonArray();
        for (BlockPos pos : BlockPos.iterate(center.add(-radius, -radius, -radius), center.add(radius, radius, radius))) {
            BlockState state = client.world.getBlockState(pos);
            if (!state.isAir()) {
                JsonObject entry = new JsonObject();
                entry.add("position", position(pos));
                entry.addProperty("block", Registries.BLOCK.getId(state.getBlock()).toString());
                blocks.add(entry);
            }
            String kind = null;
            if (state.isOf(Blocks.LAVA)) kind = "lava";
            else if (state.isOf(Blocks.FIRE) || state.isOf(Blocks.SOUL_FIRE)) kind = "fire";
            else if (state.isOf(Blocks.MAGMA_BLOCK)) kind = "hot_surface";
            if (kind != null) {
                JsonObject hazard = new JsonObject();
                hazard.addProperty("kind", kind);
                hazard.add("position", position(pos));
                hazard.addProperty("severity", 1.0);
                hazards.add(hazard);
            }
        }
        root.add("blocks", blocks);
        root.add("hazards", hazards);

        JsonArray entities = new JsonArray();
        for (Entity entity : client.world.getOtherEntities(client.player, client.player.getBoundingBox().expand(radius))) {
            JsonObject entry = new JsonObject();
            Identifier id = Registries.ENTITY_TYPE.getId(entity.getType());
            entry.addProperty("type", id.toString());
            entry.add("position", position(entity.getBlockPos()));
            entities.add(entry);
        }
        root.add("entities", entities);
        return root;
    }

    static JsonObject position(BlockPos pos) {
        JsonObject result = new JsonObject();
        result.addProperty("x", pos.getX());
        result.addProperty("y", pos.getY());
        result.addProperty("z", pos.getZ());
        return result;
    }
}
