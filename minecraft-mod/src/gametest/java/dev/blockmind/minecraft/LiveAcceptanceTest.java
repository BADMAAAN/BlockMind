package dev.blockmind.minecraft;

import com.google.gson.JsonParser;
import net.fabricmc.fabric.api.client.gametest.v1.FabricClientGameTest;
import net.fabricmc.fabric.api.client.gametest.v1.context.ClientGameTestContext;
import java.nio.file.*;

/** Disposable flat-world fixture. The external Core must execute every build action over real TCP. */
public final class LiveAcceptanceTest implements FabricClientGameTest {
    @Override public void runTest(ClientGameTestContext context) {
        Path directory = Path.of(System.getProperty("blockmind.test.directory"));
        try (var world = context.worldBuilder().create()) {
            world.getServer().runCommand("gamemode creative @a");
            world.getServer().runCommand("tp @a 97 -60 100");
            world.getClientWorld().waitForChunksDownload();
            Files.createDirectories(directory);
            Files.writeString(directory.resolve("ready"), "disposable Creative world ready\n");
            context.waitFor(client -> Files.exists(directory.resolve("result.json")), 100_000);
            var result = JsonParser.parseString(Files.readString(directory.resolve("result.json"))).getAsJsonObject();
            if (!result.get("verified").getAsBoolean()) throw new AssertionError("Live acceptance failed: " + result);
            context.takeScreenshot("blockmind-live-acceptance");
        } catch (java.io.IOException exc) { throw new RuntimeException(exc); }
    }
}
