package dev.blockmind.minecraft;

import com.google.gson.*;
import dev.blockmind.minecraft.GameAccess.Pos;
import dev.blockmind.minecraft.navigation.NavigationProvider;
import java.util.*;
import java.util.function.BiConsumer;

/** All queue consumption, Minecraft access, controls and verification occur on one game thread. */
final class ActionExecutor {
    private final GameAccess game;
    private final BiConsumer<String, JsonObject> reply;
    private final NavigationProvider navigation;
    private final Queue<JsonObject> queue = new ArrayDeque<>();
    private final Map<String, JsonObject> completed = new LinkedHashMap<>();
    private Pending pending;
    private boolean paused;
    private boolean stopped;
    private Region approved;
    private Region temporary;
    private String dimension;
    private boolean injectedFailure;
    private Batch batch;
    private int perTick = 1;
    private int maxBatch = 16;
    private String profile = "fast";
    private long placementNanos;
    private long inspectionNanos;
    private long issued;
    private static final class Batch {
        String id; JsonArray operations; JsonArray results = new JsonArray(); int index;
        Batch(String id, JsonArray operations) { this.id = id; this.operations = operations; }
    }
    private record Pending(String id, String kind, Pos target, JsonObject expected, long deadline) {}
    private record Region(Pos min, Pos max) {
        Region {
            if (min.x() > max.x() || min.y() > max.y() || min.z() > max.z()) throw new IllegalArgumentException("inverted region");
            if ((long) max.x() - min.x() > 1000 || (long) max.y() - min.y() > 1000 || (long) max.z() - min.z() > 1000)
                throw new IllegalArgumentException("region extent too large");
        }
        static Region parse(JsonObject v) { return new Region(Pos.parse(v.getAsJsonObject("minimum")), Pos.parse(v.getAsJsonObject("maximum"))); }
        boolean contains(Pos p) { return p.x() >= min.x() && p.x() <= max.x() && p.y() >= min.y() && p.y() <= max.y()
            && p.z() >= min.z() && p.z() <= max.z(); }
        long size() { return ((long) max.x() - min.x() + 1) * ((long) max.y() - min.y() + 1) * ((long) max.z() - min.z() + 1); }
    }
    ActionExecutor(GameAccess game, TcpBridge bridge, NavigationProvider navigation) {
        this(game, (id, payload) -> bridge.send("action_result", id, payload), navigation);
    }
    ActionExecutor(GameAccess game, BiConsumer<String, JsonObject> reply, NavigationProvider navigation) {
        this.game = game; this.reply = reply; this.navigation = navigation;
    }

    void enqueue(JsonObject value) {
        String id = value.get("id").getAsString();
        if (completed.containsKey(id)) { reply.accept(id, completed.get(id)); return; }
        if ((pending != null && pending.id.equals(id)) || (batch != null && batch.id.equals(id)) || queue.stream().anyMatch(v -> v.get("id").getAsString().equals(id))) return;
        try {
            String kind = value.getAsJsonObject("payload").get("kind").getAsString();
            if (value.get("type").getAsString().equals("control") || kind.equals("cancel_navigation")) {
                control(id, kind); return;
            }
            if (queue.size() >= 64) { result(id, false, "action queue full", null); return; }
            queue.add(value);
        } catch (RuntimeException exc) { result(id, false, "invalid request: " + exc.getMessage(), null); }
    }

    void tick(long tick) {
        if (!game.ready()) { abort("world unavailable"); game.finishAudio(); approved = null; return; }
        if (dimension != null && !dimension.equals(game.dimension())) { abort("dimension changed"); game.finishAudio(); stopped = true; approved = null; }
        if (pending != null) poll(tick);
        if (batch != null && !paused && !stopped) { advanceBatch(); return; }
        if (pending != null || paused) return;
        JsonObject value = queue.poll();
        if (value == null) return;
        String id = value.get("id").getAsString();
        try { execute(id, value.getAsJsonObject("payload"), tick); }
        catch (RuntimeException exc) { result(id, false, "invalid action: " + exc.getMessage(), null); }
    }

