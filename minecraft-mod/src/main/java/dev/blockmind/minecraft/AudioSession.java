package dev.blockmind.minecraft;
import java.util.function.DoubleSupplier;
import java.util.function.DoubleConsumer;

/** Only Minecraft's master volume; no OS audio changes or live options-file edits. */
final class AudioSession {
    private final DoubleSupplier read;
    private final DoubleConsumer write;
    private Double previous;
    private boolean restore = true;
    AudioSession(DoubleSupplier read, DoubleConsumer write) { this.read = read; this.write = write; }
    void begin(boolean mute, boolean restore) {
        this.restore = restore;
        if (mute) { if (previous == null) previous = read.getAsDouble(); write.accept(0); }
        else unmute();
    }
    void finish() { if (restore) unmute(); }
    void unmute() { if (previous != null) { write.accept(previous); previous = null; } }
}
