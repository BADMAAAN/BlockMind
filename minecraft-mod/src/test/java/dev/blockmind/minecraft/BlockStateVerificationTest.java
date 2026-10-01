package dev.blockmind.minecraft;

import com.google.gson.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class BlockStateVerificationTest {
    private JsonObject state(String block, String properties) {
        JsonObject value = new JsonObject(); value.addProperty("loaded", true); value.addProperty("block", block);
        value.add("properties", JsonParser.parseString(properties)); return value;
    }
    @Test void verifiesDirectionAndStateRatherThanOnlyTheBlockName() {
        for (String block : new String[]{"oak_stairs", "oak_door", "oak_log", "oak_slab", "oak_trapdoor", "lever", "repeater"}) {
            JsonObject expected = state("minecraft:" + block, "{\"facing\":\"north\"}");
            assertFalse(ActionExecutor.matches(state("minecraft:" + block, "{\"facing\":\"south\"}"), expected));
            assertTrue(ActionExecutor.matches(state("minecraft:" + block, "{\"facing\":\"north\",\"extra\":\"value\"}"), expected));
        }
    }
    @Test void unloadedBlockCanNeverSatisfyAnOperation() {
        JsonObject actual = state("minecraft:air", "{}"); actual.addProperty("loaded", false);
        assertFalse(ActionExecutor.matches(actual, state("minecraft:air", "{}")));
    }
}
