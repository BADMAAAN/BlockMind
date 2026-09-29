package dev.blockmind.minecraft;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import org.slf4j.Logger;

import java.io.*;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.Queue;
import java.util.UUID;
import java.util.concurrent.ConcurrentLinkedQueue;

final class TcpBridge implements AutoCloseable {
    private static final Gson GSON = new Gson();
    private final Logger log;
    private final Queue<JsonObject> incoming = new ConcurrentLinkedQueue<>();
    private volatile boolean running = true;
    private volatile PrintWriter output;
    private Socket socket;

    TcpBridge(Logger log) {
        this.log = log;
        Thread thread = new Thread(this::connectionLoop, "blockmind-bridge");
        thread.setDaemon(true);
        thread.start();
    }

    JsonObject poll() { return incoming.poll(); }

    synchronized void send(String type, String id, JsonObject payload) {
        if (output == null) return;
        JsonObject envelope = new JsonObject();
        envelope.addProperty("protocol", "0.1.0");
        envelope.addProperty("id", id == null ? UUID.randomUUID().toString() : id);
        envelope.addProperty("type", type);
        envelope.add("payload", payload);
        output.println(GSON.toJson(envelope));
    }

    private void connectionLoop() {
        while (running) {
            try {
                socket = new Socket();
                socket.connect(new InetSocketAddress("127.0.0.1", 8765), 2000);
                output = new PrintWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8), true);
                JsonObject hello = new JsonObject();
                hello.addProperty("adapter", "blockmind-fabric");
                hello.addProperty("minecraft", "1.21.11");
                hello.addProperty("navigation", "baritone-optional");
                send("hello", null, hello);
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8))) {
                    String line;
                    while (running && (line = reader.readLine()) != null) incoming.add(GSON.fromJson(line, JsonObject.class));
                }
            } catch (Exception exception) {
                if (running) log.debug("Core unavailable; retrying local connection: {}", exception.getMessage());
            } finally {
                output = null;
                try { if (socket != null) socket.close(); } catch (IOException ignored) {}
            }
            try { Thread.sleep(2000); } catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
        }
    }

    @Override public void close() {
        running = false;
        try { if (socket != null) socket.close(); } catch (IOException ignored) {}
    }
}
