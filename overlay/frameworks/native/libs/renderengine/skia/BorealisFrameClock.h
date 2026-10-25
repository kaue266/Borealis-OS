// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <cstdint>

namespace android::renderengine::borealis {
enum class FrameAction { Real, Interpolate, Hold };
// One intermediate presentation followed by the captured real frame. Never
// extrapolates, never runs an idle animation, and skips already-fast sources.
class FrameClock {
public:
    FrameAction advance(uint64_t token, int64_t now, bool enabled) {
        const bool changed = !mHaveFrame || token != mToken;
        if (!changed) {
            if (mPending) { mPending = false; return FrameAction::Real; }
            return FrameAction::Hold;
        }
        const int64_t interval = mHaveFrame ? now - mTime : 0;
        const bool interpolate = enabled && mHaveFrame && !mPending &&
                interval >= 25000000 && interval <= 75000000;
        mToken = token; mTime = now; mHaveFrame = true; mPending = interpolate;
        return interpolate ? FrameAction::Interpolate : FrameAction::Real;
    }
    void reset() { mHaveFrame = mPending = false; mTime = 0; mToken = 0; }
    bool pending() const { return mPending; }
private:
    bool mHaveFrame = false, mPending = false;
    uint64_t mToken = 0;
    int64_t mTime = 0;
};
}
