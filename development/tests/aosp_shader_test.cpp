// SPDX-License-Identifier: Apache-2.0
// Compile and execute the same fallback shaders with Android 13's Skia source.
#include "include/core/SkCanvas.h"
#include "include/core/SkSurface.h"
#include "include/core/SkPaint.h"
#include "include/effects/SkRuntimeEffect.h"
#include "BorealisShaders.h"
#include <array>
#include <cassert>
#include <iostream>

int main() {
    const char* texts[] = {kBorealisEasu,kBorealisRcas,kBorealisFlow,kBorealisInterpolate};
    std::array<sk_sp<SkRuntimeEffect>,4> effects;
    for (int i=0;i<4;++i) {
        auto result=SkRuntimeEffect::MakeForShader(SkString(texts[i]));
        if (!result.effect) { std::cerr<<result.errorText.c_str()<<'\n';return 1; }
        effects[i]=result.effect;
    }
    auto input=SkSurface::MakeRasterN32Premul(12,12);
    input->getCanvas()->clear(SkColorSetRGB(128,128,128));
    SkRuntimeShaderBuilder easu(effects[0]);
    easu.child("inputImage")=input->makeImageSnapshot()->makeShader(SkSamplingOptions());
    easu.uniform("inputSize")=std::array<float,2>{12,12};
    easu.uniform("outputSize")=std::array<float,2>{24,24};
    auto enlarged=SkSurface::MakeRasterN32Premul(24,24);
    SkPaint paint;paint.setShader(easu.makeShader());
    enlarged->getCanvas()->drawPaint(paint);
    SkRuntimeShaderBuilder rcas(effects[1]);
    rcas.child("inputImage")=enlarged->makeImageSnapshot()->makeShader(SkSamplingOptions());
    rcas.uniform("strength")=1.0f;
    auto output=SkSurface::MakeRasterN32Premul(24,24);
    paint.setShader(rcas.makeShader());output->getCanvas()->drawPaint(paint);
    std::array<uint32_t,24*24> pixels;
    assert(output->readPixels(SkImageInfo::MakeN32Premul(24,24),pixels.data(),24*4,0,0));
    for (auto color:pixels) assert(SkColorGetR(color)>=127 && SkColorGetR(color)<=129 && SkColorGetA(color)==255);
    std::cout<<"Android 13 Skia: four RuntimeEffects compile; EASU/RCAS execute and preserve gray\n";
}
