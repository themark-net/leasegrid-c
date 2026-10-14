"""Read the text out of a QR PNG.

Independent of segno: it samples the modules in the image and walks the QR
bit stream. Used to prove a share code is the payload a camera would see.
Versions 1–10, the range a short invite code or a modest join link needs.
"""

from __future__ import annotations

import os
import struct
import sys
import zlib
from pathlib import Path

# ISO/IEC 18004 Table C.1, same order segno uses: M, L, H, Q; mask 0–7 in each.
_FORMAT_INFO = (
    0x5412, 0x5125, 0x5E7C, 0x5B4B, 0x45F9, 0x40CE, 0x4F97, 0x4AA0,
    0x77C4, 0x72F3, 0x7DAA, 0x789D, 0x662F, 0x6318, 0x6C41, 0x6976,
    0x1689, 0x13BE, 0x1CE7, 0x19D0, 0x0762, 0x0255, 0x0D0C, 0x083B,
    0x355F, 0x3068, 0x3F31, 0x3A06, 0x24B4, 0x2183, 0x2EDA, 0x2BED,
)
_LEVEL_BY_GROUP = ("M", "L", "H", "Q")

# (nblocks, data codewords, total codewords) per group. ISO/IEC 18004 Table 9.
_ECC = {
    1: {"L": ((1, 19, 26),), "M": ((1, 16, 26),), "Q": ((1, 13, 26),), "H": ((1, 9, 26),)},
    2: {"L": ((1, 34, 44),), "M": ((1, 28, 44),), "Q": ((1, 22, 44),), "H": ((1, 16, 44),)},
    3: {"L": ((1, 55, 70),), "M": ((1, 44, 70),), "Q": ((2, 17, 35),), "H": ((2, 13, 35),)},
    4: {"L": ((1, 80, 100),), "M": ((2, 32, 50),), "Q": ((2, 24, 50),), "H": ((4, 9, 25),)},
    5: {
        "L": ((1, 108, 134),),
        "M": ((2, 43, 67),),
        "Q": ((2, 15, 33), (2, 16, 34)),
        "H": ((2, 11, 33), (2, 12, 34)),
    },
    6: {"L": ((2, 68, 86),), "M": ((4, 27, 43),), "Q": ((4, 19, 43),), "H": ((4, 15, 43),)},
    7: {
        "L": ((2, 78, 98),),
        "M": ((4, 31, 49),),
        "Q": ((2, 14, 32), (4, 15, 33)),
        "H": ((4, 13, 39), (1, 14, 40)),
    },
    8: {
        "L": ((2, 97, 121),),
        "M": ((2, 38, 60), (2, 39, 61)),
        "Q": ((4, 18, 40), (2, 19, 41)),
        "H": ((4, 14, 40), (2, 15, 41)),
    },
    9: {
        "L": ((2, 116, 146),),
        "M": ((3, 36, 58), (2, 37, 59)),
        "Q": ((4, 16, 36), (4, 17, 37)),
        "H": ((4, 12, 36), (4, 13, 37)),
    },
    10: {
        "L": ((2, 68, 86), (2, 69, 87)),
        "M": ((4, 43, 69), (1, 44, 70)),
        "Q": ((6, 19, 43), (2, 20, 44)),
        "H": ((6, 15, 43), (2, 16, 44)),
    },
}

_ALIGN = {
    2: (6, 18),
    3: (6, 22),
    4: (6, 26),
    5: (6, 30),
    6: (6, 34),
    7: (6, 22, 38),
    8: (6, 24, 42),
    9: (6, 26, 46),
    10: (6, 28, 50),
}

_ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"


def decode_qr_png(png: bytes) -> str:
    """Return the text encoded in a QR code PNG."""
    modules = _modules_from_png(png)
    version = _version(len(modules))
    level, mask = _format(modules)
    groups = _ECC[version][level]
    reserved = _reserved(version)
    raw = _read_codewords(modules, reserved, mask, _codeword_count(groups))
    return _parse_payload(_data_codewords(raw, groups), version)


