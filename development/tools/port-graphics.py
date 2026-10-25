#!/usr/bin/env python3
"""Port the experimental SDR compositor to Android 17's GPU context abstraction.

Does not enable product capability flags until native compilation is validated.
"""
from pathlib import Path
import difflib
import subprocess

package=Path(__file__).resolve().parent.parent
root=Path('/home/android/borealisos-android17')
proof=package/'validation/graphics';proof.mkdir(parents=True,exist_ok=True)

for name in ('BorealisGraphics.h','BorealisGraphics.cpp'):
 file=package/'project/frameworks/native/libs/renderengine/skia'/name
 text=file.read_text().replace('#include <GrDirectContext.h>','#include "compat/SkiaGpuContext.h"')
 text=text.replace('GrDirectContext*','SkiaGpuContext*')
 text=text.replace('SkSurface::MakeRenderTarget(context, SkBudgeted::kYes, info)','context->createRenderTarget(info)')
 file.write_text(text)
 target=root/'frameworks/native/libs/renderengine/skia'/name
 if not target.is_file() or target.read_text()!=text:target.write_text(text)

def edit(name,transform):
 file=root/name;before=file.read_text();after=transform(before)
 if before!=after:file.write_text(after)
 repository=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=file.parent,text=True).strip())
 original=subprocess.check_output(['git','show','HEAD:'+str(file.relative_to(repository))],cwd=repository,text=True)
 (proof/(name.replace('/','__')+'.patch')).write_text(''.join(difflib.unified_diff(original.splitlines(True),after.splitlines(True),fromfile='a/'+name,tofile='b/'+name)))

def insert(text,anchor,extra):
 if extra.strip() in text:return text
 assert text.count(anchor)==1,f'Android 17 anchor changed: {anchor}'
 return text.replace(anchor,anchor+extra,1)

edit('frameworks/native/libs/renderengine/include/renderengine/DisplaySettings.h',lambda s:insert(s,
 '    Rect physicalDisplay = Rect::INVALID_RECT;',
 '\n\n    // Screenshots and virtual outputs retain default-false eligibility.\n    bool borealisEligible = false;\n    uint64_t borealisFrameToken = 0;'))
edit('frameworks/native/libs/renderengine/Android.bp',lambda s:insert(s,
 '        "skia/SkiaRenderEngine.cpp",','\n        "skia/BorealisGraphics.cpp",\n        "skia/BorealisGraphicsState.cpp",'))
edit('frameworks/native/libs/renderengine/skia/SkiaRenderEngine.h',lambda s:insert(insert(s,
 '#include "compat/SkiaGpuContext.h"','\n#include "BorealisGraphics.h"'),
 '    StretchShaderFactory mStretchShaderFactory = StretchShaderFactory(mRuntimeEffectManager);',
 '\n    BorealisGraphics mBorealisGraphics;'))

def render(text):
 text=insert(text,'#include "SkiaRenderEngine.h"','\n#include <renderengine/BorealisGraphics.h>')
 text=insert(text,'namespace skia {\n\nnamespace {','''

// Keep HDR and extended-range content on the normal composition path.
static bool isHdrDataspace(ui::Dataspace dataspace) {
    const auto transfer = dataspace & HAL_DATASPACE_TRANSFER_MASK;
    const auto range = dataspace & HAL_DATASPACE_RANGE_MASK;
    return transfer == HAL_DATASPACE_TRANSFER_ST2084 ||
            transfer == HAL_DATASPACE_TRANSFER_HLG || range == HAL_DATASPACE_RANGE_EXTENDED;
}
''')
 text=insert(text,'    mTextureCleanupMgr.setDeferredStatus(false);','\n    mBorealisGraphics.reset();')
 cleanup='''    mTextureCleanupMgr.cleanup();

    // Check each context's cache management policy'''
 replacement='''    mTextureCleanupMgr.cleanup();
    if (!borealis::enabled()) mBorealisGraphics.reset();

    // Check each context's cache management policy'''
 if replacement not in text and 'if (!borealis::enabled() || !borealis::compositionEligible()) mBorealisGraphics.reset();' not in text:
  assert text.count(cleanup)==1
  text=text.replace(cleanup,replacement,1)
 text=text.replace('    return mTextureCleanupMgr.isEmpty();',
  '    return mTextureCleanupMgr.isEmpty() &&\n            (!mBorealisGraphics.hasHistory() || borealis::enabled());',1)
 if '// Borealis Android 17 SDR composition.' in text:return text
 anchor='    SkCanvas* dstCanvas = mCapture->tryCapture(dstSurface.get());'
 assert text.count(anchor)==1
 extra='''    // Borealis Android 17 SDR composition. Protected/HDR/effect/capture frames bypass it.
    const auto borealisOutput = dstSurface;
    const bool borealisSafe = !mInProtectedContext && !mCapture->isCaptureRunning() &&
            !isHdrDataspace(display.outputDataspace) &&
            std::none_of(layers.begin(), layers.end(), [](const auto& layer) {
                return isHdrDataspace(layer.sourceDataspace) || layer.backgroundBlurRadius > 0 ||
                        !layer.blurRegions.empty() || layer.postProcessEffect ||
                        (layer.source.buffer.buffer &&
                         (layer.source.buffer.buffer->getBuffer()->getUsage() & GRALLOC_USAGE_PROTECTED));
            });
    dstSurface = mBorealisGraphics.begin(context, dstSurface, display, borealisSafe);
'''
 text=text.replace(anchor,extra+'\n'+anchor,1)
 anchor='    canvas->clear(SK_ColorTRANSPARENT);\n    initCanvas(canvas, display);'
 assert text.count(anchor)==1
 text=text.replace(anchor,'''    canvas->clear(SK_ColorTRANSPARENT);
    canvas->scale(float(dstSurface->width()) / borealisOutput->width(),
                  float(dstSurface->height()) / borealisOutput->height());
    initCanvas(canvas, display);''',1)
 anchor='    surfaceAutoSaveRestore.restore();\n    mCapture->endCapture();'
 assert text.count(anchor)==1
 return text.replace(anchor,'''    surfaceAutoSaveRestore.restore();
    mBorealisGraphics.finish(context, dstSurface, borealisOutput, display);
    dstSurface = borealisOutput;
    activeSurface = dstSurface;
    mCapture->endCapture();''',1)
