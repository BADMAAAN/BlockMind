package dev.blockmind.minecraft;

import com.google.gson.JsonObject;
import dev.blockmind.minecraft.navigation.BaritoneNavigationProvider;
import dev.blockmind.minecraft.navigation.NavigationProvider;
import dev.blockmind.minecraft.navigation.SafeNavigationProvider;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.minecraft.client.MinecraftClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class BlockMindClient implements ClientModInitializer {
    private static final Logger LOG = LoggerFactory.getLogger("blockmind");
    private long tick;
    private TcpBridge bridge;
    private ActionExecutor actions;
    private ObservationCollector observations;

    @Override
    public void onInitializeClient() {
        MinecraftClient client = MinecraftClient.getInstance();
        bridge = new TcpBridge(LOG);
        NavigationProvider navigation = new SafeNavigationProvider(client, new BaritoneNavigationProvider(client));
        actions = new ActionExecutor(client, bridge, navigation);
        observations = new ObservationCollector(client);
        ClientTickEvents.END_CLIENT_TICK.register(this::onTick);
        Runtime.getRuntime().addShutdownHook(new Thread(bridge::close, "blockmind-shutdown"));
        LOG.info("BlockMind adapter initialized; Baritone available={}", navigation.available());
    }

    private void onTick(MinecraftClient client) {
        tick++;
        JsonObject incoming;
        while ((incoming = bridge.poll()) != null) actions.enqueue(incoming);
        actions.tick(tick);
        if (tick % 10 == 0 && client.player != null && client.world != null) {
            bridge.send("observation", null, observations.collect(tick, 6));
        }
    }
}
