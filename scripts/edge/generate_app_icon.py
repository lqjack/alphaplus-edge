#!/usr/bin/env python3
"""Generate a 1024x1024 PNG app icon for AlphaPlus Edge (stdlib only)."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, rgba_rows: list[bytes]) -> None:
    raw = b"".join(b"\x00" + row for row in rgba_rows)
    compressed = zlib.compress(raw, 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", compressed) + _chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def main() -> None:
    size = 1024
    rows: list[bytes] = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            # Dark slate background + green bridge accent bar
            cx, cy = size // 2, size // 2
            dx, dy = abs(x - cx), abs(y - cy)
            in_circle = dx * dx + dy * dy <= (size * 0.42) ** 2
            in_bar = abs(x - cx) < size * 0.28 and abs(y - cy) < size * 0.06
            if in_bar:
                r, g, b, a = 16, 185, 129, 255
            elif in_circle:
                r, g, b, a = 17, 24, 39, 255
            else:
                r, g, b, a = 243, 245, 248, 255
            row.extend((r, g, b, a))
        rows.append(bytes(row))

    out = Path(__file__).resolve().parents[2] / "edge-desktop" / "app-icon.png"
    write_png(out, size, size, rows)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
