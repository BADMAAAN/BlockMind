package dev.blockmind.minecraft;

import com.google.gson.JsonObject;
import dev.blockmind.minecraft.GameAccess.Pos;
import dev.blockmind.minecraft.navigation.*;
import org.junit.jupiter.api.Test;
import java.util.HashMap;
import static org.junit.jupiter.api.Assertions.*;

class CreativeFlightTest {
    static class FlightGame extends ExecutorControlTest.Game {
        boolean creative = true, enabled, flying;
        int takeoffTicks, releases;
        String motion = "moving", unsafe = "";
        public boolean creative() { return creative; }
        public boolean flying() { return flying; }
        public boolean configureFlight(boolean value) { enabled = value && creative; return !value || creative; }
        public void tickFlight() { if (enabled) { takeoffTicks++; flying = true; } }
        public String unsafeFlight(Pos target) { return unsafe; }
        public String flightMove(Pos target) { tickFlight(); return enabled ? motion : "unavailable"; }
        public void releaseMovement() { releases++; }
    }
    @Test void flightIsOptInAndRejectsSurvival() {
        var game = new FlightGame(); var ground = new ExecutorControlTest.Navigation();
        var flight = new CreativeFlightNavigationProvider(game,ground);
        assertTrue(flight.start(new Pos(1,64,0),true).accepted());
        assertEquals(0,flight.performance().get("flightGoals").getAsInt());
        game.creative = false;
        assertFalse(flight.configureFlight(true));
        assertFalse(game.enabled);
    }
    @Test void takeoffIsBoundedAndCancellationReleasesKeys() {
        var game = new FlightGame(); var ground = new ExecutorControlTest.Navigation();
        var flight = new CreativeFlightNavigationProvider(game,ground);
        var safe = new SafeNavigationProvider(game,flight);
        safe.approveFlightRegion(new Pos(-5,60,-5),new Pos(5,75,5));
        assertTrue(safe.configureFlight(true));
        assertTrue(safe.start(new Pos(1,68,0),true).accepted());
        assertEquals(NavigationProvider.NavigationStatus.State.RUNNING,safe.poll().state());
        assertTrue(game.flying);
        // Simulate a vanilla jump-key ability toggle during braking: restore
        // the owned ability before the immediate grounded-drop guard runs.
        game.flying = false;
        assertEquals(NavigationProvider.NavigationStatus.State.RUNNING,safe.poll().state());
        assertTrue(game.flying);
        game.motion = "arrived";
        assertEquals(NavigationProvider.NavigationStatus.State.SUCCEEDED,safe.poll().state());
        assertEquals(1,flight.performance().get("flightGoals").getAsInt());
        safe.configureFlight(false); assertFalse(game.enabled); assertTrue(game.releases>0);
    }
    @Test void unsafeFlightAndImmediateCollisionDoNotContinueSteering() {
        var game = new FlightGame(); var ground = new ExecutorControlTest.Navigation();
        var flight = new CreativeFlightNavigationProvider(game,ground);
        var safe = new SafeNavigationProvider(game,flight);
        safe.approveFlightRegion(new Pos(-5,60,-5),new Pos(5,75,5));
        safe.configureFlight(true); game.unsafe = "unloaded";
        assertFalse(safe.start(new Pos(1,68,0),true).accepted());
        game.unsafe = ""; safe.start(new Pos(1,68,0),true);
        game.motion = "collision";
        assertEquals(NavigationProvider.NavigationStatus.State.FAILED,safe.poll().state());
        assertTrue(game.releases>0);
    }
    @Test void pauseStopAndDisconnectCannotKeepTakingOff() {
        var requests = new ExecutorControlTest();
        var game = new FlightGame(); var flight = new CreativeFlightNavigationProvider(game,new ExecutorControlTest.Navigation());
        var replies = new HashMap<String,JsonObject>();
        var executor = new ActionExecutor(game,replies::put,new SafeNavigationProvider(game,flight));
        String config = "{\"kind\":\"configure_execution\",\"speed_profile\":\"fast\",\"max_action_batch\":16,\"mute_game_audio\":false,\"restore_audio_after_build\":true,\"prefer_local_movement\":true,\"creative_flight\":true}";
        executor.enqueue(requests.request("cfg","action",config)); executor.tick(1);
        assertFalse(replies.containsKey("cfg"));
        executor.enqueue(requests.request("pause","control","{\"kind\":\"pause\"}"));
        executor.tick(2); assertEquals(0,game.takeoffTicks);
        executor.enqueue(requests.request("stop","control","{\"kind\":\"stop\"}"));
        executor.tick(3); assertFalse(game.enabled); assertEquals(0,game.takeoffTicks);
        executor.enqueue(requests.request("cfg2","action",config)); executor.tick(4);
        assertFalse(replies.get("cfg2").get("success").getAsBoolean());
        executor.newSession(); executor.enqueue(requests.request("cfg3","action",config)); executor.tick(5);
        executor.tick(6); assertTrue(replies.get("cfg3").get("success").getAsBoolean());
        int before = game.takeoffTicks; executor.disconnect(); executor.tick(7);
        assertFalse(game.enabled); assertEquals(before,game.takeoffTicks);
    }
    @Test void flightNavigationNeedsApprovedRegion() {
        var game = new FlightGame(); game.flying = true;
        var flight = new CreativeFlightNavigationProvider(game,new ExecutorControlTest.Navigation());
        var replies = new HashMap<String,JsonObject>(); var requests = new ExecutorControlTest();
        var executor = new ActionExecutor(game,replies::put,new SafeNavigationProvider(game,flight));
        executor.enqueue(requests.request("cfg","action","{\"kind\":\"configure_execution\",\"speed_profile\":\"fast\",\"max_action_batch\":16,\"mute_game_audio\":false,\"restore_audio_after_build\":true,\"prefer_local_movement\":true,\"creative_flight\":true}")); executor.tick(1);
        executor.enqueue(requests.request("nav","action","{\"kind\":\"navigate\",\"target\":{\"x\":0,\"y\":70,\"z\":0}}")); executor.tick(2);
        assertFalse(replies.get("nav").get("success").getAsBoolean());
        assertEquals(0,flight.performance().get("flightGoals").getAsInt());
    }
}