def _version(n: int) -> int:
    if n < 21 or (n - 21) % 4:
        raise ValueError("not a QR symbol (%sx%s)" % (n, n))
    version = (n - 21) // 4 + 1
    if version not in _ECC:
        raise ValueError("QR version %s is outside the invite decoder" % version)
    return version


def _format(modules: list[list[int]]) -> tuple[str, int]:
    bits = 0
    for i, col in enumerate((0, 1, 2, 3, 4, 5, 7, 8)):
        if modules[8][col]:
            bits |= 1 << (14 - i)
    for i, row in enumerate((0, 1, 2, 3, 4, 5, 7)):
        if modules[row][8]:
            bits |= 1 << i
    try:
        idx = _FORMAT_INFO.index(bits)
    except ValueError as exc:
        raise ValueError("QR format info is not a known pattern") from exc
    return _LEVEL_BY_GROUP[idx // 8], idx % 8


def _reserved(version: int) -> list[list[bool]]:
    n = 21 + (version - 1) * 4
    mark = [[False] * n for _ in range(n)]

    def box(r0: int, c0: int, h: int, w: int) -> None:
        for r in range(r0, r0 + h):
            for c in range(c0, c0 + w):
                if 0 <= r < n and 0 <= c < n:
                    mark[r][c] = True

    box(0, 0, 8, 8)
    box(0, n - 8, 8, 8)
    box(n - 8, 0, 8, 8)
    for i in range(n):
        mark[6][i] = True
        mark[i][6] = True
    for i in range(9):
        mark[8][i] = True
        mark[i][8] = True
    for i in range(8):
        mark[8][n - 1 - i] = True
        mark[n - 1 - i][8] = True
    positions = _ALIGN.get(version, ())
    finder_centers = set()
    if positions:
        lo, hi = positions[0], positions[-1]
        finder_centers = {(lo, lo), (lo, hi), (hi, lo)}
    for r in positions:
        for c in positions:
            if (r, c) in finder_centers:
                continue
            box(r - 2, c - 2, 5, 5)
    if version >= 7:
        for i in range(6):
            for row in (n - 11, n - 10, n - 9):
                mark[row][i] = True
                mark[i][row] = True
    return mark


def _mask_flip(mask: int, row: int, col: int) -> bool:
    if mask == 0:
        return (row + col) % 2 == 0
    if mask == 1:
        return row % 2 == 0
    if mask == 2:
        return col % 3 == 0
    if mask == 3:
        return (row + col) % 3 == 0
    if mask == 4:
        return (row // 2 + col // 3) % 2 == 0
    if mask == 5:
        return (row * col) % 2 + (row * col) % 3 == 0
    if mask == 6:
        return ((row * col) % 2 + (row * col) % 3) % 2 == 0
    return ((row + col) % 2 + (row * col) % 3) % 2 == 0


def _read_codewords(
    modules: list[list[int]], reserved: list[list[bool]], mask: int, count: int
) -> bytes:
    n = len(modules)
    bits: list[int] = []
    for right in range(n - 1, 0, -2):
        if right <= 6:
            right -= 1
        for vertical in range(n):
            for z in range(2):
                col = right - z
                upwards = ((right & 2) == 0) ^ (col < 6)
                row = (n - 1 - vertical) if upwards else vertical
                if reserved[row][col]:
                    continue
                bit = modules[row][col]
                if _mask_flip(mask, row, col):
                    bit ^= 1
                bits.append(bit)
    need = count * 8
    if len(bits) < need:
        raise ValueError("QR data stream is short (%s bits, need %s)" % (len(bits), need))
    out = bytearray()
    for i in range(0, need, 8):
        value = 0
        for bit in bits[i:i + 8]:
            value = (value << 1) | bit
        out.append(value)
    return bytes(out)


def _codeword_count(groups: tuple) -> int:
    return sum(nblocks * total for nblocks, _data, total in groups)


def _data_codewords(raw: bytes, groups: tuple) -> bytes:
    needs: list[int] = []
    for nblocks, ndata, _total in groups:
        needs.extend([ndata] * nblocks)
    parts = [bytearray() for _ in needs]
    pos = 0
    for col in range(max(needs) if needs else 0):
        for i, need in enumerate(needs):
            if col < need:
                parts[i].append(raw[pos])
                pos += 1
    return b"".join(parts)


class _Bits:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.i = 0
        self.n = len(data) * 8

    def left(self) -> int:
        return self.n - self.i

    def read(self, k: int) -> int:
        if self.i + k > self.n:
            raise ValueError("QR payload ended early")
        value = 0
        for _ in range(k):
            bit = (self.data[self.i // 8] >> (7 - (self.i % 8))) & 1
            value = (value << 1) | bit
            self.i += 1
        return value


def _parse_payload(data: bytes, version: int) -> str:
    bits = _Bits(data)
    chunks: list[str] = []
    count_wide = version >= 10
    while bits.left() >= 4:
        mode = bits.read(4)
        if mode == 0:
            break
        if mode == 0b0100:
            count = bits.read(16 if count_wide else 8)
            raw = bytes(bits.read(8) for _ in range(count))
            chunks.append(raw.decode("utf-8"))
        elif mode == 0b0010:
            count = bits.read(11 if count_wide else 9)
            chars: list[str] = []
            while count >= 2:
                value = bits.read(11)
                chars.append(_ALNUM[value // 45])
                chars.append(_ALNUM[value % 45])
                count -= 2
            if count:
                chars.append(_ALNUM[bits.read(6)])
            chunks.append("".join(chars))
        elif mode == 0b0001:
            count = bits.read(12 if count_wide else 10)
            digits: list[str] = []
            while count >= 3:
                digits.append("%03d" % bits.read(10))
                count -= 3
            if count == 2:
                digits.append("%02d" % bits.read(7))
            elif count == 1:
                digits.append("%d" % bits.read(4))
            chunks.append("".join(digits))
        else:
            raise ValueError("unsupported QR mode %s" % mode)
    if not chunks:
        raise ValueError("QR has no payload")
    return "".join(chunks)


def _modules_from_png(png: bytes) -> list[list[int]]:
    pixels, width, height = _png_gray(png)
    if width != height:
        raise ValueError("QR image is not square")
    y0 = 0
    while y0 < height and not any(pixels[y0]):
        y0 += 1
    if y0 >= height:
        raise ValueError("QR image is blank")
    x0 = 0
    while x0 < width and not pixels[y0][x0]:
        x0 += 1
    run = 0
    while x0 + run < width and pixels[y0][x0 + run]:
        run += 1
    if run < 7 or run % 7:
        raise ValueError("QR finder is not on a whole-pixel grid")
    scale = run // 7
    if (width - 2 * x0) % scale or (height - 2 * y0) % scale:
        raise ValueError("QR quiet zone is not a whole number of modules")
    n = (width - 2 * x0) // scale
    if n != (height - 2 * y0) // scale:
        raise ValueError("QR module grid is not square")
    modules: list[list[int]] = []
    half = scale // 2
    for r in range(n):
        y = y0 + r * scale + half
        modules.append([1 if pixels[y][x0 + c * scale + half] else 0 for c in range(n)])
    return modules


def _png_gray(png: bytes) -> tuple[list[list[int]], int, int]:
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not a PNG")
    i = 8
    width = height = bit_depth = color_type = None
    idat = bytearray()
    while i + 8 <= len(png):
        length = struct.unpack(">I", png[i:i + 4])[0]
        kind = png[i + 4:i + 8]
        chunk = png[i + 8:i + 8 + length]
        i += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filt, inter = struct.unpack(
                ">IIBBBBB", chunk
            )
            if inter:
                raise ValueError("interlaced PNG")
        elif kind == b"IDAT":
            idat.extend(chunk)
        elif kind == b"IEND":
            break
    if width is None or not idat or bit_depth is None or color_type is None:
        raise ValueError("truncated PNG")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if channels is None or bit_depth not in (1, 8):
        raise ValueError("unsupported PNG color")
    bpp = max(1, channels * bit_depth // 8)
    raw = zlib.decompress(bytes(idat))
    row_bytes = (width * channels * bit_depth + 7) // 8
    rows: list[bytearray] = []
    pos = 0
    prev = bytearray(row_bytes)
    for _ in range(height):
        filt = raw[pos]
        pos += 1
        row = bytearray(raw[pos:pos + row_bytes])
        pos += row_bytes
        cur = bytearray(row_bytes)
        for x, value in enumerate(row):
            left = cur[x - bpp] if x >= bpp else 0
            up = prev[x]
            ul = prev[x - bpp] if x >= bpp else 0
            if filt == 0:
                cur[x] = value
            elif filt == 1:
                cur[x] = (value + left) & 255
            elif filt == 2:
                cur[x] = (value + up) & 255
            elif filt == 3:
                cur[x] = (value + ((left + up) // 2)) & 255
            elif filt == 4:
                cur[x] = (value + _paeth(left, up, ul)) & 255
            else:
                raise ValueError("bad PNG filter")
        rows.append(cur)
        prev = cur
    if bit_depth == 1:
        grid = []
        for row in rows:
            bits = []
            for byte in row:
                for shift in range(7, -1, -1):
                    bits.append((byte >> shift) & 1)
                    if len(bits) == width:
                        break
            # PNG gray: 0 is black, which is a dark QR module.
            grid.append([1 if bit == 0 else 0 for bit in bits])
        return grid, width, height
    grid = []
    for row in rows:
        line = []
        for x in range(width):
            sample = row[x * channels]
            line.append(1 if sample < 128 else 0)
        grid.append(line)
    return grid, width, height


# Tahoe stand-in shared by the invite round-trip tests. `invite` prints one
# short code and stays up. `create-node --join` accepts only that code.
INVITE_JOIN_TAHOE = "\n".join([
    "import pathlib, sys, time",
    "args = sys.argv[1:]",
    "if \"invite\" in args:",
    "    sys.stdout.write(\"Connecting to wormhole server\\n\")",
    "    sys.stdout.write(\"Invite Code for client: 7-orange-tunnel\\n\")",
    "    sys.stdout.flush()",
    "    time.sleep(60)",
    "    raise SystemExit(0)",
    "if args and args[0] == \"run\":",
    "    nodedir = pathlib.Path(args[-1])",
    "    (nodedir / \"node.url\").write_text(\"http://127.0.0.1:1/\\n\", encoding=\"utf-8\")",
    "    while True:",
    "        time.sleep(0.2)",
    "if \"create-node\" in args or \"create-client\" in args:",
    "    nodedir = pathlib.Path(args[-1])",
    "    nodedir.mkdir(parents=True, exist_ok=True)",
    "    join = [a for a in args if a.startswith(\"--join=\")]",
    "    if join == [\"--join=0-dead-code\"]:",
    "        sys.stderr.write(\"wormhole.errors.LonelyError\\n\")",
    "        raise SystemExit(1)",
    "    if not join or join[0] != \"--join=7-orange-tunnel\":",
    "        sys.stderr.write(\"wormhole rejected\\n\")",
    "        raise SystemExit(1)",
    "    (nodedir / \"tahoe.cfg\").write_text(",
    "        \"# argv: \" + \" \".join(args) + \"\\n[node]\\nnickname = alice\\n[client]\\n\"",
    "        \"introducer.furl =\\nshares.needed = b'2'\\nshares.happy = b'3'\\n\"",
    "        \"shares.total = b'3'\\n\",",
    "        encoding=\"utf-8\",",
    "    )",
    "    raise SystemExit(0)",
    "sys.stderr.write(\"unexpected %r\\n\" % (args,))",
    "raise SystemExit(2)",
])


def write_executable(directory: Path, body: str, name: str = "tahoe") -> str:
    """A script CreateProcess can start on Windows and POSIX."""
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / ("%s.py" % name)
    script.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    if os.name == "nt":
        bat = directory / ("%s.bat" % name)
        bat.write_text('@"%s" "%s" %%*\n' % (sys.executable, script), encoding="utf-8")
        return str(bat)
    script.chmod(0o755)
    return str(script)


def _paeth(left: int, up: int, ul: int) -> int:
    estimate = left + up - ul
    dl, du, dul = abs(estimate - left), abs(estimate - up), abs(estimate - ul)
    if dl <= du and dl <= dul:
        return left
    if du <= dul:
        return up
    return ul
