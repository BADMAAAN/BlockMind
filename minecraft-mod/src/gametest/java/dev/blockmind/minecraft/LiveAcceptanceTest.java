package dev.blockmind.minecraft;

import com.google.gson.JsonParser;
import net.fabricmc.fabric.api.client.gametest.v1.FabricClientGameTest;
import net.fabricmc.fabric.api.client.gametest.v1.context.ClientGameTestContext;
import java.nio.file.*;
import dev.blockmind.minecraft.navigation.*;

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
            if (!result.get("verified").getAsBoolean()) {
                Files.copy(context.takeScreenshot("blockmind-live-failed-diagnostic"),directory.resolve("failed-view.png"));
                StringBuilder threads = new StringBuilder();
                Thread.getAllStackTraces().forEach((thread, stack) -> {
                    threads.append(thread.getName()).append(" ").append(thread.getState()).append("\n");
                    for (var frame : stack) threads.append("  ").append(frame).append("\n");
                });
                Files.writeString(directory.resolve("failure-threads.txt"), threads.toString());
                throw new AssertionError("Live acceptance failed: " + result);
            }
            Files.copy(context.takeScreenshot("blockmind-live-acceptance"),directory.resolve("acceptance-view.png"));
            if (result.has("benchmark") && result.get("benchmark").getAsString().equals("full authorized Enderman reconstruction"))
                captureReferenceViews(context,directory,result);
        } catch (java.io.IOException exc) { throw new RuntimeException(exc); }
        finally {
            // Test-only lifecycle diagnostic after world closure. Both disposal
            // orderings have reproduced the OpenAL fast-fail; this is NOT a fix.
            // Audio remains enabled and native libraries are not replaced.
            context.runOnClient(client -> client.getSoundManager().close());
        }
    }

    /** Camera-only inspection AFTER Core validation; ordinary flight keys, no teleport or block writes. */
    private void captureReferenceViews(ClientGameTestContext context, Path directory, com.google.gson.JsonObject result) throws java.io.IOException {
        var project=JsonParser.parseString(Files.readString(Path.of(result.get("project_file").getAsString()))).getAsJsonObject();
        var origin=GameAccess.Pos.parse(project.getAsJsonObject("design").getAsJsonObject("origin"));
        var game=new YarnGameAccess();
        var camera=new SafeNavigationProvider(game,new CreativeFlightNavigationProvider(game,new BaritoneNavigationProvider(game)));
        var views=new com.google.gson.JsonArray();
        int previousFov=context.computeOnClient(client -> client.options.getFov().getValue());
        boolean previousHud=context.computeOnClient(client -> client.options.hudHidden);
        try {
            context.runOnClient(client -> {
                client.options.getFov().setValue(110); client.options.hudHidden=true;
                camera.approveFlightRegion(origin.add(-28,-6,-28),origin.add(36,65,36));
                camera.configureFlight(true);
            });
            int[][] positions={{3,24,-22},{24,24,-15},{3,24,29}};
            String[] names={"reference-front","reference-quarter","reference-back"};
            for (int i=0;i<positions.length;i++) {
                var target=origin.add(positions[i][0],positions[i][1],positions[i][2]);
                var start=context.computeOnClient(client -> camera.start(target,true));
                var view=new com.google.gson.JsonObject(); view.addProperty("name",names[i]);
                view.addProperty("accepted",start.accepted());
                if (start.accepted()) {
                    var last=new NavigationProvider.NavigationStatus[]{null};
                    context.waitFor(client -> {
                        last[0]=camera.poll();
                        return last[0].state()!=NavigationProvider.NavigationStatus.State.RUNNING;
                    },1500);
                    boolean arrived=last[0].state()==NavigationProvider.NavigationStatus.State.SUCCEEDED;
                    view.addProperty("arrived",arrived); view.addProperty("reason",last[0].reason());
                    if (arrived) {
                        context.runOnClient(client -> {
                            double[] p=game.precisePosition();
                            double dx=origin.x()+3.5-p[0], dz=origin.z()+3.5-p[2];
                            game.look((float)Math.toDegrees(Math.atan2(-dx,dz)),
                                (float)-Math.toDegrees(Math.atan2(origin.y()+29-p[1]-1.62,Math.hypot(dx,dz))));
                        });
                        context.waitTicks(2); // Render the new camera angle; never placement pacing.
                        Files.copy(context.takeScreenshot(names[i]),directory.resolve(names[i]+".png"));
                    }
                } else view.addProperty("reason",start.reason());
                views.add(view);
            }
        } finally {
            context.runOnClient(client -> {
                camera.cancel(); camera.configureFlight(false);
                client.options.getFov().setValue(previousFov); client.options.hudHidden=previousHud;
            });
            var metadata=new com.google.gson.JsonObject(); metadata.addProperty("after_core_validation",true);
            metadata.addProperty("normal_keys_no_teleport",true); metadata.addProperty("excluded_from_core_timing",true);
            metadata.add("views",views); Files.writeString(directory.resolve("reference-views.json"),metadata.toString());
        }
    }
}
