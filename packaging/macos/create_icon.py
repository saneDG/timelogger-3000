#!/usr/bin/env python3
"""Generate a simple TimeLogger iconset without external imaging dependencies."""

import binascii
import struct
import subprocess
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ICONSET = ROOT / "TimeLogger.iconset"


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


def png(size: int, path: Path) -> None:
    rows = []
    radius = size * 0.18
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            dx = max(radius - x, 0, x - (size - radius - 1))
            dy = max(radius - y, 0, y - (size - radius - 1))
            inside = dx * dx + dy * dy <= radius * radius
            color = (8, 9, 10, 255) if inside else (0, 0, 0, 0)
            # Compact acid-lime T mark.
            if inside and ((size * .27 <= y <= size * .39 and size * .25 <= x <= size * .75) or (size * .44 <= x <= size * .56 and size * .35 <= y <= size * .76)):
                color = (228, 242, 34, 255)
            row.extend(color)
        rows.append(bytes(row))
    raw = b"".join(rows)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(data)


ICONSET.mkdir(exist_ok=True)
for points in (16, 32, 128, 256, 512):
    png(points, ICONSET / ("icon_%dx%d.png" % (points, points)))
    png(points * 2, ICONSET / ("icon_%dx%d@2x.png" % (points, points)))
subprocess.run(["iconutil", "-c", "icns", str(ICONSET), "-o", str(ROOT / "TimeLogger.icns")], check=True)
