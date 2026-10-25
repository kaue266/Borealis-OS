// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "compat/SkiaGpuContext.h"
#include <SkSurface.h>
#include <SkImage.h>
#include <SkRuntimeEffect.h>
#include <renderengine/DisplaySettings.h>
#include "BorealisFrameClock.h"
#include <array>
#include <string>

namespace android::renderengine::skia {
// Owned and called only by the RenderEngine GPU thread, under its render lock.
class BorealisGraphics {
public:
    sk_sp<SkSurface> begin(SkiaGpuContext*, sk_sp<SkSurface> output,
                           const DisplaySettings&, bool safe);
    void finish(SkiaGpuContext*, sk_sp<SkSurface> composed, sk_sp<SkSurface> output,
                const DisplaySettings&);
    void reset();
    bool hasHistory() const { return bool(mPrevious) || bool(mCurrent); }
private:
    bool loadEffects(bool external);
    sk_sp<SkImage> render(SkiaGpuContext*, const SkImageInfo&, SkRuntimeShaderBuilder&);
    sk_sp<SkImage> spatial(SkiaGpuContext*, sk_sp<SkImage>, const SkImageInfo&);
    sk_sp<SkImage> interpolate(SkiaGpuContext*, sk_sp<SkImage>, sk_sp<SkImage>);
    std::array<sk_sp<SkRuntimeEffect>, 4> mEffects;
    sk_sp<SkImage> mPrevious, mCurrent;
    borealis::FrameClock mClock;
    DisplaySettings mLastDisplay;
    uint64_t mGeneration = 0, mToken = 0;
    bool mActive = false, mHaveDisplay = false, mEffectsReady = false;
    bool mFrameGen = false, mRcas = false;
    bool mReloadRejected = false;
    int mScale = 67, mSharpness = 0;
    std::string mMode = "off", mReload;
};
}
