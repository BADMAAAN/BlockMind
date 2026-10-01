package dev.blockmind.minecraft.navigation;
import dev.blockmind.minecraft.GameAccess;
import dev.blockmind.minecraft.GameAccess.Pos;

/** Flat, verified one/two-block steering only; complex/vertical travel stays with the backend. */
public final class LocalNavigationProvider implements NavigationProvider {
    private final GameAccess game; private final NavigationProvider backend;
    private boolean enabled = true, local, settling; private Pos target; private int ticks;
    private int localGoals;
    public com.google.gson.JsonObject performance() { var value=backend.performance(); value.addProperty("localGoals",localGoals); return value; }
    public LocalNavigationProvider(GameAccess game, NavigationProvider backend) { this.game=game; this.backend=backend; }
    public void configureLocal(boolean enabled) { this.enabled = enabled; }
    public boolean available() { return backend.available(); }
    public StartResult start(Pos target, boolean hazards) {
        this.target=target; ticks=0; settling=false;
        local = enabled && !game.localMove(target).equals("unsupported");
        if (local) localGoals++;
        return local ? new StartResult(true,target,"local steering",false) : backend.start(target,true);
    }
    public NavigationStatus poll() {
        if (settling) {
            String state = game.localMove(target);
            if (state.equals("unsupported") && ++ticks <= 10)
                return new NavigationStatus(NavigationStatus.State.RUNNING, game.playerPosition(), "settling after arrival");
            settling = false;
            if (state.equals("unsupported")) return new NavigationStatus(NavigationStatus.State.FAILED, game.playerPosition(), "could not settle at interaction position");
            if (state.equals("arrived")) return new NavigationStatus(NavigationStatus.State.SUCCEEDED, game.playerPosition(), "centered arrived");
            local = true; ticks = 0; localGoals++;
        }
        if (!local) {
            var status = backend.poll();
            if (enabled && status.state() == NavigationStatus.State.SUCCEEDED) {
                settling = true; ticks = 0;
                return new NavigationStatus(NavigationStatus.State.RUNNING, game.playerPosition(), "centering after arrival");
            }
            return status;
        }
        String state=game.localMove(target);
        if (state.equals("arrived")) { local=false; return new NavigationStatus(NavigationStatus.State.SUCCEEDED,game.playerPosition(),"local arrived"); }
        if (state.equals("unsupported") || ++ticks > 30) {
            game.releaseMovement(); local=false; var result=backend.start(target,true);
            if (!result.accepted()) return new NavigationStatus(NavigationStatus.State.FAILED,game.playerPosition(),result.reason());
        }
        return new NavigationStatus(NavigationStatus.State.RUNNING,game.playerPosition(),"");
    }
    public void cancel() { local=false; settling=false; backend.cancel(); game.releaseMovement(); }
}
