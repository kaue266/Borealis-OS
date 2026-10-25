package org.borealis.space;

import android.animation.ValueAnimator;
import android.view.Choreographer;
import android.view.MotionEvent;
import android.view.View;

/** Retargetable, critically damped press spring with continuous velocity. */
final class BorealisMotion implements Choreographer.FrameCallback {
    private final View view;
    private float position = 1f, velocity, target = 1f;
    private long previous;
    private boolean scheduled;
    private BorealisMotion(View view) { this.view = view; }
    static void press(View view) {
        view.setStateListAnimator(null);
        view.setElevation(0);
        BorealisMotion motion = new BorealisMotion(view);
        view.setOnTouchListener((v, event) -> {
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN: motion.to(.975f); break;
                case MotionEvent.ACTION_MOVE:
                    float slop = 10 * v.getResources().getDisplayMetrics().density;
                    boolean inside = event.getX() >= -slop && event.getY() >= -slop &&
                        event.getX() <= v.getWidth() + slop && event.getY() <= v.getHeight() + slop;
                    motion.to(inside ? .975f : 1f); break;
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL: motion.to(1f); break;
            }
            return false; // Keep native click cancellation, ripple and accessibility.
        });
        view.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener() {
            public void onViewAttachedToWindow(View v) {}
            public void onViewDetachedFromWindow(View v) {
                Choreographer.getInstance().removeFrameCallback(motion);
                motion.scheduled = false; motion.previous = 0;
            }
        });
    }
    private void to(float value) {
        target = value;
        if (!ValueAnimator.areAnimatorsEnabled()) {
            position = target; velocity = 0;
            view.setScaleX(position); view.setScaleY(position); return;
        }
        if (!scheduled) {
            previous = 0; scheduled = true;
            Choreographer.getInstance().postFrameCallback(this);
        }
    }
    public void doFrame(long now) {
        float dt = previous == 0 ? 1f / 60f : Math.min((now - previous) / 1e9f, .032f);
        previous = now;
        // Exact damped solution avoids instability when the A30 drops a frame.
        float omega = 24f, offset = position - target;
        float blend = velocity + omega * offset;
        float decay = (float)Math.exp(-omega * dt);
        position = target + (offset + blend * dt) * decay;
        velocity = (velocity - omega * blend * dt) * decay;
        view.setScaleX(position); view.setScaleY(position);
        if (Math.abs(position - target) < .0001f && Math.abs(velocity) < .001f) {
            position = target; velocity = 0; scheduled = false; previous = 0;
            view.setScaleX(position); view.setScaleY(position);
        } else Choreographer.getInstance().postFrameCallback(this);
    }
}
