package dev.blockmind.minecraft;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import org.slf4j.Logger;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.*;

/** Bounded IO queues: the game thread never performs socket writes. */
final class TcpBridge implements AutoCloseable {
    static final String PROTOCOL = "0.1.0";
    private static final Gson GSON = new Gson();
    private final Logger log;
    private final BlockingQueue<JsonObject> incoming = new ArrayBlockingQueue<>(128);
    private final BlockingQueue<String> outgoing = new ArrayBlockingQueue<>(128);
    private volatile boolean running = true;
    private volatile boolean connected;
    private volatile int generation;
    private volatile Socket socket;
    private volatile JsonObject metadata;

    TcpBridge(Logger log, JsonObject metadata) {
        this.log = log; this.metadata = metadata;
        Thread thread = new Thread(this::connectionLoop, "blockmind-bridge");
        thread.setDaemon(true); thread.start();
    }
    JsonObject poll() { return incoming.poll(); }
    int generation() { return generation; }
    boolean connected() { return connected; }
    void metadata(JsonObject value) { metadata = value; if (connected) send("hello", null, value); }

    void send(String type, String id, JsonObject payload) {
        if (!connected) return;
        JsonObject message = new JsonObject();
        message.addProperty("protocol", PROTOCOL); message.addProperty("type", type);
        message.addProperty("id", id == null ? UUID.randomUUID().toString() : id); message.add("payload", payload);
        String line = GSON.toJson(message);
        if (line.getBytes(StandardCharsets.UTF_8).length > 1_048_576 || !outgoing.offer(line)) disconnect();
    }

    private void connectionLoop() {
        while (running) {
            Thread sender = null;
            try {
                socket = new Socket();
                socket.connect(new InetSocketAddress("127.0.0.1", Integer.getInteger("blockmind.port", 8765)), 2000);
                socket.setSoTimeout(15000);
                BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8));
                BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
                connected = true; generation++;
                send("hello", null, metadata);
                String hello = outgoing.poll(2, TimeUnit.SECONDS);
                writer.write(hello); writer.newLine(); writer.flush();
                JsonObject ack = read(reader);
                if (!ack.get("type").getAsString().equals("hello_ack") || !ack.getAsJsonObject("payload").get("accepted").getAsBoolean())
                    throw new IOException("Core rejected handshake");
                socket.setSoTimeout(0);
                sender = new Thread(() -> {
                    try {
                        while (connected && running) {
                            String line = outgoing.poll(1, TimeUnit.SECONDS);
                            if (line != null) { writer.write(line); writer.newLine(); writer.flush(); }
                        }
                    } catch (Exception exc) { disconnect(); }
                }, "blockmind-send");
                sender.setDaemon(true); sender.start();
                log.info("[CONNECTION] mode=LIVE handshake accepted");
                while (running && connected) {
                    JsonObject value = read(reader);
                    String type = value.get("type").getAsString();
                    if (type.equals("hello_ack")) continue;
                    if (type.equals("error")) throw new IOException(value.getAsJsonObject("payload").toString());
                    if (!type.equals("action") && !type.equals("control")) throw new IOException("unexpected envelope type");
                    if (type.equals("action") && value.getAsJsonObject("payload").has("kind") && value.getAsJsonObject("payload").get("kind").getAsString().equals("ping")) {
                        JsonObject response=new JsonObject(); response.addProperty("success",true);
                        send("action_result",value.get("id").getAsString(),response); continue;
                    }
                    value.addProperty("_generation", generation);
                    if (!incoming.offer(value)) throw new IOException("request queue full");
                }
            } catch (Exception exc) {
                if (running) log.debug("Core connection closed: {}", exc.getMessage());
            } finally {
                disconnect(); generation++;
                incoming.clear(); outgoing.clear();
                if (sender != null) { sender.interrupt(); try { sender.join(1000); } catch (InterruptedException ignored) { } }
            }
            try { Thread.sleep(2000); } catch (InterruptedException exc) { Thread.currentThread().interrupt(); return; }
        }
    }

    private static JsonObject read(BufferedReader reader) throws IOException {
        StringBuilder line = new StringBuilder();
        int ch;
        while ((ch = reader.read()) != -1 && ch != '\n') {
            if (line.length() >= 1_048_576) throw new IOException("message too large");
            line.append((char) ch);
        }
        if (ch == -1) throw new EOFException("disconnected");
        if (line.toString().getBytes(StandardCharsets.UTF_8).length > 1_048_576) throw new IOException("message too large");
        try {
            JsonObject value = GSON.fromJson(line.toString(), JsonObject.class);
            if (!PROTOCOL.equals(value.get("protocol").getAsString()) || !value.get("payload").isJsonObject()
                || value.get("id").getAsString().isEmpty() || value.get("id").getAsString().length() > 128)
                throw new IOException("invalid protocol envelope");
            return value;
        } catch (RuntimeException exc) { throw new IOException("malformed message", exc); }
    }

    private void disconnect() {
        connected = false;
        try { if (socket != null) socket.close(); } catch (IOException ignored) { }
    }
    @Override public void close() { running = false; disconnect(); }
}
