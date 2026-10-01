package dev.blockmind.minecraft;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class AudioSessionTest {
    @Test void muteRemembersOriginalAndRestoresAfterRepeatedConfiguration() {
        double[] volume={.37}; var audio=new AudioSession(()->volume[0],value->volume[0]=value);
        audio.begin(true,true); audio.begin(true,true); assertEquals(0,volume[0]);
        audio.finish(); assertEquals(.37,volume[0]); audio.finish(); assertEquals(.37,volume[0]);
    }
    @Test void permanentMuteAndExplicitUnmuteOnlyAffectMasterVolume() {
        double[] volume={.63}; var audio=new AudioSession(()->volume[0],value->volume[0]=value);
        audio.begin(true,false); audio.finish(); assertEquals(0,volume[0]);
        audio.unmute(); assertEquals(.63,volume[0]);
    }
}
