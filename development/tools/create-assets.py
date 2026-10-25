#!/usr/bin/env python3
"""Generate original Borealis vector geometry and fullscreen boot frames."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib
import io
import json
import math
import zipfile

root = Path(__file__).resolve().parent.parent
vendor = root / 'project/vendor/borealis'
design = root / 'design'
width, height = 1080, 2340
font = ImageFont.truetype(str(vendor / 'fonts/BorealisOrbit-Regular.ttf'), 100)
small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 23)
base = Image.new('RGB', (width, height), '#090D15')
pixels = base.load()
for y in range(height):
    for x in range(width):
        purple = math.exp(-((x - 190) / 530) ** 2 - ((y - 1020) / 610) ** 2)
        green = math.exp(-((x - 990) / 550) ** 2 - ((y - 1590) / 630) ** 2)
        pixels[x,y] = (int(9+24*purple+2*green), int(13+15*purple+22*green), int(21+40*purple+17*green))
draw = ImageDraw.Draw(base)
curves = []
for layer in range(16):
    points = []
    for x in range(-80, width + 81, 8):
        y = 790 + layer*33 + 155*math.sin(x/440 + layer*.035) + x*.37
        points.append((x, y))
    color = (44+layer*2, 47+layer*2, 77+layer*2)
    draw.line(points, fill=color, width=2)
    curves.append('M'+' L'.join(f'{x},{y:.1f}' for x,y in points))
svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 2340"><rect width="1080" height="2340" fill="#090D15"/>'
svg += ''.join(f'<path d="{p}" fill="none" stroke="#735E9A" stroke-opacity=".22" stroke-width="2"/>' for p in curves)
svg += '</svg>'
design.mkdir(exist_ok=True)
(design / 'aurora-wallpaper.svg').write_text(svg)
for target in (
        vendor / 'apps/BorealisSpace/res/drawable-nodpi/cosmic_wallpaper.png',
        vendor / 'overlay/base/frameworks/base/core/res/res/drawable-nodpi/default_wallpaper.png'):
    target.parent.mkdir(parents=True, exist_ok=True)
    base.save(target, optimize=True)

def boot_frame(progress):
    # A stable full-screen field; motion is confined to the small orbit mark.
    image = Image.new('RGB', (width, height), '#090D15')
    d = ImageDraw.Draw(image)
    intensity = min(1, progress * 2)
    violet = tuple(int(a*intensity) for a in (197,180,255))
    aurora = tuple(int(a*intensity) for a in (139,232,208))
    cx, cy = width // 2, height // 2 - 105
    d.ellipse((cx-71,cy-71,cx+71,cy+71), outline=violet, width=4)
    d.arc((cx-106,cy-40,cx+106,cy+40), 15, 220, fill=aurora, width=5)
    d.ellipse((cx+51,cy-63,cx+66,cy-48), fill=aurora)
    title = 'BorealisOS'
    box = d.textbbox((0,0), title, font=font)
    d.text(((width-(box[2]-box[0]))/2,cy+123),title,font=font,fill=violet)
    caption = 'UM NOVO HORIZONTE'
    box = d.textbbox((0,0),caption,font=small)
    d.text(((width-(box[2]-box[0]))/2,cy+274),caption,font=small,fill=(154,169,192))
    return image

target = vendor / 'media/bootanimation.zip'
with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_STORED) as archive:
    archive.writestr('desc.txt','1080 2340 24\np 1 0 part0\np 0 24 part1\n')
    for i in range(24):
        stream=io.BytesIO();boot_frame(i/23).save(stream,format='PNG',optimize=True)
        archive.writestr(f'part0/{i:04}.png',stream.getvalue())
    stream=io.BytesIO();boot_frame(1).save(stream,format='PNG',optimize=True)
    archive.writestr('part1/0000.png',stream.getvalue())
    assert archive.testzip() is None
boot_frame(1).save(design / 'bootanimation-preview.png')
validation = root / 'validation';validation.mkdir(exist_ok=True)
(validation / 'assets.json').write_text(json.dumps({
    'generated_original_artwork': True, 'dimensions': [width,height],
    'boot_fps': 24, 'boot_frames': 25,
    'bootanimation_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    'zip_crc_verified': True},indent=2)+'\n')
print('Original wallpaper and 1080x2340 fullscreen bootanimation generated.')