edit('frameworks/native/libs/renderengine/skia/SkiaRenderEngine.cpp',render)

def output_header(text):
 if 'mBorealisGraphicsActive' in text:return text
 pos=text.rfind('\n};');assert pos>0
 return text[:pos]+'\n    bool mBorealisGraphicsActive = false;\n'+text[pos:]
edit('frameworks/native/services/surfaceflinger/CompositionEngine/include/compositionengine/impl/Output.h',output_header)

def output(text):
 text=insert(text,'#include <renderengine/DisplaySettings.h>','\n#include <renderengine/BorealisGraphics.h>\n#include <sstream>')
 if '// Borealis Android 17 output eligibility.' in text:return text
 anchor='    mLayerRequestingBackgroundBlur = findLayerRequestingBackgroundComposition();'
 extra='''    // Borealis Android 17 output eligibility. Never move secure outputs to this path.
    const bool internal = getState().layerFilter.toInternalDisplay;
    bool compatible = internal;
    for (const auto* layer : getOutputLayersOrderedByZ()) {
        const auto* state = layer->getLayerFE().getCompositionState();
        if (state && (state->isSecure || state->hasProtectedContent ||
                state->backgroundBlurRadius > 0 ||
                (state->dataspace & HAL_DATASPACE_TRANSFER_MASK) == HAL_DATASPACE_TRANSFER_ST2084 ||
                (state->dataspace & HAL_DATASPACE_TRANSFER_MASK) == HAL_DATASPACE_TRANSFER_HLG))
            compatible = false;
    }
    const bool wasBorealisActive = mBorealisGraphicsActive;
    mBorealisGraphicsActive = compatible && renderengine::borealis::enabled();
    const bool borealisChanged = wasBorealisActive != mBorealisGraphicsActive;
    if (internal && (!compatible || borealisChanged)) renderengine::borealis::invalidateHistory();
    if (internal && !compatible && renderengine::borealis::enabled())
        renderengine::borealis::reportStatus("bypassed");
    if (internal && !renderengine::borealis::enabled()) renderengine::borealis::reportStatus("off");
    if (mBorealisGraphicsActive || wasBorealisActive)
        editState().dirtyRegion.set(getState().layerStackSpace.getContent());

'''
 assert text.count(anchor)==1;text=text.replace(anchor,extra+anchor,1)
 text=text.replace('layer->updateCompositionState(refreshArgs.updatingGeometryThisFrame,',
   'layer->updateCompositionState(refreshArgs.updatingGeometryThisFrame || borealisChanged,',1)
 text=text.replace('layerForceClientComposition || forceClientComposition,',
   'layerForceClientComposition || forceClientComposition || mBorealisGraphicsActive,',1)
 anchor='    appendRegionFlashRequests(debugRegion, clientCompositionLayers);'
 text=insert(text,anchor,'''
    clientCompositionDisplay.borealisEligible = mBorealisGraphicsActive;
    if (mBorealisGraphicsActive) {
        std::ostringstream frame;
        for (const auto& layer : clientCompositionLayers) PrintTo(layer, &frame);
        clientCompositionDisplay.borealisFrameToken = std::hash<std::string>{}(frame.str());
    }
''')
 return text.replace('    if (mClientCompositionRequestCache) {\n        if (mClientCompositionRequestCache->exists(',
                     '    if (mClientCompositionRequestCache && !mBorealisGraphicsActive) {\n        if (mClientCompositionRequestCache->exists(',1)
edit('frameworks/native/services/surfaceflinger/CompositionEngine/src/Output.cpp',output)

