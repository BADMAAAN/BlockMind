package dev.blockmind.minecraft;

import com.google.gson.*;
import dev.blockmind.minecraft.GameAccess.Pos;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class GuardedBreakTest {
    static class Game extends ExecutorControlTest.Game {
        String block = "minecraft:cobblestone";
        boolean loaded = true;
        String axis = "y";
        double[] position = {0.5, 64, 0.5};
        String danger = "";
        int releases;
        @Override public double[] precisePosition() { return position; }
        @Override public String immediateDanger() { return danger; }
        @Override public void releaseMovement() { releases++; }
        @Override public JsonObject inspect(Pos p) {
            JsonObject result = super.inspect(p);
            result.addProperty("loaded", loaded);
            result.addProperty("block", block);
            result.getAsJsonObject("properties").addProperty("axis", axis);
            return result;
        }
    }
    private JsonObject request(String id, String kind, String fields) {
        JsonObject result = new JsonObject(); result.addProperty("id", id); result.addProperty("type", "action");
        result.add("payload", JsonParser.parseString("{\"kind\":\"" + kind + "\"" + fields + "}"));
        return result;
    }
    private ActionExecutor approved(Game game, Map<String, JsonObject> replies) {
        ActionExecutor executor = new ActionExecutor(game, replies::put, new ExecutorControlTest.Navigation());
        String region = "{\"minimum\":{\"x\":-2,\"y\":60,\"z\":-2},\"maximum\":{\"x\":2,\"y\":70,\"z\":2}}";
        executor.enqueue(request("area", "approve_region", ",\"region\":" + region + ",\"temporaryRegion\":" + region + ",\"dimension\":\"minecraft:overworld\""));
        executor.tick(1);
        return executor;
    }
    private JsonObject breaking(String expected) {
        return request("break", "break_block", ",\"position\":{\"x\":1,\"y\":64,\"z\":0},\"temporary\":true" +
            (expected == null ? "" : ",\"expected\":" + expected));
    }
    private static final String GUARD = "{\"block\":\"minecraft:cobblestone\",\"properties\":{}}";

    @Test void missingAndMismatchedPreconditionsNeverBreak() {
        for (String guard : new String[]{null, "{\"block\":\"minecraft:diamond_block\"}"}) {
            Game game = new Game(); Map<String, JsonObject> replies = new HashMap<>();
            ActionExecutor executor = approved(game, replies);
            executor.enqueue(breaking(guard)); executor.tick(2);
            assertEquals(0, game.mutations); assertFalse(replies.get("break").get("success").getAsBoolean());
        }
    }
    @Test void changedTargetBetweenBreakingTicksAbortsWithoutFurtherMutation() {
        Game game = new Game(); Map<String, JsonObject> replies = new HashMap<>();
        ActionExecutor executor = approved(game, replies);
        executor.enqueue(breaking(GUARD)); executor.tick(2); assertEquals(1, game.mutations);
        game.block = "minecraft:diamond_block"; executor.tick(3); executor.tick(4);
        assertEquals(1, game.mutations); assertFalse(replies.get("break").get("success").getAsBoolean());
        assertTrue(game.releases > 0, "cancel breaking progress when the target changes");
        executor.enqueue(breaking(GUARD)); executor.tick(5); assertEquals(1, game.mutations, "duplicate id is not replayed");
    }
    @Test void unloadedTargetAbortsAnActiveBreak() {
        Game game = new Game(); Map<String, JsonObject> replies = new HashMap<>();
        ActionExecutor executor = approved(game, replies);
        executor.enqueue(breaking(GUARD)); executor.tick(2);
        game.loaded = false; executor.tick(3);
        assertEquals(1, game.mutations); assertFalse(replies.get("break").get("success").getAsBoolean());
    }
    @Test void propertyChangeAlsoAbortsAnActiveBreak() {
        Game game = new Game(); Map<String, JsonObject> replies = new HashMap<>();
        ActionExecutor executor = approved(game, replies);
        executor.enqueue(breaking("{\"block\":\"minecraft:cobblestone\",\"properties\":{\"axis\":\"y\"}}")); executor.tick(2);
        game.axis = "x"; executor.tick(3);
        assertEquals(1, game.mutations); assertFalse(replies.get("break").get("success").getAsBoolean());
    }
    @Test void allAirVariantsCompleteWithoutAdditionalBreaks() {
        for (String air : new String[]{"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}) {
            Game game = new Game(); Map<String, JsonObject> replies = new HashMap<>();
            ActionExecutor executor = approved(game, replies);
            executor.enqueue(breaking(GUARD)); executor.tick(2);
            game.block = air; executor.tick(3);
            assertEquals(1, game.mutations); assertTrue(replies.get("break").get("success").getAsBoolean());
        }
    }
    @Test void alreadyAbsentOwnedBlockNeedsNoMutation() {
        Game game = new Game(); game.block = "minecraft:air";
        Map<String, JsonObject> replies = new HashMap<>(); ActionExecutor executor = approved(game, replies);
        executor.enqueue(breaking(GUARD)); executor.tick(2);
        assertEquals(0, game.mutations); assertTrue(replies.get("break").get("success").getAsBoolean());
    }
    @Test void unchangedTargetContinuesUntilObservedAir() {
        Game game = new Game(); Map<String, JsonObject> replies = new HashMap<>();
        ActionExecutor executor = approved(game, replies);
        executor.enqueue(breaking(GUARD)); executor.tick(2); executor.tick(3);
        assertEquals(2, game.mutations); assertFalse(replies.containsKey("break"));
        game.block = "minecraft:air"; executor.tick(4);
        assertEquals(2, game.mutations); assertTrue(replies.get("break").get("success").getAsBoolean());
    }
    @Test void emergencyStopInterruptsGuardedBreakBeforeAnotherTick() {
        Game game = new Game(); Map<String, JsonObject> replies = new HashMap<>();
        ActionExecutor executor = approved(game, replies);
        executor.enqueue(breaking(GUARD)); executor.tick(2);
        JsonObject stop = request("stop", "emergency_stop", ""); stop.addProperty("type", "control");
        executor.enqueue(stop); executor.tick(3);
        assertEquals(1, game.mutations); assertFalse(replies.get("break").get("success").getAsBoolean());
        assertTrue(replies.get("stop").get("success").getAsBoolean());
    }
    @Test void steppingOntoTargetWhileBreakingPreservesOwnFooting() {
        Game game = new Game(); Map<String, JsonObject> replies = new HashMap<>();
        ActionExecutor executor = approved(game, replies);
        executor.enqueue(breaking(GUARD)); executor.tick(2);
        game.position = new double[]{1.5, 65, .5}; executor.tick(3);
        assertEquals(1, game.mutations); assertFalse(replies.get("break").get("success").getAsBoolean());
        assertTrue(game.releases > 0);
    }
    @Test void edgeOverlapProtectsSupportOutsideIntegerFeetCell() {
        Game game = new Game(); game.position = new double[]{2.1, 65, .5};
        Map<String, JsonObject> replies = new HashMap<>(); ActionExecutor executor = approved(game, replies);
        executor.enqueue(breaking(GUARD)); executor.tick(2);
        assertEquals(0, game.mutations); assertFalse(replies.get("break").get("success").getAsBoolean());
    }
    @Test void newImmediateDangerCancelsActiveBreaking() {
        Game game = new Game(); Map<String, JsonObject> replies = new HashMap<>();
        ActionExecutor executor = approved(game, replies);
        executor.enqueue(breaking(GUARD)); executor.tick(2);
        game.danger = "hazard: lava"; executor.tick(3);
        assertEquals(1, game.mutations); assertFalse(replies.get("break").get("success").getAsBoolean());
        assertTrue(game.releases > 0);
    }
}
