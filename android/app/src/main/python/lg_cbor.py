"""Minimal CBOR for the Tahoe HTTP storage API (RFC 8949).

Tahoe's Great Black Swamp messages are small maps, sets of share numbers
(tag 258), byte strings, and integers. This codec covers that subset.
"""

from __future__ import annotations

from typing import Any


class CborError(ValueError):
    pass


def dumps(value: Any) -> bytes:
    out = bytearray()
    _write(out, value)
    return bytes(out)


def loads(data: bytes) -> Any:
    value, pos = _read(data, 0)
    if pos != len(data):
        raise CborError("trailing bytes after CBOR value")
    return value


def _write(out: bytearray, value: Any) -> None:
    if value is None:
        out.append(0xF6)
        return
    if value is True:
        out.append(0xF5)
        return
    if value is False:
        out.append(0xF4)
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if value >= 0:
            _head(out, 0, value)
        else:
            _head(out, 1, -1 - value)
        return
    if isinstance(value, (bytes, bytearray)):
        blob = bytes(value)
        _head(out, 2, len(blob))
        out.extend(blob)
        return
    if isinstance(value, str):
        blob = value.encode("utf-8")
        _head(out, 3, len(blob))
        out.extend(blob)
        return
    if isinstance(value, (list, tuple)):
        _head(out, 4, len(value))
        for item in value:
            _write(out, item)
        return
    if isinstance(value, set):
        # Tag 258, then an array. Tahoe's CDDL is ``#6.258([* uint])``.
        _head(out, 6, 258)
        items = list(value)
        _head(out, 4, len(items))
        for item in items:
            _write(out, item)
        return
    if isinstance(value, dict):
        _head(out, 5, len(value))
        for key, item in value.items():
            _write(out, key)
            _write(out, item)
        return
    raise CborError("cannot encode %s" % type(value).__name__)


def _head(out: bytearray, major: int, n: int) -> None:
    if n < 0:
        raise CborError("negative length")
    prefix = major << 5
    if n < 24:
        out.append(prefix | n)
    elif n < 256:
        out.append(prefix | 24)
        out.append(n)
    elif n < 65536:
        out.append(prefix | 25)
        out.extend(n.to_bytes(2, "big"))
    elif n < 2**32:
        out.append(prefix | 26)
        out.extend(n.to_bytes(4, "big"))
    else:
        out.append(prefix | 27)
        out.extend(n.to_bytes(8, "big"))


def _read(data: bytes, pos: int) -> tuple[Any, int]:
    if pos >= len(data):
        raise CborError("truncated CBOR")
    initial = data[pos]
    pos += 1
    major = initial >> 5
    extra = initial & 0x1F
    if extra < 24:
        arg = extra
    elif extra == 24:
        arg, pos = _take(data, pos, 1)
    elif extra == 25:
        arg, pos = _take(data, pos, 2)
    elif extra == 26:
        arg, pos = _take(data, pos, 4)
    elif extra == 27:
        arg, pos = _take(data, pos, 8)
    else:
        raise CborError("unsupported additional info %d" % extra)
    if major == 0:
        return arg, pos
    if major == 1:
        return -1 - arg, pos
    if major == 2:
        end = pos + arg
        if end > len(data):
            raise CborError("truncated bytes")
        return data[pos:end], end
    if major == 3:
        end = pos + arg
        if end > len(data):
            raise CborError("truncated text")
        return data[pos:end].decode("utf-8"), end
    if major == 4:
        items = []
        for _ in range(arg):
            item, pos = _read(data, pos)
            items.append(item)
        return items, pos
    if major == 5:
        mapping: dict[Any, Any] = {}
        for _ in range(arg):
            key, pos = _read(data, pos)
            item, pos = _read(data, pos)
            mapping[key] = item
        return mapping, pos
    if major == 6:
        tagged, pos = _read(data, pos)
        if arg == 258 and isinstance(tagged, list):
            return set(tagged), pos
        return tagged, pos
    if major == 7:
        if extra == 20:
            return False, pos
        if extra == 21:
            return True, pos
        if extra == 22:
            return None, pos
        raise CborError("unsupported simple value")
    raise CborError("unsupported major type %d" % major)


def _take(data: bytes, pos: int, n: int) -> tuple[int, int]:
    end = pos + n
    if end > len(data):
        raise CborError("truncated header")
    return int.from_bytes(data[pos:end], "big"), end
