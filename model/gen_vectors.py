"""Write test vectors for test/tb_vectors.v and test/tb_fault.v.

One 56-bit hex word per line: a (16) b (16) result (16) flags (8).

    python gen_vectors.py wide out.hex [n]        every operand class of verify_reference.py
    python gen_vectors.py finite out.hex [n]      random finite, non-zero operands (fault injection)
    python gen_vectors.py mant out.hex ea eb [sa sb]
                                                  ALL 2^20 fraction pairs for the exponents ea / eb
                                                  (signs fixed, default 0 0): exhaustive mantissa test
    python gen_vectors.py directed out.hex        hand-picked corner cases (all pairs of CORNERS)
"""
import sys
import numpy as np
from fp16_div_model import fp16_div
from verify_reference import samples

CORNERS = [0x0000, 0x8000, 0x0001, 0x03FF, 0x0400, 0x3C00, 0xBC00, 0x4000, 0x3555, 0x7BFF, 0xFBFF,
           0x7C00, 0xFC00, 0x7E00, 0x7D00, 0x0200, 0x0401, 0x3BFF, 0x3C01, 0x5640, 0x0100, 0x8001]


def wide(n, seed=754):
    rng = np.random.default_rng(seed)
    per = max(1, n // 12)
    A, B = zip(*[(a, b) for _, a, b in samples(rng, per)])
    return np.concatenate(A), np.concatenate(B)


def finite(n, seed=2026):
    rng = np.random.default_rng(seed)

    def op():
        e = rng.integers(0, 31, n, dtype=np.int64)
        f = rng.integers(0, 1 << 10, n, dtype=np.int64)
        f = np.where((e == 0) & (f == 0), 1, f)
        return (rng.integers(0, 2, n, dtype=np.int64) << 15) | (e << 10) | f
    return op(), op()


def mant(ea, eb, sa=0, sb=0):
    fb = np.repeat(np.arange(1 << 10, dtype=np.int64), 1 << 10)
    fa = np.tile(np.arange(1 << 10, dtype=np.int64), 1 << 10)
    return (sa << 15) | (ea << 10) | fa, (sb << 15) | (eb << 10) | fb


def directed():
    c = np.array(CORNERS, dtype=np.int64)
    return np.repeat(c, c.size), np.tile(c, c.size)


def write(path, a, b):
    res, flags = fp16_div(a, b)
    with open(path, "w") as f:
        f.write("\n".join(f"{x:04x}{y:04x}{r:04x}{g:02x}"
                          for x, y, r, g in zip(a.tolist(), b.tolist(), res.tolist(), flags.tolist())))
        f.write("\n")
    print(f"{len(a)} vectors -> {path}")


def main():
    mode, path = sys.argv[1], sys.argv[2]
    if mode == "mant":
        ea, eb = int(sys.argv[3]), int(sys.argv[4])
        sa = int(sys.argv[5]) if len(sys.argv) > 5 else 0
        sb = int(sys.argv[6]) if len(sys.argv) > 6 else 0
        a, b = mant(ea, eb, sa, sb)
    elif mode == "directed":
        a, b = directed()
    else:
        default = {"wide": 600_000, "finite": 100_000}[mode]
        n = int(sys.argv[3]) if len(sys.argv) > 3 else default
        a, b = {"wide": wide, "finite": finite}[mode](n)
    write(path, a, b)


if __name__ == "__main__":
    main()