    private void execute(String id, JsonObject action, long tick) {
        String kind = action.get("kind").getAsString();
        if (kind.equals("performance")) {
            JsonObject payload = base(true, "metrics"); payload.add("gameTimings", game.performance());
            payload.add("navigationTimings", navigation.performance());
            payload.addProperty("placementSeconds", placementNanos / 1e9); payload.addProperty("inspectionSeconds", inspectionNanos / 1e9);
            payload.addProperty("issuedPlacements", issued); send(id, payload); return;
        }
        if (kind.equals("configure_execution")) {
            profile = action.get("speed_profile").getAsString();
            perTick = switch(profile) { case "safe", "normal" -> 1; case "fast" -> 2; case "max" -> 4; default -> throw new IllegalArgumentException("unknown speed profile"); };
            maxBatch = Math.max(1, Math.min(32, action.get("max_action_batch").getAsInt()));
            game.configureAudio(action.get("mute_game_audio").getAsBoolean(), action.get("restore_audio_after_build").getAsBoolean());
            navigation.configureLocal(action.get("prefer_local_movement").getAsBoolean());
            result(id, true, "execution configured", null); return;
        }
        if (kind.equals("finish_project")) { game.finishAudio(); result(id, true, "audio policy applied", null); return; }
        if (kind.equals("validate_batch")) {
            JsonArray operations = action.getAsJsonArray("operations");
            if (operations.size() > 256) throw new IllegalArgumentException("validation batch too large");
            JsonArray mismatches = new JsonArray(); int correct = 0, missing = 0, incorrect = 0;
            long start = System.nanoTime();
            for (JsonElement entry : operations) {
                JsonObject op = entry.getAsJsonObject(); JsonObject actual = game.inspect(Pos.parse(op.getAsJsonObject("position")));
                if (matches(actual, op)) correct++;
                else { JsonObject mismatch = new JsonObject(); mismatch.addProperty("id", op.get("id").getAsString()); mismatch.add("observed", actual); mismatches.add(mismatch);
                    if (actual.has("block") && actual.get("block").getAsString().equals("minecraft:air")) missing++; else incorrect++;
                }
            }
            inspectionNanos += System.nanoTime() - start;
            JsonObject payload = base(true, "component checkpoint"); payload.addProperty("expected", operations.size());
            payload.addProperty("correct", correct); payload.addProperty("missing", missing); payload.addProperty("incorrect", incorrect);
            payload.add("mismatches", mismatches); send(id, payload); return;
        }
        if (kind.equals("approve_region")) {
            if (pending != null || batch != null || !queue.isEmpty()) { result(id, false, "executor busy", null); return; }
            if (!game.dimension().equals(action.get("dimension").getAsString())) { result(id, false, "dimension mismatch", null); return; }
            approved = Region.parse(action.getAsJsonObject("region"));
            temporary = Region.parse(action.getAsJsonObject("temporaryRegion"));
            if (approved.size() <= 0 || approved.size() > 1_000_000 || temporary.size() <= 0 || temporary.size() > 1_000_000)
                throw new IllegalArgumentException("invalid region size");
            dimension = game.dimension(); stopped = false; paused = false;
            result(id, true, "region approved", null); return;
        }
        if (kind.equals("observe")) {
            JsonObject payload = base(true, ""); payload.add("observation", game.observe(6, tick)); send(id, payload); return;
        }
        if (kind.equals("observe_block")) { result(id, true, "observed", Pos.parse(action.getAsJsonObject("position"))); return; }
        if (kind.equals("observe_positions") || kind.equals("observe_region")) {
            JsonArray blocks = new JsonArray();
            if (kind.equals("observe_positions")) {
                JsonArray points = action.getAsJsonArray("positions");
                if (points.size() > 4096) throw new IllegalArgumentException("too many positions");
                for (JsonElement point : points) blocks.add(game.inspect(Pos.parse(point.getAsJsonObject())));
            } else {
                Region area = Region.parse(action.getAsJsonObject("region"));
                if (area.size() <= 0 || area.size() > 4096) throw new IllegalArgumentException("scan must have 1..4096 cells");
                for (int y = area.min.y(); y <= area.max.y(); y++) for (int z = area.min.z(); z <= area.max.z(); z++)
                    for (int x = area.min.x(); x <= area.max.x(); x++) blocks.add(game.inspect(new Pos(x, y, z)));
            }
            JsonObject payload = base(true, "observed"); payload.add("blocks", blocks); send(id, payload); return;
        }
        if (stopped) { result(id, false, "executor stopped; approve a new/reconciled project", null); return; }
        switch (kind) {
            case "action_batch" -> {
                JsonArray operations = action.getAsJsonArray("operations");
                if (!game.creative() || profile.equals("safe")) { result(id, false, "batches require Creative non-SAFE mode", null); return; }
                if (operations.size() < 1 || operations.size() > maxBatch) throw new IllegalArgumentException("invalid batch size");
                for (JsonElement entry : operations) if (!simple(entry.getAsJsonObject())) throw new IllegalArgumentException("batch contains sensitive operation");
                batch = new Batch(id, operations); advanceBatch();
            }
            case "navigate" -> {
                Pos target = Pos.parse(action.getAsJsonObject("target"));
                NavigationProvider.StartResult started = navigation.start(target, true);
                if (!started.accepted()) result(id, false, started.reason(), target);
                else pending = new Pending(id, kind, started.target(), null, tick + 2400);
            }
            case "look" -> { game.look(action.get("yaw").getAsFloat(), action.get("pitch").getAsFloat()); result(id, true, "looked", null); }
            case "select_hotbar" -> result(id, game.select(action.get("slot").getAsInt()), "inventory selection", null);
            case "provision" -> result(id, game.provision(action.get("item").getAsString()), "Creative provisioning", null);
            case "place_block", "break_block", "interact" -> {
                Pos target = Pos.parse(action.getAsJsonObject("position"));
                boolean temp = action.has("temporary") && action.get("temporary").getAsBoolean();
                Region area = temp ? temporary : approved;
                if (area == null || !area.contains(target)) { result(id, false, "action outside approved region", target); return; }
                JsonObject expected = new JsonObject();
                String reason;
                if (kind.equals("place_block")) {
                    if (Boolean.getBoolean("blockmind.test.failFirstPlacement") && !injectedFailure) {
                        injectedFailure = true; result(id, false, "controlled development placement failure", target); return;
                    }
                    expected.addProperty("block", action.get("block").getAsString());
                    expected.add("properties", action.has("properties") ? action.getAsJsonObject("properties") : new JsonObject());
                    if (matches(game.inspect(target), expected)) { result(id, true, "already satisfied", target); return; }
                    long start = System.nanoTime();
                    reason = game.place(target, action.get("block").getAsString(), expected.getAsJsonObject("properties"));
                    placementNanos += System.nanoTime() - start;
                    if (reason.isEmpty()) issued++;
                } else if (kind.equals("break_block")) {
                    expected.addProperty("block", "minecraft:air"); expected.add("properties", new JsonObject());
                    reason = game.breakBlock(target);
                } else {
                    if (!action.has("expected")) { result(id, false, "interact requires expected block state for verification", target); return; }
                    expected = action.getAsJsonObject("expected"); reason = game.interact(target);
                }
                if (!reason.isEmpty()) result(id, false, reason, target);
                else pending = new Pending(id, kind, target, expected, tick + 80);
            }
            default -> result(id, false, "unsupported action: " + kind, null);
        }
    }

