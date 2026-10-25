// SPDX-License-Identifier: Apache-2.0
package com.android.settings.borealis;

import android.app.AlertDialog;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemProperties;
import android.provider.Settings;
import androidx.preference.ListPreference;
import androidx.preference.Preference;
import androidx.preference.PreferenceCategory;
import androidx.preference.PreferenceScreen;
import androidx.preference.SwitchPreferenceCompat;
import com.android.settings.R;
import com.android.settings.SettingsPreferenceFragment;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;

/** Native Settings controls. A vendor service owns all writes to kernel nodes. */
public final class BorealisPerformanceSettings extends SettingsPreferenceFragment {
    private static final String TRANSIENT = "borealis.perf.";
    private static final String PERSIST = "persist.borealis.perf.";
    private static final String VENDOR_STATUS = "vendor.borealis.perf.";
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Preference status;
    private Preference audioStatus;
    private Preference batteryStatus;
    private BorealisGraphicsPreferences graphics;
    private final ArrayList<ListPreference> clocks = new ArrayList<>();
    private final Runnable refresh = new Runnable() {
        @Override public void run() {
            String state = SystemProperties.get(VENDOR_STATUS + "status", "starting");
            String active = SystemProperties.get(VENDOR_STATUS + "active", "");
            status.setSummary(getString(R.string.borealis_status_format, profileName(active), performanceState(state)));
            audioStatus.setSummary(audioState(Settings.Global.getString(getContentResolver(), "borealis_audio_status")));
            graphics.refresh();
            Intent battery = getContext().registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
            if (battery != null) {
                int temperature = battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Integer.MIN_VALUE);
                int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
                int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
                if (temperature != Integer.MIN_VALUE && scale > 0 && level >= 0)
                    batteryStatus.setSummary(getString(R.string.borealis_battery_status_format, temperature / 10.0, level * 100 / scale));
            }
            handler.postDelayed(this, 1500);
        }
    };
    @Override public int getMetricsCategory() { return 0; }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        PreferenceScreen screen = getPreferenceManager().createPreferenceScreen(getContext());
        setPreferenceScreen(screen);
        Preference header = new Preference(getContext()); header.setSelectable(false);
        header.setLayoutResource(R.layout.borealis_performance_header); screen.addPreference(header);
        status = new Preference(getContext());
        status.setTitle(R.string.borealis_status); status.setSelectable(false); screen.addPreference(status);
        PreferenceCategory performance = category(screen, R.string.borealis_performance);
        ListPreference profile = list(performance, "profile", R.string.borealis_profile,
            new String[]{getString(R.string.borealis_stock), getString(R.string.borealis_battery),
                getString(R.string.borealis_balanced), getString(R.string.borealis_gaming), getString(R.string.borealis_ultra)},
            new String[]{"stock", "battery", "balanced", "gaming", "ultra"});
        profile.setValue(SystemProperties.get(TRANSIENT + "profile", SystemProperties.get(PERSIST + "profile", "balanced")));
        profile.setOnPreferenceChangeListener((p, value) -> {
            String chosen = (String)value;
            Runnable apply = () -> {
                // Clear manual frequency overrides so the new profile takes effect.
                for (ListPreference clock : clocks) { SystemProperties.set(TRANSIENT + clock.getKey(), "auto"); clock.setValue("auto"); }
                SystemProperties.set(TRANSIENT + "profile", chosen);
                if (Arrays.asList("battery", "balanced").contains(chosen))
                    SystemProperties.set(PERSIST + "profile", chosen);
                else SystemProperties.set(PERSIST + "profile", "balanced");
                profile.setValue(chosen); request();
            };
            if (chosen.equals("gaming") || chosen.equals("ultra")) confirm(apply);
            else apply.run();
            return false;
        });
        addClock(performance, "cpu_little", R.string.borealis_cpu_little, cpu(0) + "scaling_available_frequencies");
        addClock(performance, "cpu_big", R.string.borealis_cpu_big, cpu(6) + "scaling_available_frequencies");
        addClock(performance, "gpu", R.string.borealis_gpu, "/sys/kernel/gpu/gpu_freq_table");
        String[] governors = intersection(tokens(read(cpu(0) + "scaling_available_governors")), tokens(read(cpu(6) + "scaling_available_governors")));
        addOption(performance, "governor", R.string.borealis_governor, governors, false);
        PreferenceCategory memory = category(screen, R.string.borealis_memory_network);
        addOption(memory, "io", R.string.borealis_io, tokens(read("/sys/block/mmcblk0/queue/scheduler")), true);
        addOption(memory, "tcp", R.string.borealis_tcp, tokens(read("/proc/sys/net/ipv4/tcp_available_congestion_control")), true);
        addToggle(memory, "ksm", R.string.borealis_ksm, R.string.borealis_ksm_note, "/sys/kernel/mm/ksm/run");
        Preference zram = new Preference(getContext()); zram.setTitle("ZRAM"); zram.setSelectable(false);
        String algorithms = read("/sys/block/zram0/comp_algorithm");
        zram.setSummary(algorithms.isEmpty() ? getString(R.string.borealis_unavailable) : algorithms);
        memory.addPreference(zram);
        addToggle(memory, "usb", R.string.borealis_usb, R.string.borealis_usb_note, "/sys/kernel/fast_charge/force_fast_charge");
        batteryStatus = new Preference(getContext()); batteryStatus.setTitle(R.string.borealis_battery_status);
        batteryStatus.setSelectable(false); memory.addPreference(batteryStatus);
        PreferenceCategory audio = category(screen, R.string.borealis_audio);
        SwitchPreferenceCompat effect = new SwitchPreferenceCompat(getContext());
        effect.setKey("audio_enabled"); effect.setTitle(R.string.borealis_audio_enabled);
        effect.setSummary(R.string.borealis_audio_note); effect.setPersistent(false);
        effect.setChecked(Settings.Global.getInt(getContentResolver(), "borealis_audio_enabled", 0) == 1);
        effect.setOnPreferenceChangeListener((p, value) -> Settings.Global.putInt(getContentResolver(), "borealis_audio_enabled", (Boolean)value ? 1 : 0));
        audio.addPreference(effect);
        ListPreference preset = list(audio, "audio_preset", R.string.borealis_audio_preset,
            new String[]{getString(R.string.borealis_audio_flat), getString(R.string.borealis_audio_voice), getString(R.string.borealis_audio_warm)},
            new String[]{"flat", "voice", "warm"});
        String saved = Settings.Global.getString(getContentResolver(), "borealis_audio_preset");
        preset.setValue(saved == null ? "flat" : saved);
        preset.setOnPreferenceChangeListener((p, value) -> Settings.Global.putString(getContentResolver(), "borealis_audio_preset", (String)value));
        audioStatus = new Preference(getContext()); audioStatus.setTitle(R.string.borealis_audio_status);
        audioStatus.setSelectable(false); audio.addPreference(audioStatus);
        graphics = new BorealisGraphicsPreferences(getContext(), screen);
        Preference note = new Preference(getContext()); note.setTitle(R.string.borealis_limits);
        note.setSummary(R.string.borealis_limits_note); note.setSelectable(false); screen.addPreference(note);
    }
    @Override public void onResume() { super.onResume(); handler.post(refresh); }
    @Override public void onPause() { handler.removeCallbacks(refresh); super.onPause(); }
    private void request() {
        status.setSummary(R.string.borealis_applying);
        SystemProperties.set(TRANSIENT + "request", Long.toString(System.nanoTime()));
    }
    private String profileName(String name) {
        if (name.isEmpty()) return getString(R.string.borealis_not_applied);
        int resource = R.string.borealis_balanced;
        if ("stock".equals(name)) resource = R.string.borealis_stock;
        if ("battery".equals(name)) resource = R.string.borealis_battery;
        if ("gaming".equals(name)) resource = R.string.borealis_gaming;
        if ("ultra".equals(name)) resource = R.string.borealis_ultra;
        return getString(resource);
    }
    private String performanceState(String state) {
        if (state.equals("ok_applied_gpu_unavailable")) return getString(R.string.borealis_applied_without_gpu);
        if (state.startsWith("ok_")) return getString(R.string.borealis_applied);
        if (state.contains("rollback_failed")) return getString(R.string.borealis_reboot_required);
        if (state.startsWith("error_")) return getString(R.string.borealis_failed);
        return getString(R.string.borealis_applying);
    }
    private String audioState(String state) {
        int resource = R.string.borealis_audio_disabled;
        if ("active_compatible_mix".equals(state)) resource = R.string.borealis_audio_active;
        else if ("paused_call".equals(state)) resource = R.string.borealis_audio_paused;
        else if (state != null && state.startsWith("unavailable")) resource = R.string.borealis_audio_unavailable;
        return getString(resource);
    }
    private void confirm(Runnable apply) {
        new AlertDialog.Builder(getContext()).setTitle(R.string.borealis_experimental)
            .setMessage(R.string.borealis_experimental_note)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.borealis_apply, (d, which) -> apply.run()).show();
    }
    private PreferenceCategory category(PreferenceScreen screen, int title) {
        PreferenceCategory c = new PreferenceCategory(getContext()); c.setTitle(title); screen.addPreference(c); return c;
    }
    private ListPreference list(PreferenceCategory c, String key, int title, String[] entries, String[] values) {
        ListPreference p = new ListPreference(getContext()); p.setKey(key); p.setTitle(title);
        p.setPersistent(false); p.setEntries(entries); p.setEntryValues(values);
        p.setSummaryProvider(ListPreference.SimpleSummaryProvider.getInstance()); c.addPreference(p); return p;
    }
    private void addClock(PreferenceCategory category, String key, int title, String file) {
        String[] frequencies = tokens(read(file));
        ArrayList<String> values = new ArrayList<>(); values.add("auto");
        ArrayList<String> entries = new ArrayList<>(); entries.add(getString(R.string.borealis_profile_limit));
        ArrayList<Integer> numbers = new ArrayList<>();
        for (String f : frequencies) try {
            int value = Integer.parseInt(f);
            if (value > 0 && !numbers.contains(value)) numbers.add(value);
        } catch (NumberFormatException ignored) { }
        Collections.sort(numbers);
        for (int n : numbers) { values.add(Integer.toString(n)); entries.add((n > 10000 ? n / 1000 : n) + " MHz"); }
        ListPreference p = list(category, key, title, entries.toArray(new String[0]), values.toArray(new String[0]));
        p.setEnabled(!numbers.isEmpty()); p.setValue(SystemProperties.get(TRANSIENT + key, "auto")); clocks.add(p);
        if (numbers.isEmpty()) p.setSummaryProvider(pref -> getString(R.string.borealis_unavailable));
        p.setOnPreferenceChangeListener((pref, value) -> {
            Runnable apply = () -> { SystemProperties.set(TRANSIENT + key, (String)value); p.setValue((String)value); request(); };
            if (!"auto".equals(value)) confirm(apply); else apply.run(); return false;
        });
    }
    private void addOption(PreferenceCategory category, String key, int title, String[] options, boolean persistent) {
        ArrayList<String> values = new ArrayList<>(); values.add("default"); values.addAll(Arrays.asList(options));
        String[] labels = values.toArray(new String[0]); labels[0] = getString(R.string.borealis_default);
        ListPreference p = list(category, key, title, labels, values.toArray(new String[0]));
        String prefix = persistent ? PERSIST : TRANSIENT;
        p.setValue(SystemProperties.get(prefix + key, "default")); p.setEnabled(options.length > 0);
        p.setOnPreferenceChangeListener((pref, value) -> { SystemProperties.set(prefix + key, (String)value); request(); return true; });
    }
    private void addToggle(PreferenceCategory category, String key, int title, int summary, String file) {
        SwitchPreferenceCompat p = new SwitchPreferenceCompat(getContext()); p.setKey(key); p.setTitle(title);
        p.setSummary(summary); p.setPersistent(false); String current = read(file); p.setEnabled(!current.isEmpty());
        p.setChecked(SystemProperties.get(PERSIST + key, current).equals("1"));
        p.setOnPreferenceChangeListener((pref, value) -> { SystemProperties.set(PERSIST + key, (Boolean)value ? "1" : "0"); request(); return true; });
        category.addPreference(p);
    }
    private static String cpu(int core) {
        String policy = "/sys/devices/system/cpu/cpufreq/policy" + core + "/";
        return read(policy + "scaling_available_frequencies").isEmpty() ? "/sys/devices/system/cpu/cpu" + core + "/cpufreq/" : policy;
    }
    private static String read(String path) {
        try { return new String(Files.readAllBytes(Paths.get(path)), StandardCharsets.UTF_8).trim(); }
        catch (Exception e) { return ""; }
    }
    private static String[] tokens(String text) {
        return text.trim().isEmpty() ? new String[0] : text.replace("[", "").replace("]", "").trim().split("\\s+");
    }
    private static String[] intersection(String[] a, String[] b) {
        ArrayList<String> result = new ArrayList<>(Arrays.asList(a)); result.retainAll(Arrays.asList(b)); return result.toArray(new String[0]);
    }
}
