package dev.blockmind.minecraft;
import net.minecraft.entity.player.PlayerInventory;
import net.minecraft.util.Identifier;
final class ApiCompat {
    static Identifier id(String value) { return Identifier.of(value); }
    static int selected(PlayerInventory inventory) { return inventory.getSelectedSlot(); }
    static void select(PlayerInventory inventory, int slot) { inventory.setSelectedSlot(slot); }
    static void syncLook(net.minecraft.client.MinecraftClient client) {
        client.player.networkHandler.sendPacket(new net.minecraft.network.packet.c2s.play.PlayerMoveC2SPacket.LookAndOnGround(
            client.player.getYaw(), client.player.getPitch(), client.player.isOnGround(), client.player.horizontalCollision));
    }
}
