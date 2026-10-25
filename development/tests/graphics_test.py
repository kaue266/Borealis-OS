#!/usr/bin/env python3
"""Execute the actual shaders on host Skia. Not a handset FPS benchmark."""
from pathlib import Path
import argparse
import json
import numpy as np
import skia

p=argparse.ArgumentParser();p.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1]/'project')
p.add_argument('--output',type=Path);args=p.parse_args()
shaders=args.project/'vendor/borealis/graphics/shaders'
effects={name:skia.RuntimeEffect.MakeForShader((shaders/(name+'.sksl')).read_text())
         for name in ('easu','rcas','flow','interpolate')}

def image(pixels):
    return skia.Image.fromarray(np.ascontiguousarray(pixels),colorType=skia.ColorType.kRGBA_8888_ColorType,
                               alphaType=skia.AlphaType.kPremul_AlphaType)
def run(name, width, height, children, uniforms, floating=False):
    builder=skia.RuntimeShaderBuilder(effects[name])
    for key,value in children.items():builder.setChild(key,value)
    for key,value in uniforms.items():
        builder.setUniform(key,skia.V2(*value) if isinstance(value,tuple) else float(value))
    info=skia.ImageInfo.Make(width,height,skia.ColorType.kRGBA_F16_ColorType if floating else skia.ColorType.kRGBA_8888_ColorType,
                            skia.AlphaType.kPremul_AlphaType)
    surface=skia.Surface.MakeRaster(info)
    surface.getCanvas().drawPaint(skia.Paint(Shader=builder.makeShader(),BlendMode=skia.BlendMode.kSrc))
    return surface.makeImageSnapshot()
def sample(im,linear=False,raw=False):
    options=skia.SamplingOptions(skia.FilterMode.kLinear if linear else skia.FilterMode.kNearest)
    return im.makeRawShader(options) if raw else im.makeShader(options)
def array(im):return im.toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)

checks=[]
# Flat colors must stay flat and finite, including zero denominators in RCAS.
for color in (0,128,255):
    pixels=np.full((12,12,4),color,dtype=np.uint8);pixels[:,:,3]=255
    source=image(pixels)
    enlarged=run('easu',24,24,{'inputImage':sample(source)}, {'inputSize':(12.,12.),'outputSize':(24.,24.)})
    sharpened=run('rcas',24,24,{'inputImage':sample(enlarged)},{'strength':1.0})
    assert np.max(np.abs(array(sharpened).astype(int)-np.array([color,color,color,255])))<=1
checks.append('EASU and RCAS preserve black, gray and white')
# 25% is a custom 4x-per-axis experiment beyond the usual FSR1 presets.
# Test odd output dimensions as on the A30, not only integer 2x fixtures.
for width,height in ((48,48),(43,93)):
    pixels=np.full((height//4,width//4,4),128,dtype=np.uint8);pixels[:,:,3]=255
    source=image(pixels)
    enlarged=run('easu',width,height,{'inputImage':sample(source)},
                 {'inputSize':(float(source.width()),float(source.height())),
                  'outputSize':(float(width),float(height))})
    assert np.max(np.abs(array(enlarged).astype(int)-np.array([128,128,128,255])))<=1
checks.append('Experimental 25% EASU preserves flat colors at 4x and odd output dimensions')
# EASU edge reconstruction must be different from ordinary bilinear filtering.
pixels=np.zeros((12,12,4),dtype=np.uint8);pixels[:,:,3]=255
for y in range(12):pixels[y,y:,0:3]=255
source=image(pixels)
enlarged=run('easu',24,24,{'inputImage':sample(source)},{'inputSize':(12.,12.),'outputSize':(24.,24.)})
bilinear=skia.Surface(24,24);bilinear.getCanvas().drawImageRect(source,skia.Rect.MakeWH(24,24),skia.SamplingOptions(skia.FilterMode.kLinear))
assert np.max(np.abs(array(enlarged).astype(int)-array(bilinear.makeImageSnapshot()).astype(int)))>8
checks.append('EASU produces edge-adaptive reconstruction beyond bilinear')
# Known translation with textured corners (the aperture problem is avoided).
rng=np.random.default_rng(7)
texture=rng.integers(60,195,(64,64,3),dtype=np.uint8)
# Smooth the fixture so iterative optical flow can linearize the displacement.
for _ in range(3):texture=((texture.astype(float)+np.roll(texture,1,0)+np.roll(texture,-1,0)+np.roll(texture,1,1)+np.roll(texture,-1,1))/5).astype(np.uint8)
old=np.dstack((texture,np.full((64,64),255,dtype=np.uint8)))
new=np.roll(old,2,axis=1)
previous,current=image(old),image(new);flow=None
for iteration in range(4):
    flow=run('flow',64,64,{'previousImage':sample(previous,True),'currentImage':sample(current,True),
         'flowImage':sample(flow,True,True) if flow else skia.Shaders.Color(skia.ColorGRAY)},
         {'imageScale':(1.,1.),'hasFlow':float(flow is not None)},floating=True)
field=flow.toarray(colorType=skia.ColorType.kRGBA_F32_ColorType,alphaType=skia.AlphaType.kPremul_AlphaType)
motion=(field-.5)*16
assert np.isfinite(motion).all()
assert np.median(motion[8:-8,8:-8,0])>0.65, np.median(motion[8:-8,8:-8,0])
assert np.median(motion[8:-8,8:-8,2])<-.65
midpoint=run('interpolate',64,64,{'previousImage':sample(previous,True),'currentImage':sample(current,True),
             'flowImage':sample(flow,True,True)},{'imageScale':(1.,1.),'imageSize':(64.,64.)})
expected=np.roll(old,1,axis=1)
error=np.mean(np.abs(array(midpoint)[8:-8,8:-8,:3].astype(float)-expected[8:-8,8:-8,:3]))
real_error=np.mean(np.abs(new[8:-8,8:-8,:3].astype(float)-expected[8:-8,8:-8,:3]))
assert error<real_error*.85,(error,real_error)
checks.append('Bidirectional optical flow reconstructs a translated midpoint')
# Abrupt cut must use current pixels, not blend unrelated frames.
black=image(np.dstack((np.zeros((16,16,3),np.uint8),np.full((16,16),255,np.uint8))))
white=image(np.full((16,16,4),255,np.uint8))
zero_flow=run('flow',16,16,{'previousImage':sample(black),'currentImage':sample(white),'flowImage':skia.Shaders.Color(skia.ColorGRAY)},
              {'imageScale':(1.,1.),'hasFlow':0.},floating=True)
cut=run('interpolate',16,16,{'previousImage':sample(black),'currentImage':sample(white),'flowImage':sample(zero_flow,True,True)},
        {'imageScale':(1.,1.),'imageSize':(16.,16.)})
assert np.all(array(cut)==255)
checks.append('Scene cuts fall back to the current real frame')
result={'host_skia':skia.__version__,'checks':checks,'midpoint_mean_error':float(error),
        'real_frame_mean_error':float(real_error),'device_tested':False}
if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
