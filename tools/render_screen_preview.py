#!/usr/bin/env python3
"""Render actual native C RGB565 framebuffer fixtures as lossless PNGs."""
from pathlib import Path
import struct
import sys
import zlib
root=Path(sys.argv[1])
width,height=428,142
def chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
for path in root.glob('*.rgb565'):
    pixels=struct.unpack('<'+str(width*height)+'H',path.read_bytes())
    data=bytearray()
    for y in range(height):
        data.append(0)
        for value in pixels[y*width:(y+1)*width]:
            data.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(data))+chunk(b'IEND',b'')
    path.with_suffix('.png').write_bytes(png)
print('Rendered actual C framebuffers to PNG:',root)
