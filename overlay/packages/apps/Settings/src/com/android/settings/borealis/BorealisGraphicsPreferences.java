// SPDX-License-Identifier: Apache-2.0
package com.android.settings.borealis;

import android.app.AlertDialog;
import android.content.Context;
import android.os.SystemProperties;
import androidx.preference.ListPreference;
import androidx.preference.Preference;
import androidx.preference.PreferenceCategory;
import androidx.preference.PreferenceScreen;
import androidx.preference.SwitchPreferenceCompat;
import com.android.settings.R;

/** Independent runtime controls; experimental effects reset after reboot. */
final class BorealisGraphicsPreferences {
    private static final String PREFIX = "debug.borealis.graphics.";
    private final Context context;
    private final Preference status;
    private SwitchPreferenceCompat easu, rcas, fg;
    private ListPreference scale, sharpness;
    private final boolean supported;

    BorealisGraphicsPreferences(Context context, PreferenceScreen screen) {
        this.context = context;
        PreferenceCategory category = new PreferenceCategory(context);
        category.setTitle(R.string.borealis_graphics); screen.addPreference(category);
        supported = "fsr1-experimental".equals(SystemProperties.get("ro.borealis.graphics.fsr"));
        easu = toggle(category, "easu", R.string.borealis_graphics_easu,
                R.string.borealis_graphics_mode_note);
        easu.setOnPreferenceChangeListener((p, value) -> {
            Runnable apply = () -> {
                applySpatial((Boolean) value, rcas.isChecked()); refresh();
            };
            if ((Boolean) value) confirm(apply); else apply.run();
            return false;
        });
        scale = list(category, "scale", R.string.borealis_graphics_scale,
                new String[]{"100% · Native", "77% · Ultra Quality", "67% · Quality",
                        "59% · Balanced", "50% · Performance", "33% · Experimental",
                        "25% · Experimental (270 × 585)"},
                new String[]{"100", "77", "67", "59", "50", "33", "25"}, "67");
        scale.setOnPreferenceChangeListener((p, value) -> {
            if (scale.findIndexOfValue((String) value) < 0) return false;
            set("scale", (String) value); return true;
        });
        rcas = toggle(category, "rcas", R.string.borealis_graphics_rcas,
                R.string.borealis_graphics_rcas_note);
        rcas.setOnPreferenceChangeListener((p, value) -> {
            Runnable apply = () -> {
                if ((Boolean) value && SystemProperties.getInt(PREFIX+"sharpness", 0) <= 0)
                    set("sharpness", "50");
                applySpatial(easu.isChecked(), (Boolean) value); refresh();
            };
            if ((Boolean) value) confirm(apply); else apply.run();
            return false;
        });
        sharpness = list(category, "sharpness", R.string.borealis_graphics_sharpness,
                new String[]{context.getString(R.string.borealis_graphics_off), "25%", "50%", "75%", "100%"},
                new String[]{"0", "25", "50", "75", "100"}, "0");
        sharpness.setSummaryProvider(preference -> {
            int value = Math.max(0, Math.min(100,
                    SystemProperties.getInt(PREFIX+"sharpness", 0)));
            return value == 0 ? context.getString(R.string.borealis_graphics_off) : value+"%";
        });
        sharpness.setOnPreferenceChangeListener((p, value) -> {
            if (sharpness.findIndexOfValue((String) value) < 0) return false;
            set("sharpness", (String) value); refresh(); return false;
        });
        fg = toggle(category, "fg", R.string.borealis_graphics_fg,
                R.string.borealis_graphics_fg_note);
        fg.setOnPreferenceChangeListener((p, value) -> {
            Runnable apply = () -> { set("fg", (Boolean)value ? "1" : "0"); refresh(); };
            if ((Boolean)value) confirm(apply); else apply.run();
            return false;
        });
        Preference reload = new Preference(context); reload.setTitle(R.string.borealis_graphics_reload);
        reload.setSummary(R.string.borealis_graphics_reload_note); reload.setEnabled(supported);
        reload.setOnPreferenceClickListener(p -> { set("reload", Long.toString(System.nanoTime())); return true; });
        category.addPreference(reload);
        Preference reset = new Preference(context); reset.setTitle(R.string.borealis_graphics_reset);
        reset.setEnabled(supported);
        reset.setOnPreferenceClickListener(p -> {
            set("mode", "off"); set("rcas", "0"); set("fg", "0"); set("scale", "67");
            set("sharpness", "0"); set("reload", "builtin"); refresh(); return true;
        }); category.addPreference(reset);
        status = new Preference(context); status.setTitle(R.string.borealis_graphics_status);
        status.setSelectable(false); category.addPreference(status);
        Preference temporal = new Preference(context); temporal.setTitle("FSR 2 / FSR 3");
        temporal.setSummary(R.string.borealis_graphics_temporal_note); temporal.setSelectable(false);
        category.addPreference(temporal);
        refresh();
    }
    private void applySpatial(boolean upscale, boolean sharpen) {
        // Explicit RCAS prevents EASU from inheriting legacy stored sharpness.
        set("rcas", sharpen ? "1" : "0");
        set("mode", upscale ? "fsr1" : sharpen ? "rcas" : "off");
    }
    void refresh() {
        String mode = SystemProperties.get(PREFIX+"mode", "off");
        boolean upscale = "fsr1".equals(mode);
        boolean sharpen = (upscale || "rcas".equals(mode))
                && SystemProperties.getBoolean(PREFIX+"rcas", true);
        easu.setChecked(upscale); rcas.setChecked(sharpen);
        fg.setChecked(SystemProperties.getBoolean(PREFIX+"fg", false));
        String requestedScale = Integer.toString(SystemProperties.getInt(PREFIX+"scale", 67));
        scale.setValue(scale.findIndexOfValue(requestedScale) >= 0 ? requestedScale : "100");
        int strength = Math.max(0, Math.min(100, SystemProperties.getInt(PREFIX+"sharpness", 0)));
        sharpness.setValue(Integer.toString(strength));
        // Preparing values while a stage is off must not enable it.
        scale.setEnabled(supported); sharpness.setEnabled(supported);
        String state = SystemProperties.get(PREFIX+"status", "off");
        int text = R.string.borealis_graphics_off;
        if ("fsr1".equals(state)) text = R.string.borealis_graphics_fsr_active;
        else if ("rcas".equals(state)) text = R.string.borealis_graphics_rcas_active;
        else if (state.startsWith("fg_")) text = "fg_unavailable".equals(state) ? R.string.borealis_graphics_failed : R.string.borealis_graphics_fg_active;
        else if ("bypassed".equals(state)) text = R.string.borealis_graphics_bypassed;
        else if ("hwc_bypass".equals(state)) text = R.string.borealis_graphics_hwc_bypassed;
        else if (state.contains("error") || state.equals("reload_rejected")) text = R.string.borealis_graphics_failed;
        status.setSummary(text);
    }
    private void set(String key, String value) { SystemProperties.set(PREFIX+key, value); }
    private SwitchPreferenceCompat toggle(PreferenceCategory category, String key, int title, int note) {
        SwitchPreferenceCompat p = new SwitchPreferenceCompat(context);
        p.setKey("borealis_graphics_"+key); p.setPersistent(false);
        p.setTitle(title); p.setSummary(note); p.setEnabled(supported);
        category.addPreference(p); return p;
    }
    private ListPreference list(PreferenceCategory category, String key, int title, String[] labels, String[] values, String fallback) {
        ListPreference p = new ListPreference(context); p.setKey("borealis_graphics_"+key); p.setTitle(title);
        p.setPersistent(false); p.setEntries(labels); p.setEntryValues(values);
        p.setValue(SystemProperties.get(PREFIX+key, fallback));
        p.setSummaryProvider(ListPreference.SimpleSummaryProvider.getInstance()); category.addPreference(p); return p;
    }
    private void confirm(Runnable apply) {
        new AlertDialog.Builder(context).setTitle(R.string.borealis_graphics_experimental)
                .setMessage(R.string.borealis_graphics_warning)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.borealis_apply, (d,w) -> apply.run()).show();
    }
}
