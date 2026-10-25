// SPDX-License-Identifier: Apache-2.0
#include <renderengine/BorealisGraphics.h>
#include <android-base/properties.h>
#include <cassert>
#include <iostream>
#include <cmath>
#include <limits>
using namespace android::renderengine::borealis;
using android::base::SetProperty;
int main() {
 assert(!enabled());
 assert(!compositionEligible());
 SetProperty("debug.borealis.graphics.mode", "rcas");
 assert(!enabled()); // A zero-strength filter must not allocate a GPU pass.
 SetProperty("debug.borealis.graphics.sharpness", "25");
 assert(enabled());
 assert(rcasEnabled()); // Compatibility with callers predating the RCAS flag.
 SetProperty("debug.borealis.graphics.rcas", "0");
 assert(!enabled());
 SetProperty("debug.borealis.graphics.mode", "fsr1");
 SetProperty("debug.borealis.graphics.scale", "25");
 assert(enabled() && !rcasEnabled() && compositionScale()==25);
 SetProperty("debug.borealis.graphics.scale", "33");
 assert(enabled() && compositionScale()==33);
 SetProperty("debug.borealis.graphics.scale", "100");
 assert(!enabled()); // Stored sharpness does not turn on RCAS with EASU.
 auto rcasConfig=configurationToken();
 SetProperty("debug.borealis.graphics.rcas", "1");
 assert(enabled() && rcasEnabled() && configurationToken()!=rcasConfig);
 SetProperty("debug.borealis.graphics.mode", "rcas");
 assert(enabled()); // RCAS works without EASU/downscale.
 for (int strength : {-1, 0, 25, 50, 75, 100, 250, std::numeric_limits<int>::max()}) {
     SetProperty("debug.borealis.graphics.sharpness", std::to_string(strength));
     const float coefficient=rcasStrength(strength);
     assert(std::isfinite(coefficient) && coefficient>=0.0f && coefficient<=1.0f);
     // Four taps at the worst lobe must retain a positive denominator.
     assert(1.0f - 4.0f*0.1875f*coefficient >= 0.25f);
     assert(rcasSharpness()>=0 && rcasSharpness()<=100);
 }
 SetProperty("debug.borealis.graphics.mode", "unknown");
 assert(!enabled());
 SetProperty("debug.borealis.graphics.sharpness", "0");
 SetProperty("debug.borealis.graphics.mode", "fsr1");
 SetProperty("debug.borealis.graphics.scale", "67");
 assert(enabled());
 SetProperty("debug.borealis.graphics.scale", "100");
 assert(!enabled()); // Native size + no sharpness is the ordinary composition.
 SetProperty("debug.borealis.graphics.scale", "invalid");
 assert(enabled()); // Malformed value uses the explicit safe default, 67.
 SetProperty("debug.borealis.graphics.scale", "0");
 assert(!enabled()); // Numeric unsupported scale fails back to native size.
 SetProperty("debug.borealis.graphics.scale", "67");
 assert(enabled());
 auto config=configurationToken();
 assert(configurationToken()==config);
 reportStatus("fsr1");
 assert(configurationToken()==config); // Status IPC must not invalidate itself.
 SetProperty("debug.borealis.graphics.reload", "builtin");
 assert(configurationToken()!=config);
 auto history=historyGeneration();
 setPendingFrame(true);
 setCompositionEligible(true);
 assert(compositionEligible() && !needsRepaint() && historyGeneration()>history);
 history=historyGeneration();
 setCompositionEligible(true);
 assert(historyGeneration()==history);
 setPendingFrame(true);
 setCompositionEligible(false); // HWC or a protected frame cancels pending FG.
 assert(!compositionEligible() && !needsRepaint() && historyGeneration()>history);
 SetProperty("debug.borealis.graphics.mode", "off");
 SetProperty("debug.borealis.graphics.fg", "1");
 assert(enabled());
 SetProperty("debug.borealis.graphics.fg", "0");
 assert(!enabled());
 std::cout << "Graphics runtime controls and HWC history transitions passed.\n";
}
