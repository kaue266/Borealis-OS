// SPDX-License-Identifier: Apache-2.0
#include "BorealisGraphics.h"
#include "BorealisShaders.h"
#include <renderengine/BorealisGraphics.h>
#include <android-base/properties.h>
#include <SkCanvas.h>
#include <SkPaint.h>
#include <SkSamplingOptions.h>
#include <SkString.h>
#include <utils/Timers.h>
#include <log/log.h>
#define ATRACE_TAG ATRACE_TAG_GRAPHICS
#include <utils/Trace.h>
#include <algorithm>
#include <cmath>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace android::renderengine::skia {
namespace {
using Type = SkRuntimeEffect::Uniform::Type;
const char* names[] = {"easu", "rcas", "flow", "interpolate"};
const char* builtins[] = {kBorealisEasu, kBorealisRcas, kBorealisFlow, kBorealisInterpolate};
bool uniform(const SkRuntimeEffect* effect, const char* name, Type type) {
    const auto* u = effect->findUniform(name);
    return u && u->type == type && !u->isArray() && !u->isColor();
}
bool child(const SkRuntimeEffect* effect, const char* name) {
    const auto* c = effect->findChild(name);
    return c && c->type == SkRuntimeEffect::ChildType::kShader;
}
bool interfaceValid(const SkRuntimeEffect* effect, int index) {
    if (index == 0) return effect->children().size() == 1 && effect->uniforms().size() == 2 &&
            child(effect, "inputImage") && uniform(effect, "inputSize", Type::kFloat2) &&
            uniform(effect, "outputSize", Type::kFloat2);
    if (index == 1) return effect->children().size() == 1 && effect->uniforms().size() == 1 &&
            child(effect, "inputImage") && uniform(effect, "strength", Type::kFloat);
    return effect->children().size() == 3 && effect->uniforms().size() == 2 &&
            child(effect, "previousImage") && child(effect, "currentImage") &&
            child(effect, "flowImage") && uniform(effect, "imageScale", Type::kFloat2) &&
            uniform(effect, index == 2 ? "hasFlow" : "imageSize",
                    index == 2 ? Type::kFloat : Type::kFloat2);
}
// A developer-installed text bundle, never an executable library. All four
// shaders must pass both compilation and interface checks before replacing it.
bool readShader(const char* name, std::string& value) {
    const std::string path = std::string("/data/misc/borealis-graphics/") + name + ".sksl";
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return false;
    struct stat st {};
    const bool safe = fstat(fd, &st) == 0 && S_ISREG(st.st_mode) &&
            (st.st_uid == 0 || st.st_uid == 1000) && !(st.st_mode & 0022) &&
            st.st_size > 0 && st.st_size <= 32768;
    if (!safe) { close(fd); return false; }
    value.resize(st.st_size);
    size_t offset = 0;
    while (offset < value.size()) {
        const auto n = read(fd, value.data() + offset, value.size() - offset);
        if (n <= 0) { close(fd); return false; }
        offset += n;
    }
    close(fd); return true;
}
sk_sp<SkShader> imageShader(sk_sp<SkImage> image, bool linear = false, bool raw = false) {
    const SkSamplingOptions sampling(linear ? SkFilterMode::kLinear : SkFilterMode::kNearest);
    return raw ? image->makeRawShader(sampling) : image->makeShader(sampling);
}
}

