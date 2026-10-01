package dev.blockmind.minecraft;

import com.google.gson.*;
import dev.blockmind.minecraft.navigation.*;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.loader.api.FabricLoader;
import org.slf4j.*;

public final class BlockMindClient implements ClientModInitializer {
    private static final Logger LOG = LoggerFactory.getLogger("blockmind");
    private long tick;
    private int generation;
    private boolean lastAvailability;
    private boolean lastReady;
    private GameAccess game;
    private TcpBridge bridge;
    private ActionExecutor actions;
    private NavigationProvider navigation;
    @Override public void onInitializeClient() {
        game = GameBindings.create();
        navigation = new SafeNavigationProvider(game, new LocalNavigationProvider(game, new BaritoneNavigationProvider(game)));
        bridge = new TcpBridge(LOG, metadata());
        actions = new ActionExecutor(game, bridge, navigation);
        GameBindings.onTick(this::onTick);
        Runtime.getRuntime().addShutdownHook(new Thread(bridge::close, "blockmind-shutdown"));
        LOG.info("[BLOCKMIND] mode=LIVE adapter={} protocol={}", adapterVersion(), TcpBridge.PROTOCOL);
    }
    private static String adapterVersion() {
        return FabricLoader.getInstance().getModContainer("blockmind").orElseThrow().getMetadata().getVersion().getFriendlyString();
    }
    private JsonObject metadata() {
        JsonObject value = new JsonObject();
        value.addProperty("adapter", "blockmind-fabric"); value.addProperty("adapterVersion", adapterVersion());
        value.addProperty("minecraft", FabricLoader.getInstance().getModContainer("minecraft").orElseThrow().getMetadata().getVersion().getFriendlyString());
        value.addProperty("protocol", TcpBridge.PROTOCOL);
        JsonArray capabilities = new JsonArray();
        for (String c : new String[]{"OBSERVE_BLOCKS", "OBSERVE_ENTITIES", "PLACE_BLOCK", "BREAK_BLOCK", "INTERACT",
            "CREATIVE_PROVISION", "CANCEL_NAVIGATION", "BLOCK_STATE_ORIENTATION", "HAZARD_SCAN", "LOOK", "SELECT_HOTBAR",
            "ACTION_BATCH", "VALIDATE_BATCH", "EXECUTION_CONFIG", "AUDIO_CONTROL", "PERFORMANCE_METRICS"}) capabilities.add(c);
        // The primary Baritone instance is initialized after client entrypoints, not before them.
        lastAvailability = game.ready() && navigation.available();
        if (lastAvailability) capabilities.add("NAVIGATE");
        value.add("capabilities", capabilities);
        JsonObject nav = new JsonObject(); nav.addProperty("provider", "baritone"); nav.addProperty("available", lastAvailability);
        value.add("navigation", nav); return value;
    }
    private void onTick() {
        tick++;
        if (generation != bridge.generation()) {
            generation = bridge.generation();
            if (bridge.connected()) actions.newSession(); else actions.disconnect();
        }
        if (lastReady && !game.ready()) actions.disconnect();
        lastReady = game.ready();
        if (tick % 40 == 0 && lastAvailability != (game.ready() && navigation.available())) bridge.metadata(metadata());
        JsonObject value;
        while ((value = bridge.poll()) != null) {
            if (bridge.connected() && value.get("_generation").getAsInt() == generation) actions.enqueue(value);
        }
        actions.tick(tick);
        if (tick % 40 == 0 && bridge.connected() && game.ready()) bridge.send("observation", null, game.observe(6, tick));
    }
}
