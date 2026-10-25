// SPDX-License-Identifier: Apache-2.0
package com.android.server.borealis;

import android.content.Context;
import android.database.ContentObserver;
import android.media.AudioManager;
import android.media.audiofx.Equalizer;
import android.os.Handler;
import android.os.HandlerThread;
import android.provider.Settings;
import android.util.Slog;
import com.android.server.SystemService;

/** Optional mix equalizer. No amplifier gain, fake Dolby, or volume bypass. */
public final class BorealisAudioService extends SystemService {
    private static final String TAG = "BorealisAudio";
    private Handler handler;
    private Equalizer equalizer;
    private AudioManager manager;
    public BorealisAudioService(Context context) { super(context); }
    @Override public void onStart() { }
    @Override public void onBootPhase(int phase) {
        if (phase != PHASE_BOOT_COMPLETED) return;
        try { startAudio(); }
        catch (RuntimeException error) { Slog.w(TAG, "Audio service unavailable", error); release(); status("unavailable_service"); }
    }
    private void startAudio() {
        HandlerThread thread = new HandlerThread(TAG); thread.start(); handler = new Handler(thread.getLooper());
        manager = getContext().getSystemService(AudioManager.class);
        ContentObserver observer = new ContentObserver(handler) {
            @Override public void onChange(boolean selfChange) { apply(); }
        };
        getContext().getContentResolver().registerContentObserver(Settings.Global.getUriFor("borealis_audio_enabled"), false, observer);
        getContext().getContentResolver().registerContentObserver(Settings.Global.getUriFor("borealis_audio_preset"), false, observer);
        manager.addOnModeChangedListener(command -> handler.post(command), mode -> apply());
        handler.post(this::apply);
    }
    @SuppressWarnings("deprecation")
    private void apply() {
        boolean enabled = Settings.Global.getInt(getContext().getContentResolver(), "borealis_audio_enabled", 0) == 1;
        if (!enabled || manager.getMode() != AudioManager.MODE_NORMAL) {
            release(); status(enabled ? "paused_call" : "disabled"); return;
        }
        try {
            if (equalizer == null) equalizer = new Equalizer(0, 0);
            if (!equalizer.hasControl()) { release(); status("unavailable_control"); return; }
            String preset = Settings.Global.getString(getContext().getContentResolver(), "borealis_audio_preset");
            short[] range = equalizer.getBandLevelRange();
            for (short band = 0; band < equalizer.getNumberOfBands(); ++band) {
                int hz = equalizer.getCenterFreq(band) / 1000;
                // Attenuation only: headroom stays within the existing mix.
                int level = 0;
                if ("voice".equals(preset) && (hz < 250 || hz > 6000)) level = -250;
                if ("warm".equals(preset) && hz > 2000) level = -200;
                equalizer.setBandLevel(band, (short)Math.max(range[0], Math.min(range[1], level)));
            }
            equalizer.setEnabled(true);
            status("active_compatible_mix");
        } catch (RuntimeException error) {
            Slog.w(TAG, "Equalizer unavailable", error); release(); status("unavailable_effect");
        }
    }
    private void release() {
        if (equalizer != null) { try { equalizer.release(); } catch (RuntimeException ignored) { } equalizer = null; }
    }
    private void status(String state) { Settings.Global.putString(getContext().getContentResolver(), "borealis_audio_status", state); }
}
