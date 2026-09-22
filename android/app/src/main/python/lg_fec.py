"""Reed-Solomon erasure codec compatible with zfec (systematic Vandermonde).

Used to read Tahoe-LAFS shares. The field and matrix match the published
Rizzo/zfec construction; this file is an original Python implementation.
"""

from __future__ import annotations

_PP = "101110001"
_EXP = [0] * 510
_LOG = [0] * 256
_INV = [0] * 256
_MUL = [[0] * 256 for _ in range(256)]
_READY = False


def _modnn(x: int) -> int:
    while x >= 255:
        x -= 255
        x = (x >> 8) + (x & 255)
    return x


def _init() -> None:
    global _READY
    if _READY:
        return
    mask = 1
    _EXP[8] = 0
    for i in range(8):
        _EXP[i] = mask
        _LOG[_EXP[i]] = i
        if _PP[i] == "1":
            _EXP[8] ^= mask
        mask = (mask << 1) & 0x1FF
    _LOG[_EXP[8]] = 8
    mask = 1 << 7
    for i in range(9, 255):
        if _EXP[i - 1] >= mask:
            _EXP[i] = _EXP[8] ^ ((_EXP[i - 1] ^ mask) << 1)
        else:
            _EXP[i] = _EXP[i - 1] << 1
        _EXP[i] &= 0xFF
        _LOG[_EXP[i]] = i
    _LOG[0] = 255
    for i in range(255):
        _EXP[i + 255] = _EXP[i]
    _INV[0] = 0
    _INV[1] = 1
    for i in range(2, 256):
        _INV[i] = _EXP[255 - _LOG[i]]
    for i in range(256):
        for j in range(256):
            if i == 0 or j == 0:
                _MUL[i][j] = 0
            else:
                _MUL[i][j] = _EXP[_modnn(_LOG[i] + _LOG[j])]
    _READY = True


def _mul(a: int, b: int) -> int:
    return _MUL[a][b]


def _addmul(dst: bytearray, src: bytes, c: int) -> None:
    if c == 0:
        return
    table = _MUL[c]
    for i, s in enumerate(src):
        dst[i] ^= table[s]


def _invert_mat(src: list[int], k: int) -> None:
    """Gauss-Jordan invert of a k*k row-major matrix, in place."""
    indxc = [0] * k
    indxr = [0] * k
    ipiv = [0] * k
    for col in range(k):
        irow = icol = 0
        found = False
        if ipiv[col] != 1 and src[col * k + col] != 0:
            irow = col
            icol = col
            found = True
        if not found:
            for row in range(k):
                if ipiv[row] != 1:
                    for ix in range(k):
                        if ipiv[ix] == 0 and src[row * k + ix] != 0:
                            irow = row
                            icol = ix
                            found = True
                            break
                if found:
                    break
        if not found:
            raise ValueError("singular erasure matrix")
        ipiv[icol] += 1
        if irow != icol:
            for ix in range(k):
                a = irow * k + ix
                b = icol * k + ix
                src[a], src[b] = src[b], src[a]
        indxr[col] = irow
        indxc[col] = icol
        pivot = icol * k
        c = src[pivot + icol]
        if c != 1:
            c = _INV[c]
            src[pivot + icol] = 1
            for ix in range(k):
                src[pivot + ix] = _mul(c, src[pivot + ix])
        for ix in range(k):
            if ix == icol:
                continue
            row = ix * k
            c = src[row + icol]
            src[row + icol] = 0
            if c:
                for j in range(k):
                    src[row + j] ^= _mul(c, src[pivot + j])
    for col in range(k, 0, -1):
        if indxr[col - 1] != indxc[col - 1]:
            for row in range(k):
                a = row * k + indxr[col - 1]
                b = row * k + indxc[col - 1]
                src[a], src[b] = src[b], src[a]


def _invert_vdm(src: list[int], k: int) -> None:
    if k == 1:
        return
    c = [0] * k
    p = [src[i * k + 1] for i in range(k)]
    c[k - 1] = p[0]
    for i in range(1, k):
        p_i = p[i]
        for j in range(k - 1 - (i - 1), k - 1):
            c[j] ^= _mul(p_i, c[j + 1])
        c[k - 1] ^= p_i
    for row in range(k):
        xx = p[row]
        t = 1
        b = [0] * k
        b[k - 1] = 1
        for i in range(k - 1, 0, -1):
            b[i - 1] = c[i] ^ _mul(xx, b[i])
            t = _mul(xx, t) ^ b[i - 1]
        inv_t = _INV[t]
        for col in range(k):
            src[col * k + row] = _mul(inv_t, b[col])


def _encode_matrix(k: int, n: int) -> list[int]:
    """n*k systematic encode matrix, row-major."""
    _init()
    tmp = [0] * (n * k)
    tmp[0] = 1
    for row in range(n - 1):
        base = (row + 1) * k
        for col in range(k):
            tmp[base + col] = _EXP[_modnn(row * col)]
    _invert_vdm(tmp, k)
    enc = [0] * (n * k)
    # bottom = (vandermonde bottom) * (inverted top)
    for row in range(n - k):
        for col in range(k):
            acc = 0
            for i in range(k):
                acc ^= _mul(tmp[(k + row) * k + i], tmp[i * k + col])
            enc[(k + row) * k + col] = acc
    for col in range(k):
        enc[col * k + col] = 1
    return enc


def encode_blocks(k: int, n: int, data_blocks: list[bytes]) -> list[bytes]:
    if len(data_blocks) != k:
        raise ValueError("need exactly k blocks")
    enc = _encode_matrix(k, n)
    size = len(data_blocks[0])
    out = [bytearray(data_blocks[i]) for i in range(k)]
    for sh in range(k, n):
        buf = bytearray(size)
        row = sh * k
        for j in range(k):
            _addmul(buf, data_blocks[j], enc[row + j])
        out.append(buf)
    return [bytes(x) for x in out]


def decode_blocks(k: int, n: int, shares: list[tuple[int, bytes]]) -> list[bytes]:
    """Return the k original blocks, given any k distinct shares."""
    if len(shares) < k:
        raise ValueError("not enough shares")
    chosen = shares[:k]
    enc = _encode_matrix(k, n)
    size = len(chosen[0][1])
    mat = [0] * (k * k)
    blocks = []
    for row, (shnum, block) in enumerate(chosen):
        if len(block) != size:
            raise ValueError("share length mismatch")
        src = shnum * k
        mat[row * k : (row + 1) * k] = enc[src : src + k]
        blocks.append(block)
    _invert_mat(mat, k)
    out = [bytearray(size) for _ in range(k)]
    for j in range(k):
        for i in range(k):
            _addmul(out[j], blocks[i], mat[j * k + i])
    return [bytes(x) for x in out]