    private void poll(long tick) {
        Pending work = pending;
        if (tick >= work.deadline) { abort("action timed out; observed state did not match"); return; }
        if (work.kind.equals("navigate")) {
            NavigationProvider.NavigationStatus status = navigation.poll();
            if (status.state() != NavigationProvider.NavigationStatus.State.RUNNING) {
                pending = null;
                result(work.id, status.state() == NavigationProvider.NavigationStatus.State.SUCCEEDED, status.reason(), null);
            }
        } else if (matches(game.inspect(work.target), work.expected)) {
            pending = null; result(work.id, true, "observed and verified", work.target);
        } else if (work.kind.equals("break_block")) {
            String reason = game.breakBlock(work.target);
            if (!reason.isEmpty()) { pending = null; result(work.id, false, reason, work.target); }
        }
    }

    static boolean matches(JsonObject actual, JsonObject expected) {
        if (!actual.has("loaded") || !actual.get("loaded").getAsBoolean() || !actual.get("block").equals(expected.get("block"))) return false;
        JsonObject properties = expected.getAsJsonObject("properties");
        if (properties == null) return true;
        for (var entry : properties.entrySet()) if (!entry.getValue().equals(actual.getAsJsonObject("properties").get(entry.getKey()))) return false;
        return true;
    }

