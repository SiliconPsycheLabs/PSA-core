#!/usr/bin/env python3
"""Generate PSA Legal extension icons at 16x16, 48x48, 128x128."""
import struct, zlib, math

def png(width, height, pixels):
    def chunk(name, data):
        c = zlib.crc32(name + data) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', c)

    raw = b''
    for row in pixels:
        raw += b'\x00' + bytes(row)

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw)
    return (
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', ihdr)
        + chunk(b'IDAT', idat)
        + chunk(b'IEND', b'')
    )

def make_icon(size):
    bg    = (28, 30, 38)
    gold  = (184, 165, 106)
    light = (228, 230, 240)

    pixels = []
    cx, cy = size / 2, size / 2
    r = size / 2 - 1

    for y in range(size):
        row = []
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx*dx + dy*dy)

            if dist > r:
                row += [0, 0, 0]       # transparent → black bg outside
            elif dist > r - max(1, size // 16):
                row += list(gold)      # gold border ring
            else:
                # Draw a simple scale of justice symbol scaled to size
                # Base: horizontal beam near 60% height
                beam_y = int(size * 0.42)
                beam_h = max(1, size // 20)
                beam_w = int(size * 0.55)
                beam_x0 = int(cx - beam_w / 2)
                beam_x1 = int(cx + beam_w / 2)

                # Vertical post: center x, from beam down to 80% height
                post_x0 = int(cx - max(1, size // 30))
                post_x1 = int(cx + max(1, size // 30))
                post_y0 = beam_y + beam_h
                post_y1 = int(size * 0.78)

                # Left pan: small circle at left beam end
                lp_cx = beam_x0 + max(1, size // 14)
                lp_cy = beam_y + int(size * 0.14)
                lp_r  = max(1, size // 10)

                # Right pan
                rp_cx = beam_x1 - max(1, size // 14)
                rp_cy = lp_cy
                rp_r  = lp_r

                is_beam  = beam_y <= y <= beam_y + beam_h and beam_x0 <= x <= beam_x1
                is_post  = post_y0 <= y <= post_y1 and post_x0 <= x <= post_x1
                is_lpan  = math.sqrt((x-lp_cx)**2 + (y-lp_cy)**2) < lp_r
                is_rpan  = math.sqrt((x-rp_cx)**2 + (y-rp_cy)**2) < rp_r

                if is_beam or is_post or is_lpan or is_rpan:
                    row += list(gold)
                else:
                    row += list(bg)
        pixels.append(row)

    return png(size, size, pixels)

import os
out = os.path.join(os.path.dirname(__file__), 'icons')
os.makedirs(out, exist_ok=True)

for sz in [16, 48, 128]:
    data = make_icon(sz)
    path = os.path.join(out, f'icon{sz}.png')
    with open(path, 'wb') as f:
        f.write(data)
    print(f'icon{sz}.png written ({len(data)} bytes)')
