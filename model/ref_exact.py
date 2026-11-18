"""Exact references for IEEE 754 binary16 division (round-to-nearest-even).

ref_fraction(a, b): the ground truth - Python fractions.Fraction, no floating point anywhere.
ref_int(a, b)     : the same arithmetic on plain integers (faster); model/c/ref16.c is its C port.
Both return (bits, flags) with flags = {invalid, divzero, overflow, underflow, inexact} as
a 5-bit integer (16, 8, 4, 2, 1). Overflow always reports inexact too; tininess is detected
after rounding; NaN results are the canonical quiet NaN 0x7E00 (invalid only for sNaN, 0/0, inf/inf).
"""
from fractions import Fraction

QNAN, INF = 0x7E00, 0x7C00


def decode(x):
    return x >> 15, (x >> 10) & 0x1F, x & 0x3FF


def classify(a, b):
    """Special-case handling shared by both references. Returns (bits, flags) or None."""
    sa, ea, fa = decode(a)
    sb, eb, fb = decode(b)
    s = sa ^ sb
    a_nan, b_nan = ea == 31 and fa != 0, eb == 31 and fb != 0
    a_inf, b_inf = ea == 31 and fa == 0, eb == 31 and fb == 0
    a_zero, b_zero = ea == 0 and fa == 0, eb == 0 and fb == 0
    snan = (a_nan and not (fa >> 9)) or (b_nan and not (fb >> 9))
    if a_nan or b_nan:
        return QNAN, 16 if snan else 0
    if (a_inf and b_inf) or (a_zero and b_zero):
        return QNAN, 16
    if a_inf or b_zero:
        return (s << 15) | INF, 0 if a_inf else 8
    if a_zero or b_inf:
        return s << 15, 0
    return None


def ref_fraction(a, b):
    sp = classify(a, b)
    if sp is not None:
        return sp
    sa, ea, fa = decode(a)
    sb, eb, fb = decode(b)
    s = sa ^ sb
    va = Fraction(fa | 1024, 1) * Fraction(2) ** (ea - 25) if ea else Fraction(fa) * Fraction(2) ** -24
    vb = Fraction(fb | 1024, 1) * Fraction(2) ** (eb - 25) if eb else Fraction(fb) * Fraction(2) ** -24
    v = va / vb                                    # exact quotient, > 0
    # e: 2^e <= v < 2^(e+1)
    e = v.numerator.bit_length() - v.denominator.bit_length()
    if v < Fraction(2) ** e:
        e -= 1

    def rne(x):
        """Round the Fraction x >= 0 to an integer, ties to even; returns (k, exact)."""
        k = x.numerator // x.denominator
        r = x - k
        if r > Fraction(1, 2) or (r == Fraction(1, 2) and (k & 1)):
            k += 1
        return k, x == k

    k_unb, _ = rne(v / Fraction(2) ** (e - 10))    # 11 bits, unbounded exponent
    e_unb = e + 1 if k_unb == 2048 else e
    tiny = e_unb < -14
    lsb = max(e - 10, -24)
    k, exact = rne(v / Fraction(2) ** lsb)
    inexact = not exact
    if k == 0:
        return s << 15, 2 | 1
    top = k.bit_length() - 1 + lsb                 # exponent of the rounded result
    if top > 15:
        return (s << 15) | INF, 4 | 1
    if top < -14:
        bits = k                                   # subnormal: lsb is -24
    else:
        bits = ((top + 15) << 10) | ((k << (10 - (k.bit_length() - 1))) & 0x3FF)
    flags = (1 if inexact else 0) | (2 if (tiny and inexact) else 0)
    return (s << 15) | bits, flags


def ref_int(a, b):
    sp = classify(a, b)
    if sp is not None:
        return sp
    sa, ea, fa = decode(a)
    sb, eb, fb = decode(b)
    s = sa ^ sb
    na, xa = (fa | 1024, ea - 25) if ea else (fa, -24)
    nb, xb = (fb | 1024, eb - 25) if eb else (fb, -24)
    num, den = na, nb
    x = xa - xb
    if x >= 0:
        num <<= x
    else:
        den <<= -x
    e = num.bit_length() - den.bit_length()
    if (num << max(-e, 0)) < (den << max(e, 0)):
        e -= 1

    def round_at(lsb):
        n, d = (num << -lsb, den) if lsb < 0 else (num, den << lsb)
        k, r = divmod(n, d)
        if 2 * r > d or (2 * r == d and (k & 1)):
            k += 1
        return k, r != 0

    k_unb, _ = round_at(e - 10)
    e_unb = e + 1 if k_unb == 2048 else e
    tiny = e_unb < -14
    lsb = max(e - 10, -24)
    k, inexact = round_at(lsb)
    if k == 0:
        return s << 15, 2 | 1
    top = k.bit_length() - 1 + lsb
    if top > 15:
        return (s << 15) | INF, 4 | 1
    if top < -14:
        bits = k
    else:
        bits = ((top + 15) << 10) | ((k << (10 - (k.bit_length() - 1))) & 0x3FF)
    flags = (1 if inexact else 0) | (2 if (tiny and inexact) else 0)
    return (s << 15) | bits, flags
