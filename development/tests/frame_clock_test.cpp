// SPDX-License-Identifier: Apache-2.0
#include "BorealisFrameClock.h"
#include <cassert>
#include <iostream>
using namespace android::renderengine::borealis;
int main() {
    FrameClock clock;
    assert(clock.advance(1,0,true)==FrameAction::Real);
    assert(clock.advance(2,33333333,true)==FrameAction::Interpolate && clock.pending());
    assert(clock.advance(2,50000000,true)==FrameAction::Real && !clock.pending());
    assert(clock.advance(2,66666666,true)==FrameAction::Hold && !clock.pending());
    assert(clock.advance(3,66666666,true)==FrameAction::Interpolate);
    // New content while the captured real frame is pending must cancel interpolation.
    assert(clock.advance(4,83333333,true)==FrameAction::Real && !clock.pending());
    clock.reset();
    for (int i=0;i<10;++i) assert(clock.advance(i,i*16666666LL,true)==FrameAction::Real);
    clock.reset();
    assert(clock.advance(1,0,false)==FrameAction::Real);
    assert(clock.advance(2,33333333,false)==FrameAction::Real);
    assert(clock.advance(3,1000000000,true)==FrameAction::Real);
    assert(clock.advance(4,500000000,true)==FrameAction::Real);
    std::cout << "Frame cadence, one-shot completion, 60 FPS bypass, disabled, stale and reversed time: passed\n";
}