    private void control(String id, String kind) {
        switch (kind) {
            case "pause" -> { paused = true; abort("paused"); }
            case "resume" -> {
                if (stopped) { result(id, false, "stop is terminal; approve a new/reconciled project", null); return; }
                paused = false;
            }
            case "stop", "emergency_stop" -> { stopped = true; paused = false; abort(kind); game.finishAudio(); }
            case "cancel_navigation" -> abort("navigation cancelled");
            default -> { result(id, false, "unknown control: " + kind, null); return; }
        }
        result(id, true, kind, null);
    }

    private void abort(String reason) {
        navigation.cancel(); game.releaseMovement();
        if (batch != null) { Batch work = batch; batch = null; JsonObject payload = base(false, reason); payload.add("results", work.results); send(work.id, payload); }
        if (pending != null) { Pending work = pending; pending = null; result(work.id, false, reason, work.target); }
        JsonObject value;
        while ((value = queue.poll()) != null) result(value.get("id").getAsString(), false, reason, null);
    }
    void disconnect() { abort("connection lost"); game.finishAudio(); stopped = true; approved = null; temporary = null; completed.clear(); }
    void newSession() { disconnect(); stopped = false; paused = false; }

    private JsonObject base(boolean success, String reason) {
        JsonObject value = new JsonObject(); value.addProperty("success", success); value.addProperty("reason", reason);
        value.add("position", game.playerPosition().json()); return value;
    }
    private void result(String id, boolean success, String reason, Pos target) {
        JsonObject payload = base(success, reason);
        if (target != null && game.ready()) {
            JsonObject block = game.inspect(target); payload.add("observed", block);
            payload.addProperty("loaded", block.get("loaded").getAsBoolean());
            if (block.has("block")) { payload.add("observedBlock", block.get("block")); payload.add("properties", block.get("properties")); }
            if (!block.get("loaded").getAsBoolean()) { payload.addProperty("success", false); payload.addProperty("reason", "target chunk unloaded"); }
        }
        send(id, payload);
    }
    private void send(String id, JsonObject payload) {
        completed.put(id, payload);
        if (completed.size() > 256) completed.remove(completed.keySet().iterator().next());
        reply.accept(id, payload);
    }

    private static boolean simple(JsonObject op) {
        if (op.has("properties") && op.getAsJsonObject("properties").size() > 0) return false;
        if (op.has("temporary") && op.get("temporary").getAsBoolean()) return false;
        String block = op.get("block").getAsString().replace("minecraft:", "");
        return Set.of("stone", "cobblestone", "smooth_quartz", "quartz_block", "bricks", "dirt", "glass").contains(block)
            || block.endsWith("_planks") || block.endsWith("_concrete") || block.endsWith("_wool");
    }
    private void advanceBatch() {
        Batch work = batch;
        for (int count = 0; count < perTick && work.index < work.operations.size(); count++) {
            JsonObject op = work.operations.get(work.index++).getAsJsonObject();
            Pos point = Pos.parse(op.getAsJsonObject("position"));
            JsonObject outcome = new JsonObject(); outcome.add("id", op.get("id"));
            String reason = approved == null || !approved.contains(point) ? "outside approved region" : "";
            if (reason.isEmpty() && Boolean.getBoolean("blockmind.test.failFirstPlacement") && !injectedFailure) {
                injectedFailure = true; reason = "controlled development placement failure";
            }
            if (reason.isEmpty()) {
                long start = System.nanoTime();
                if (!matches(game.inspect(point), op)) reason = game.place(point, op.get("block").getAsString(), new JsonObject());
                placementNanos += System.nanoTime() - start;
            }
            outcome.addProperty("issued", reason.isEmpty()); outcome.addProperty("reason", reason);
            if (reason.isEmpty()) issued++;
            work.results.add(outcome);
        }
        if (work.index == work.operations.size()) {
            batch = null; JsonObject payload = base(true, "issued; component validation required"); payload.add("results", work.results); send(work.id, payload);
        }
    }
}