# Do not replace hardware composition to run an optional effect. Its previous
# force-GPU path increased work on the A30 during the user's Android 13 test.
def efficient_display(text):
 text=insert(text,'    uint64_t borealisFrameToken = 0;',
  '\n    uint64_t borealisConfigToken = 0;')
 return insert(text,'    return lhs.namePlusId == rhs.namePlusId &&',
  '\n            lhs.borealisEligible == rhs.borealisEligible &&\n            lhs.borealisConfigToken == rhs.borealisConfigToken &&')
edit('frameworks/native/libs/renderengine/include/renderengine/DisplaySettings.h',efficient_display)
edit('frameworks/native/services/surfaceflinger/CompositionEngine/include/compositionengine/impl/Output.h',
 lambda text:insert(text,'    bool mBorealisGraphicsActive = false;',
  '\n    uint64_t mBorealisConfigToken = 0;'))

def efficient_output(text):
 text=text.replace('layerForceClientComposition || forceClientComposition || mBorealisGraphicsActive,',
                   'layerForceClientComposition || forceClientComposition,')
 text=text.replace('    if (mBorealisGraphicsActive || wasBorealisActive)',
                   '    if (borealisChanged)')
 old='    const bool borealisChanged = wasBorealisActive != mBorealisGraphicsActive;'
 new='''    const auto borealisConfig = renderengine::borealis::configurationToken();
    const bool borealisChanged = wasBorealisActive != mBorealisGraphicsActive ||
            ((mBorealisGraphicsActive || wasBorealisActive) &&
             mBorealisConfigToken != borealisConfig);
    mBorealisConfigToken = borealisConfig;'''
 if new not in text:
  previous='''    const auto borealisConfig = renderengine::borealis::configurationToken();
    const bool borealisChanged = wasBorealisActive != mBorealisGraphicsActive ||
            mBorealisConfigToken != borealisConfig;
    mBorealisConfigToken = borealisConfig;'''
  if previous in text:text=text.replace(previous,new,1)
  else:
   assert text.count(old)==1
   text=text.replace(old,new,1)
 anchor='    if (!hasClientComposition) {'
 extra='''    // Borealis keeps the HWC decision. Mixed/device-composed frames bypass effects.
    const bool borealisEligible = mBorealisGraphicsActive &&
            outputState.usesClientComposition && !outputState.usesDeviceComposition;
    if (outputState.layerFilter.toInternalDisplay) {
        renderengine::borealis::setCompositionEligible(borealisEligible);
        if (renderengine::borealis::enabled() && !borealisEligible)
            renderengine::borealis::reportStatus("hwc_bypass");
    }
'''
 if extra.strip() not in text:
  assert text.count(anchor)==1
  text=text.replace(anchor,extra+anchor,1)
 text=text.replace('clientCompositionDisplay.borealisEligible = mBorealisGraphicsActive;',
                   'clientCompositionDisplay.borealisEligible = borealisEligible;\n    clientCompositionDisplay.borealisConfigToken = mBorealisConfigToken;')
 text=text.replace('    if (mBorealisGraphicsActive) {\n        std::ostringstream frame;',
                   '    if (borealisEligible && renderengine::borealis::frameGenerationEnabled()) {\n        std::ostringstream frame;')
 text=text.replace('    if (mClientCompositionRequestCache && !mBorealisGraphicsActive) {',
                   '    if (mClientCompositionRequestCache &&\n            !(borealisEligible && renderengine::borealis::frameGenerationEnabled())) {')
 return text
edit('frameworks/native/services/surfaceflinger/CompositionEngine/src/Output.cpp',efficient_output)
edit('frameworks/native/libs/renderengine/skia/SkiaRenderEngine.cpp',lambda text:
 text.replace('if (!borealis::enabled()) mBorealisGraphics.reset();',
              'if (!borealis::enabled() || !borealis::compositionEligible()) mBorealisGraphics.reset();')
 .replace('(!mBorealisGraphics.hasHistory() || borealis::enabled());',
          '(!mBorealisGraphics.hasHistory() ||\n             (borealis::enabled() && borealis::compositionEligible()));'))
edit('frameworks/native/services/surfaceflinger/SurfaceFlinger.cpp',lambda s:insert(insert(s,
 '#include "SurfaceFlinger.h"','\n#include <renderengine/BorealisGraphics.h>'),
 '    mCompositionEngine->present(refreshArgs);',
 '\n    // Borealis: request one real presentation after an interpolated midpoint.\n    if (renderengine::borealis::needsRepaint()) scheduleComposite(FrameHint::kNone);'))

def append(text,extra):return text if extra.strip() in text else text.rstrip()+'\n\n'+extra
edit('system/sepolicy/private/property_contexts',lambda s:append(s,'''# Borealis graphics controls are transient.
debug.borealis.graphics.status u:object_r:borealis_graphics_status_prop:s0 exact string
debug.borealis.graphics. u:object_r:borealis_graphics_config_prop:s0 prefix
'''))
edit('system/sepolicy/private/file_contexts',lambda s:append(s,
 r'/data/misc/borealis-graphics(/.*)? u:object_r:borealis_graphics_data_file:s0'+'\n'))
print('Android 17 graphics source hooks installed. Native compile and protected-content runtime tests pending.')
