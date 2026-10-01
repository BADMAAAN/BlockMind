package dev.blockmind.minecraft;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
public final class GameBindings {
    public static GameAccess create() { return new OfficialGameAccess(); }
    public static void onTick(Runnable callback) { ClientTickEvents.END_CLIENT_TICK.register(client -> callback.run()); }
}
