// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <atomic>
#include <cstdint>

namespace android::renderengine::borealis {
// SurfaceFlinger and RenderEngine share these in the same process.
bool enabled();
bool frameGenerationEnabled();
bool rcasEnabled();
int compositionScale();
int rcasSharpness();
float rcasStrength(int sharpness);
bool compositionEligible();
void setCompositionEligible(bool eligible);
uint64_t configurationToken();
bool needsRepaint();
void invalidateHistory();
uint64_t historyGeneration();
void setPendingFrame(bool pending);
void reportStatus(const char* status);
}
