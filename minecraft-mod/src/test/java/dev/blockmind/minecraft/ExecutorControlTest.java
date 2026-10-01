package dev.blockmind.minecraft;

import com.google.gson.*;
import dev.blockmind.minecraft.GameAccess.Pos;
import dev.blockmind.minecraft.navigation.NavigationProvider;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ExecutorControlTest {
    static class Game implements GameAccess {
        int mutations;
        public boolean ready() { return true; }
        public Pos playerPosition() { return new Pos(0, 64, 0); }
        public String dimension() { return "minecraft:overworld"; }
        public JsonObject observe(int radius, long tick) { return new JsonObject(); }
        public JsonObject inspect(Pos p) {
            JsonObject value = new JsonObject(); value.addProperty("loaded", true);
            value.addProperty("block", "minecraft:air"); value.add("properties", new JsonObject()); return value;
        }
        public String place(Pos p, String b, JsonObject props) { mutations++; return ""; }
        public String breakBlock(Pos p) { mutations++; return ""; }
        public String interact(Pos p) { mutations++; return ""; }
        public void look(float yaw, float pitch) { }
        public boolean select(int slot) { return true; }
        public boolean provision(String item) { return true; }
        public void releaseMovement() { }
        public String unsafe(Pos feet) { return ""; }
        public String immediateDanger() { return ""; }
    }
    static class Navigation implements NavigationProvider {
        boolean cancelled;
        public StartResult start(Pos target, boolean avoid) { return new StartResult(true, target, "", false); }
        public NavigationStatus poll() { return new NavigationStatus(NavigationStatus.State.RUNNING, new Pos(0, 64, 0), ""); }
        public void cancel() { cancelled = true; }
        public boolean available() { return true; }
    }
    JsonObject request(String id, String type, String payload) {
        JsonObject value = new JsonObject(); value.addProperty("id", id); value.addProperty("type", type);
        value.add("payload", JsonParser.parseString(payload)); return value;
    }
    @Test void emergencyStopInterruptsNavigationAndClearsQueuedMutations() {
        Game game = new Game(); Navigation navigation = new Navigation(); Map<String, JsonObject> responses = new HashMap<>();
        ActionExecutor executor = new ActionExecutor(game, responses::put, navigation);
        executor.enqueue(request("nav", "action", "{\"kind\":\"navigate\",\"target\":{\"x\":1,\"y\":64,\"z\":0}}"));
        executor.tick(1);
        executor.enqueue(request("place", "action", "{\"kind\":\"place_block\",\"position\":{\"x\":1,\"y\":64,\"z\":0},\"block\":\"minecraft:stone\"}"));
        executor.enqueue(request("halt", "control", "{\"kind\":\"emergency_stop\"}"));
        executor.tick(2);
        assertTrue(navigation.cancelled); assertEquals(0, game.mutations);
        assertFalse(responses.get("nav").get("success").getAsBoolean());
        assertFalse(responses.get("place").get("success").getAsBoolean());
        assertTrue(responses.get("halt").get("success").getAsBoolean());
    }
    @Test void destructiveActionRequiresRegionAndDuplicateRequestIsNotReexecuted() {
        Game game = new Game(); Map<String, JsonObject> replies = new HashMap<>();
        ActionExecutor executor = new ActionExecutor(game, replies::put, new Navigation());
        JsonObject action = request("break", "action", "{\"kind\":\"break_block\",\"position\":{\"x\":1,\"y\":64,\"z\":0}}");
        executor.enqueue(action); executor.tick(1);
        assertEquals(0, game.mutations); assertFalse(replies.get("break").get("success").getAsBoolean());
        executor.enqueue(action); executor.tick(2); assertEquals(0, game.mutations);
    }
    @Test void audioIsRestoredOnEmergencyStopAndDisconnect() {
        double[] volume = { .37 };
        var audio = new AudioSession(() -> volume[0], value -> volume[0] = value);
        Game game = new Game() {
            public void configureAudio(boolean mute, boolean restore) { audio.begin(mute, restore); }
            public void finishAudio() { audio.finish(); }
        };
        var executor = new ActionExecutor(game, (id, payload) -> {}, new Navigation());
        String fields = "{\"kind\":\"configure_execution\",\"speed_profile\":\"max\",\"max_action_batch\":16,\"mute_game_audio\":true,\"restore_audio_after_build\":true,\"prefer_local_movement\":true}";
        executor.enqueue(request("cfg", "action", fields)); executor.tick(1);
        assertEquals(0, volume[0]);
        executor.enqueue(request("stop", "control", "{\"kind\":\"emergency_stop\"}"));
        assertEquals(.37, volume[0]);
        executor.newSession(); executor.enqueue(request("cfg2", "action", fields)); executor.tick(2);
        assertEquals(0, volume[0]); executor.disconnect(); assertEquals(.37, volume[0]);
    }
}
