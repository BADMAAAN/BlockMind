package dev.blockmind.minecraft;
import com.google.gson.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class BatchControlTest {
    private JsonObject request(String id, String kind, String fields) {
        JsonObject v=new JsonObject(); v.addProperty("id",id); v.addProperty("type",kind.equals("emergency_stop")?"control":"action");
        v.add("payload",JsonParser.parseString("{\"kind\":\""+kind+"\""+fields+"}")); return v;
    }
    @Test void boundedBatchStopsBetweenTicksAndCannotEscapeRegion() {
        var game=new ExecutorControlTest.Game() { public boolean creative() { return true; } };
        var replies=new HashMap<String,JsonObject>(); var executor=new ActionExecutor(game,replies::put,new ExecutorControlTest.Navigation());
        executor.enqueue(request("cfg","configure_execution",",\"speed_profile\":\"fast\",\"max_action_batch\":16,\"mute_game_audio\":true,\"restore_audio_after_build\":true,\"prefer_local_movement\":true")); executor.tick(1);
        executor.enqueue(request("area","approve_region",",\"region\":{\"minimum\":{\"x\":0,\"y\":64,\"z\":0},\"maximum\":{\"x\":9,\"y\":65,\"z\":9}},\"temporaryRegion\":{\"minimum\":{\"x\":0,\"y\":64,\"z\":0},\"maximum\":{\"x\":9,\"y\":65,\"z\":9}},\"dimension\":\"minecraft:overworld\"")); executor.tick(2);
        JsonArray ops=new JsonArray();
        for (int i=0;i<8;i++) { JsonObject op=new JsonObject(); op.addProperty("id","op"+i); op.addProperty("block","minecraft:stone"); op.add("properties",new JsonObject()); op.add("position",new GameAccess.Pos(i==0?100:i,64,1).json()); ops.add(op); }
        executor.enqueue(request("batch","action_batch",",\"operations\":"+ops)); executor.tick(3);
        assertEquals(1,game.mutations,"first out-of-area item rejected; only one other item this tick");
        executor.enqueue(request("stop","emergency_stop","")); executor.tick(4); executor.tick(5);
        assertEquals(1,game.mutations); assertFalse(replies.get("batch").get("success").getAsBoolean());
        assertTrue(replies.get("stop").get("success").getAsBoolean());
    }
    @Test void sensitiveBatchAndOversizedBatchAreRejected() {
        var game=new ExecutorControlTest.Game() { public boolean creative() { return true; } };
        var replies=new HashMap<String,JsonObject>(); var executor=new ActionExecutor(game,replies::put,new ExecutorControlTest.Navigation());
        executor.enqueue(request("bad","action_batch",",\"operations\":[{\"id\":\"x\",\"block\":\"minecraft:oak_stairs\",\"properties\":{},\"position\":{\"x\":1,\"y\":64,\"z\":1}}]")); executor.tick(1);
        assertFalse(replies.get("bad").get("success").getAsBoolean()); assertEquals(0,game.mutations);
        JsonArray operations = new JsonArray();
        for (int i=0;i<17;i++) operations.add(JsonParser.parseString("{\"id\":\"op"+i+"\",\"block\":\"minecraft:stone\",\"position\":{\"x\":1,\"y\":64,\"z\":1}}"));
        executor.enqueue(request("large","action_batch",",\"operations\":"+operations)); executor.tick(2);
        assertFalse(replies.get("large").get("success").getAsBoolean()); assertEquals(0,game.mutations);
    }
}
