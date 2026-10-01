package dev.blockmind.minecraft;

import com.google.gson.JsonObject;

/** Mapping-independent game boundary. Every method runs on the client thread. */
public interface GameAccess {
    record Pos(int x, int y, int z) {
        public Pos add(int dx, int dy, int dz) { return new Pos(x + dx, y + dy, z + dz); }
        public JsonObject json() {
            JsonObject value = new JsonObject();
            value.addProperty("x", x); value.addProperty("y", y); value.addProperty("z", z);
            return value;
        }
        public static Pos parse(JsonObject value) {
            return new Pos(value.get("x").getAsInt(), value.get("y").getAsInt(), value.get("z").getAsInt());
        }
    }
    boolean ready();
    Pos playerPosition();
    String dimension();
    JsonObject observe(int radius, long tick);
    JsonObject inspect(Pos target);
    String place(Pos target, String block, JsonObject properties);
    String breakBlock(Pos target);
    String interact(Pos target);
    void look(float yaw, float pitch);
    boolean select(int slot);
    boolean provision(String item);
    void releaseMovement();
    String unsafe(Pos feet);
    String immediateDanger();
    default boolean creative() { return false; }
    default void configureAudio(boolean mute, boolean restore) { }
    default void finishAudio() { }
    default JsonObject performance() { return new JsonObject(); }
    default String localMove(Pos target) { return "unsupported"; }
}
