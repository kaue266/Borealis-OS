// SPDX-License-Identifier: Apache-2.0
#include <renderengine/BorealisGraphics.h>
#include <android-base/properties.h>
#include <mutex>
#include <string>
#include <functional>
#include <algorithm>
#include <cmath>

namespace android::renderengine::borealis {
namespace {
std::atomic_bool pending{false};
std::atomic_uint64_t generation{1};
std::atomic_bool eligible{false};
std::mutex statusMutex;
std::string lastStatus;
}
bool enabled() {
    const auto mode = base::GetProperty("debug.borealis.graphics.mode", "off");
    if (frameGenerationEnabled()) return true;
    return (mode == "fsr1" && compositionScale() < 100) || rcasEnabled();
}
int compositionScale() {
    const int scale = base::GetIntProperty("debug.borealis.graphics.scale", 67);
    switch (scale) {
        case 25: case 33: case 50: case 59: case 67: case 77: case 100: return scale;
        default: return 100;
    }
}
int rcasSharpness() {
    // The RCAS lobe bound assumes strength <= 1. Never feed an extrapolated
    // 250% coefficient into its reciprocal denominator.
    return std::clamp(base::GetIntProperty("debug.borealis.graphics.sharpness", 0), 0, 100);
}
bool rcasEnabled() {
    const auto mode = base::GetProperty("debug.borealis.graphics.mode", "off");
    if (mode != "fsr1" && mode != "rcas") return false;
    // Absent property preserves old callers; explicit false separates EASU
    // from RCAS even if a previously selected sharpness is still stored.
    return base::GetBoolProperty("debug.borealis.graphics.rcas", true) && rcasSharpness() > 0;
}
float rcasStrength(int sharpness) {
    const int bounded = std::clamp(sharpness, 0, 100);
    return bounded == 0 ? 0.0f : std::exp2(-2.0f * (1.0f - bounded / 100.0f));
}
bool frameGenerationEnabled() {
    return base::GetBoolProperty("debug.borealis.graphics.fg", false);
}
bool compositionEligible() { return eligible.load(); }
void setCompositionEligible(bool value) {
    if (eligible.exchange(value) != value) invalidateHistory();
}
uint64_t configurationToken() {
    std::string values;
    for (const char* name : {"mode", "rcas", "fg", "scale", "sharpness", "reload"}) {
        values += base::GetProperty(std::string("debug.borealis.graphics.") + name, "");
        values += '\0';
    }
    return std::hash<std::string>{}(values);
}
bool needsRepaint() { return pending.load(); }
void setPendingFrame(bool value) { pending.store(value); }
void invalidateHistory() { pending.store(false); generation.fetch_add(1); }
uint64_t historyGeneration() { return generation.load(); }
void reportStatus(const char* value) {
    std::lock_guard<std::mutex> lock(statusMutex);
    if (lastStatus != value && base::SetProperty("debug.borealis.graphics.status", value))
        lastStatus = value;
}
}