void BorealisGraphics::reset() {
    mPrevious.reset(); mCurrent.reset(); mClock.reset(); mToken = 0;
    mActive = false; mHaveDisplay = false;
    borealis::setPendingFrame(false);
}
bool BorealisGraphics::loadEffects(bool external) {
    std::array<sk_sp<SkRuntimeEffect>, 4> candidate;
    for (int i = 0; i < 4; ++i) {
        std::string text;
        if (external && !readShader(names[i], text)) return false;
        auto result = SkRuntimeEffect::MakeForShader(SkString(external ? text.c_str() : builtins[i]));
        if (!result.effect || !interfaceValid(result.effect.get(), i)) {
            ALOGE("Borealis shader %s rejected: %s", names[i], result.errorText.c_str());
            return false;
        }
        candidate[i] = std::move(result.effect);
    }
    mEffects = std::move(candidate); mEffectsReady = true; return true;
}
sk_sp<SkSurface> BorealisGraphics::begin(SkiaGpuContext* context, sk_sp<SkSurface> output,
                                        const DisplaySettings& display, bool safe) {
    if (!context || !output) {
        reset(); borealis::reportStatus("allocation_error"); return output;
    }
    const auto generation = borealis::historyGeneration();
    const std::string mode = base::GetProperty("debug.borealis.graphics.mode", "off");
    const int validScale = borealis::compositionScale();
    const int sharpness = borealis::rcasSharpness();
    const bool rcas = borealis::rcasEnabled();
    const bool fg = borealis::frameGenerationEnabled();
    if (!display.borealisEligible) {
        mActive = false;
        if (!borealis::enabled() || !borealis::compositionEligible()) reset();
        return output;
    }
    if (!safe || !borealis::enabled()) {
        reset(); mGeneration = generation;
        if (display.borealisEligible) borealis::reportStatus(!safe ? "bypassed" : "off");
        return output;
    }
    // Bound retained images and offscreen render targets to the A30's 1080p panel.
    // Higher-resolution virtual displays already have false eligibility.
    if (output->width() <= 0 || output->height() <= 0 ||
            uint64_t(output->width()) * output->height() > 3u * 1024u * 1024u) {
        reset(); borealis::reportStatus("allocation_error"); return output;
    }
    // A screenshot / virtual display must not erase or reuse the primary history.
    if (mGeneration != generation || mMode != mode || mScale != validScale ||
        mSharpness != sharpness || mRcas != rcas || mFrameGen != fg ||
        (mHaveDisplay && !(mLastDisplay == display))) reset();
    mGeneration = generation; mMode = mode; mScale = validScale; mSharpness = sharpness;
    mFrameGen = fg; mRcas = rcas;
    mLastDisplay = display; mHaveDisplay = true;
    if (!mEffectsReady && !loadEffects(false)) {
        reset(); borealis::reportStatus("shader_error"); return output;
    }
    const std::string reload = base::GetProperty("debug.borealis.graphics.reload", "");
    if (reload != mReload) {
        mReload = reload;
        if (!reload.empty()) {
            if (loadEffects(reload != "builtin")) {
                mReloadRejected = false;
                reset(); mHaveDisplay = true; mLastDisplay = display;
            } else mReloadRejected = true;
        }
    }
    const int percent = mMode == "fsr1" ? mScale : 100;
    const auto info = output->imageInfo().makeWH(std::max(1, output->width()*percent/100),
                                                std::max(1, output->height()*percent/100));
    auto surface = context->createRenderTarget(info);
    if (!surface) { reset(); borealis::reportStatus("allocation_error"); return output; }
    mActive = true; return surface;
}
sk_sp<SkImage> BorealisGraphics::render(SkiaGpuContext* context, const SkImageInfo& info,
                                      SkRuntimeShaderBuilder& builder) {
    const auto shader = builder.makeShader();
    if (!shader) return nullptr;
    auto surface = context->createRenderTarget(info);
    if (!surface) return nullptr;
    SkPaint paint; paint.setShader(shader); paint.setBlendMode(SkBlendMode::kSrc);
    surface->getCanvas()->drawPaint(paint);
    return surface->makeImageSnapshot();
}
sk_sp<SkImage> BorealisGraphics::spatial(SkiaGpuContext* context, sk_sp<SkImage> image,
                                       const SkImageInfo& info) {
    if (mMode == "fsr1" && (image->width() != info.width() || image->height() != info.height())) {
        SkRuntimeShaderBuilder builder(mEffects[0]);
        builder.child("inputImage") = imageShader(image);
        builder.uniform("inputSize") = std::array<float,2>{float(image->width()), float(image->height())};
        builder.uniform("outputSize") = std::array<float,2>{float(info.width()), float(info.height())};
        image = render(context, info, builder); if (!image) return nullptr;
    }
    if (mRcas) {
        SkRuntimeShaderBuilder builder(mEffects[1]);
        builder.child("inputImage") = imageShader(image);
        builder.uniform("strength") = borealis::rcasStrength(mSharpness);
        image = render(context, info, builder);
    }
    return image;
}
sk_sp<SkImage> BorealisGraphics::interpolate(SkiaGpuContext* context, sk_sp<SkImage> previous,
                                           sk_sp<SkImage> current) {
    // Bounded to ~45k analysis pixels on the A30. No CPU readback of the display.
    const int w = 144, h = std::max(1, current->height()*w/current->width());
    const auto flowInfo = SkImageInfo::Make(w, h, kRGBA_F16_SkColorType, kPremul_SkAlphaType);
    const std::array<float,2> scale{float(current->width())/w, float(current->height())/h};
    sk_sp<SkImage> flow;
    for (int iteration = 0; iteration < 4; ++iteration) {
        SkRuntimeShaderBuilder builder(mEffects[2]);
        builder.child("previousImage") = imageShader(previous, true);
        builder.child("currentImage") = imageShader(current, true);
        builder.child("flowImage") = flow ? imageShader(flow, true, true) : SkShaders::Color(SK_ColorGRAY);
        builder.uniform("imageScale") = scale;
        builder.uniform("hasFlow") = flow ? 1.0f : 0.0f;
        flow = render(context, flowInfo, builder); if (!flow) return nullptr;
    }
    SkRuntimeShaderBuilder builder(mEffects[3]);
    builder.child("previousImage") = imageShader(previous, true);
    builder.child("currentImage") = imageShader(current, true);
    builder.child("flowImage") = imageShader(flow, true, true);
    builder.uniform("imageScale") = scale;
    builder.uniform("imageSize") = std::array<float,2>{float(current->width()),float(current->height())};
    return render(context, current->imageInfo(), builder);
}
void BorealisGraphics::finish(SkiaGpuContext* context, sk_sp<SkSurface> composed,
                              sk_sp<SkSurface> output, const DisplaySettings& display) {
    if (!mActive || composed == output) return;
    // Spatial-only effects need no temporal history or forced next presentation.
    // Release any old FG images before allocating the spatial passes.
    if (!mFrameGen) {
        mPrevious.reset(); mCurrent.reset(); mClock.reset(); mToken = 0;
        borealis::setPendingFrame(false);
        auto image = spatial(context, composed->makeImageSnapshot(), output->imageInfo());
        SkPaint paint; paint.setBlendMode(SkBlendMode::kSrc);
        if (image) {
            output->getCanvas()->drawImage(image, 0, 0, SkSamplingOptions(), &paint);
            borealis::reportStatus(mReloadRejected ? "reload_rejected" : mMode.c_str());
        } else {
            output->getCanvas()->drawImageRect(composed->makeImageSnapshot(),
                    SkRect::MakeWH(output->width(), output->height()),
                    SkSamplingOptions(SkFilterMode::kLinear), &paint);
            reset(); borealis::reportStatus("shader_error");
        }
        return;
    }
    const uint64_t token = display.borealisFrameToken;
    const bool changed = !mCurrent || token != mToken;
    const auto action = mClock.advance(token, systemTime(SYSTEM_TIME_MONOTONIC), mFrameGen);
    if (changed) {
        auto image = spatial(context, composed->makeImageSnapshot(), output->imageInfo());
        if (!image) {
            SkPaint paint; paint.setBlendMode(SkBlendMode::kSrc);
            output->getCanvas()->drawImageRect(composed->makeImageSnapshot(),
                    SkRect::MakeWH(output->width(), output->height()), SkSamplingOptions(SkFilterMode::kLinear), &paint);
            reset(); borealis::reportStatus("shader_error"); return;
        }
        mPrevious = std::move(mCurrent); mCurrent = std::move(image); mToken = token;
    }
    auto presented = mCurrent;
    bool interpolationFailed = false;
    if (action == borealis::FrameAction::Interpolate && mPrevious) {
        ATRACE_NAME("BorealisFG::Midpoint");
        if (auto generated = interpolate(context, mPrevious, mCurrent)) {
            presented = std::move(generated);
        } else {
            mClock.reset(); interpolationFailed = true;
        }
    }
    // Do not perform property-service IPC for every generated/real presentation.
    borealis::reportStatus(interpolationFailed ? "fg_unavailable" :
                          mFrameGen ? "fg_enabled" : mMode.c_str());
    borealis::setPendingFrame(mClock.pending());
    if (mReloadRejected) borealis::reportStatus("reload_rejected");
    SkPaint paint; paint.setBlendMode(SkBlendMode::kSrc);
    output->getCanvas()->drawImage(presented, 0, 0, SkSamplingOptions(), &paint);
}
}
