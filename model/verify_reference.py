"""Operand classes used by the verification flow, and the model-versus-reference sweep.

samples(rng, n) yields (name, A, B) groups of n operand pairs each:
uniform bits, every exponent pair, subnormals, overflow / underflow boundaries,
boundary mantissas, power-of-two divisors (exact quotients, ties in the subnormal range), ...

    python verify_reference.py [n_per_class]

compares model.fp16_div with ref_exact.ref_int on every sample and with the Fraction-based
ref_fraction on a thinner subset (the Fraction reference is ~50x slower).
"""
import sys
import numpy as np
from fp16_div_model import fp16_div
from ref_exact import ref_int, ref_fraction

EDGE_F = [0, 1, 2, 3, 0x155, 0x2AA, 0x200, 0x1FF, 0x201, 0x3FF, 0x3FE, 0x3FD, 0x100, 0x0FF]


def samples(rng, n):
    r = lambda hi: rng.integers(0, hi, n, dtype=np.int64)
    u = lambda: r(1 << 16)
    yield "uniform bits", u(), u()

    def fp(e, f=None, s=None):
        f = r(1 << 10) if f is None else f
        s = r(2) if s is None else s
        return (s << 15) | (e << 10) | f

    yield "all exponent pairs", fp(r(31) + 0), fp(r(31) + 0)
    yield "normal / normal, close exponents", fp(15 + r(3) - 1), fp(15 + r(3) - 1)
    yield "subnormal / normal", fp(np.zeros(n, dtype=np.int64)), fp(r(31))
    yield "normal / subnormal", fp(r(31)), fp(np.zeros(n, dtype=np.int64))
    yield "subnormal / subnormal", fp(np.zeros(n, dtype=np.int64)), fp(np.zeros(n, dtype=np.int64))
    yield "overflow boundary", fp(29 + r(2)), fp(r(3))
    yield "underflow boundary", fp(r(3)), fp(26 + r(5))
    yield "subnormal results", fp(1 + r(4)), fp(14 + r(14))
    ef = np.array(EDGE_F, dtype=np.int64)
    yield "boundary mantissas", fp(r(31), ef[r(ef.size)]), fp(r(31), ef[r(ef.size)])
    yield "power-of-two divisor", fp(r(31)), fp(1 + r(30), np.zeros(n, dtype=np.int64))
    yield "specials", np.where(r(4) == 0, fp(np.full(n, 31), r(1 << 10)), fp(r(32))), \
        np.where(r(4) == 0, fp(np.full(n, 31), r(1 << 10)), fp(r(32)))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    rng = np.random.default_rng(754)
    total = bad = 0
    for name, a, b in samples(rng, n):
        res, flags = fp16_div(a, b)
        res, flags = res.tolist(), flags.tolist()
        al, bl = a.tolist(), b.tolist()
        nb = 0
        for i in range(len(al)):
            if (res[i], flags[i]) != ref_int(al[i], bl[i]):
                nb += 1
        thin = max(1, len(al) // 20)
        for i in range(0, len(al), len(al) // thin):
            if (res[i], flags[i]) != ref_fraction(al[i], bl[i]):
                nb += 1
        print(f"{name:36s} {len(al):8d} pairs  mismatches {nb}")
        total += len(al)
        bad += nb
    print(f"total {total} pairs, {bad} mismatches")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
