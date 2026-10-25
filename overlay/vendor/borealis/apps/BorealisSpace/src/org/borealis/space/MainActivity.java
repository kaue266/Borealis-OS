package org.borealis.space;

import android.app.Activity;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.app.WallpaperManager;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.animation.ValueAnimator;
import android.content.res.ColorStateList;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.StyleSpan;
import android.text.style.RelativeSizeSpan;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.format.Formatter;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.graphics.Insets;
import android.widget.ImageView;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private LinearLayout content;
    private LinearLayout tabs;
    private int selected;
    private Bitmap wallpaperPreview;
    private Typeface orbit;
    private int BACKGROUND, CARD, TEXT, MUTED, ACCENT, AURORA, OUTLINE, ON_ACCENT;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        BACKGROUND = getColor(R.color.borealis_background);
        CARD = getColor(R.color.borealis_surface);
        TEXT = getColor(R.color.borealis_text);
        MUTED = getColor(R.color.borealis_muted);
        ACCENT = getColor(R.color.borealis_accent);
        AURORA = getColor(R.color.borealis_aurora);
        OUTLINE = getColor(R.color.borealis_outline);
        ON_ACCENT = getColor(R.color.borealis_on_accent);
        getWindow().setDecorFitsSystemWindows(false);
        orbit = getResources().getFont(R.font.borealis_orbit);
        if (state != null) selected = state.getInt("tab", 0);
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = 2;
        wallpaperPreview = BitmapFactory.decodeResource(getResources(), R.drawable.cosmic_wallpaper, options);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BACKGROUND);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            Insets safe = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
            view.setPadding(safe.left, safe.top, safe.right, safe.bottom);
            return insets;
        });
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(22), dp(20), dp(22), dp(24));
        scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        tabs = new LinearLayout(this);
        tabs.setPadding(dp(12), dp(8), dp(12), dp(12));
        root.addView(tabs, new LinearLayout.LayoutParams(-1, -2));
        setContentView(root);
        root.requestApplyInsets();
        show(selected);
    }

    private void show(int tab) {
        content.animate().cancel();
        selected = Math.max(0, Math.min(2, tab));
        content.removeAllViews();
        tabs.removeAllViews();
        int[] names = {R.string.home, R.string.appearance, R.string.system};
        for (int i = 0; i < names.length; i++) {
            final int index = i;
            Button item = new Button(this);
            item.setText(names[i]); item.setTextSize(14); item.setAllCaps(false);
            item.setTextColor(i == selected ? ACCENT : MUTED);
            item.setMinHeight(dp(48)); item.setMinimumHeight(dp(48));
            item.setGravity(Gravity.CENTER);
            item.setPadding(0, dp(15), 0, dp(15));
            item.setBackground(ripple(i == selected ? CARD : BACKGROUND, 20));
            item.setOnClickListener(v -> show(index));
            item.setSelected(i == selected);
            item.setFocusable(true);
            BorealisMotion.press(item);
            tabs.addView(item, new LinearLayout.LayoutParams(0, -2, 1));
        }
        if (selected == 0) home();
        else if (selected == 1) appearance();
        else system();
        // Tab changes keep their current presentation; no teleporting content.
        content.setAlpha(1f); content.setTranslationY(0f);
    }

    private void home() {
        TextView label = text(R.string.eyebrow, 10, ACCENT);
        label.setLetterSpacing(0.16f);
        content.addView(label);
        TextView edition = text(R.string.edition, 12, AURORA);
        edition.setPadding(0, dp(20), 0, 0); content.addView(edition);
        TextView brand = text(R.string.brand, 38, TEXT);
        brand.setTypeface(orbit);
        brand.setPadding(0, dp(8), 0, dp(3));
        content.addView(brand);
        addText(R.string.tagline, 19, MUTED);
        addPreview(190);
        addText(R.string.intro, 14, MUTED);
        TextView device = text(getString(R.string.device_format, Build.MODEL, Build.VERSION.RELEASE), 12, ACCENT);
        device.setPadding(0, dp(18), 0, dp(10));
        content.addView(device);
        card(R.string.performance, R.string.performance_detail, this::kernel);
        card(R.string.battery, R.string.battery_detail, () -> open(Settings.ACTION_BATTERY_SAVER_SETTINGS));
        card(R.string.display, R.string.display_detail, () -> open(Settings.ACTION_DISPLAY_SETTINGS));
    }

    private void appearance() {
        title(R.string.appearance);
        addText(R.string.wallpaper, 21, ACCENT);
        addPreview(340);
        addText(R.string.wallpaper_detail, 14, MUTED);
        action(R.string.apply_wallpaper, this::applyWallpaper);
        action(R.string.wallpaper_picker, () -> open(Intent.ACTION_SET_WALLPAPER));
        card(R.string.display, R.string.display_detail, () -> open(Settings.ACTION_DISPLAY_SETTINGS));
    }

    private void system() {
        title(R.string.system);
        ActivityManager.MemoryInfo info = new ActivityManager.MemoryInfo();
        getSystemService(ActivityManager.class).getMemoryInfo(info);
        content.addView(text(getString(R.string.memory_format,
            Formatter.formatFileSize(this, info.availMem),
            Formatter.formatFileSize(this, info.totalMem)), 14, ACCENT));
        card(R.string.about, R.string.about_detail, () -> new AlertDialog.Builder(this)
            .setTitle(R.string.about)
            .setMessage(getString(R.string.about_format, Build.MODEL, Build.VERSION.RELEASE, Build.DISPLAY))
            .setPositiveButton(R.string.close, null).show());
        card(R.string.storage, R.string.storage_detail, () -> open(Settings.ACTION_INTERNAL_STORAGE_SETTINGS));
        card(R.string.privacy, R.string.privacy_detail, () -> open(Settings.ACTION_PRIVACY_SETTINGS));
        card(R.string.performance, R.string.performance_detail, this::kernel);
        addText(R.string.root_note, 12, MUTED);
        addText(R.string.graphics_note, 12, MUTED);
        TextView badge = text(R.string.experimental, 10, ACCENT);
        badge.setLetterSpacing(0.12f);
        badge.setPadding(0, dp(24), 0, 0);
        content.addView(badge);
    }

    private void title(int resource) {
        TextView view = text(resource, 32, TEXT);
        view.setTypeface(orbit);
        view.setPadding(0, 0, 0, dp(20));
        content.addView(view);
    }

    private void addPreview(int height) {
        ImageView image = new ImageView(this);
        image.setImageBitmap(wallpaperPreview);
        image.setScaleType(ImageView.ScaleType.CENTER_CROP);
        image.setContentDescription(getString(R.string.wallpaper));
        image.setBackground(round(CARD, 26));
        image.setClipToOutline(true);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(height));
        params.setMargins(0, dp(20), 0, dp(20));
        content.addView(image, params);
    }

    private void card(int title, int detail, Runnable onClick) {
        Button box = new Button(this);
        box.setAllCaps(false); box.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        box.setTextColor(TEXT); box.setTextSize(14);
        box.setMinHeight(dp(88)); box.setMinimumHeight(dp(88));
        box.setPadding(dp(20), dp(19), dp(20), dp(19));
        box.setBackground(ripple(CARD, 24));
        String heading = getString(title);
        SpannableString label = new SpannableString(heading + "\n" + getString(detail));
        label.setSpan(new StyleSpan(Typeface.BOLD), 0, heading.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        label.setSpan(new RelativeSizeSpan(1.22f), 0, heading.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        box.setText(label); box.setLineSpacing(dp(5), 1f);
        box.setContentDescription(getString(title) + ". " + getString(detail));
        box.setOnClickListener(v -> onClick.run());
        box.setFocusable(true);
        BorealisMotion.press(box);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, dp(10), 0, 0);
        content.addView(box, params);
    }

    private void action(int label, Runnable onClick) {
        Button button = new Button(this); button.setText(label); button.setTextSize(14);
        button.setTextColor(ON_ACCENT); button.setAllCaps(false);
        button.setMinHeight(dp(48));
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(16), dp(18), dp(16), dp(18));
        button.setBackground(ripple(ACCENT, 20));
        button.setOnClickListener(v -> onClick.run());
        button.setFocusable(true);
        BorealisMotion.press(button);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, dp(14), 0, dp(2));
        content.addView(button, params);
    }

    private void applyWallpaper() {
        worker.execute(() -> {
            boolean ok;
            try {
                WallpaperManager.getInstance(getApplicationContext()).setResource(R.drawable.cosmic_wallpaper);
                ok = true;
            } catch (Exception failure) { ok = false; }
            final boolean success = ok;
            runOnUiThread(() -> {
                if (!isFinishing() && !isDestroyed())
                    Toast.makeText(this, success ? R.string.wallpaper_applied : R.string.wallpaper_failed, Toast.LENGTH_SHORT).show();
            });
        });
    }

    private void kernel() {
        try {
            startActivity(new Intent().setComponent(new ComponentName("com.android.settings", "com.android.settings.Settings$BorealisPerformanceActivity")));
        } catch (ActivityNotFoundException failure) {
            Toast.makeText(this, R.string.kernel_missing, Toast.LENGTH_LONG).show();
        }
    }

    private void open(String action) {
        try { startActivity(new Intent(action)); }
        catch (ActivityNotFoundException failure) { Toast.makeText(this, R.string.unavailable, Toast.LENGTH_SHORT).show(); }
    }

    private void addText(int resource, int size, int color) {
        TextView view = text(resource, size, color);
        view.setPadding(0, dp(8), 0, dp(4));
        content.addView(view);
    }
    private TextView text(int resource, int size, int color) { return text(getString(resource), size, color); }
    private TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value); view.setTextSize(size); view.setTextColor(color);
        return view;
    }
    private GradientDrawable round(int color, int radius) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color); shape.setCornerRadius(dp(radius));
        if (color == CARD) shape.setStroke(dp(1), OUTLINE);
        return shape;
    }
    private RippleDrawable ripple(int color, int radius) {
        return new RippleDrawable(ColorStateList.valueOf(Color.argb(45,197,180,255)),
                round(color,radius),round(Color.WHITE,radius));
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    @Override public void onSaveInstanceState(Bundle state) { state.putInt("tab", selected); super.onSaveInstanceState(state); }
    @Override public void onDestroy() { worker.shutdownNow(); super.onDestroy(); }
}
