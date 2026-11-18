"""Bit-accurate golden model of the FP16 (IEEE 754 binary16) Newton-Raphson divider.

Every integer width and truncation here matches model/../src/fp16_div_core.v, so this model
doubles as the reference for the testbenches. Works on numpy int64 arrays (vectorised) or
plain ints.

Algorithm (all mantissas are 11-bit normalised integers in [1024, 2047]):

    ge  = ma >= mb;  N = ge ? ma : 2*ma                     N in [mb, 2*mb), 12 bits
    Y0  = ROM[mb[9:4]]                                      7 bits, ~ 2^17 / mb  (64 entries)
    T   = mb * Y0                                           ~ 2^17
    e   = (2^17 - T) >> 4                                   signed 8 bits, |e| <= 89
    Q0  = (N * Y0) >> 4                                     quotient estimate, 2 extra fraction bits
    dQ  = ((Q0 >> 4) * e) >> 9                              the one Newton-Raphson / Goldschmidt step
    Q1  = (Q0 + dQ) >> 2                                    12 bits, always Q or Q - 1
    Rr  = N*2^11 - Q1*mb                                    exact remainder, in [0, 2*mb) when Q1 is Q or Q-1
    ge2 = Rr >= mb;  Q = Q1 + ge2;  rem_nz = (Rr - ge2*mb) != 0

with Q = floor(N * 2^11 / mb) exactly, in [2048, 4095]: 11 kept bits, the round bit is Q[0],
the sticky bit is rem_nz. "ok" is the built-in remainder check (0 <= Rr < 2*mb).
"""
import numpy as np

MW = 11                # mantissa bits including the hidden one
EBITS = 5
BIAS = 15
EMAX = 31
QNAN = 0x7E00
INF = 0x7C00
HID = 1 << (MW - 1)    # 1024
FMASK = HID - 1

SY = 17                # Y0 ~ 2^SY / mb
ET_SHIFT = 4
QX = 2                 # extra fraction bits of Q0
Q0T_SHIFT = 4

FLAG_INVALID, FLAG_DIVZERO, FLAG_OVERFLOW, FLAG_UNDERFLOW, FLAG_INEXACT = 16, 8, 4, 2, 1


def _build_rom():
    """Y0 for each of the 64 intervals of mb: the 7-bit value minimising max |2^17 - mb*Y0|."""
    rom = []
    for i in range(64):
        lo = HID + (i << 4)
        m = np.arange(lo, lo + 16, dtype=np.int64)
        best = None
        for y in range(64, 128):
            err = int(np.abs((1 << SY) - m * y).max())
            if best is None or err < best[0]:
                best = (err, y)
        rom.append(best[1])
    return np.array(rom, dtype=np.int64)


SEED_ROM = _build_rom()


def clz11(f):
    """Leading zeros of an 11-bit value f > 0 (0 .. 10)."""
    n = np.zeros_like(f)
    found = np.zeros_like(f, dtype=bool)
    for bit in range(MW - 1, -1, -1):
        hit = ((f >> bit) & 1) == 1
        n = np.where(found | hit, n, n + 1)
        found = found | hit
    return n


def unpack(x):
    s = (x >> 15) & 1
    e = (x >> 10) & 0x1F
    f = x & FMASK
    is_zero = (e == 0) & (f == 0)
    is_sub = (e == 0) & (f != 0)
    is_inf = (e == EMAX) & (f == 0)
    is_nan = (e == EMAX) & (f != 0)
    is_snan = is_nan & ((f >> 9) == 0)
    lz = np.where(is_sub, clz11(np.where(is_sub, f, 1)), 0)   # f has 10 bits: lz in 1 .. 10 here
    m = np.where(is_sub, f << lz, f | HID)                    # normalised 11-bit mantissa
    E = np.where(is_sub, 1 - lz, e)                           # biased exponent, may be <= 0
    return s, E, m, is_zero, is_inf, is_nan, is_snan


def recip_terms(mb):
    """Seed, T and the signed 8-bit residual e."""
    y0 = SEED_ROM[(mb >> 4) & 63]
    t = mb * y0
    e = ((1 << SY) - t) >> ET_SHIFT
    return y0, t, e


def nr_core(ma, mb):
    """Quotient datapath exactly as the RTL computes it.

    Returns (Q, rem_nz, ok, Rr, Q1): Q = floor(N * 2^11 / mb), the nonzero-remainder flag,
    the built-in remainder check (always True without a hardware fault), and the raw
    remainder and estimate for the testbenches.
    """
    ge = ma >= mb
    n = np.where(ge, ma, ma << 1)
    y0, t, e = recip_terms(mb)
    q0 = (n * y0) >> (SY - 11 - QX)                      # N*Y0 / 2^4, 14 bits
    dq = ((q0 >> Q0T_SHIFT) * e) >> 9                    # signed (arithmetic shift)
    q1 = (q0 + dq) >> QX
    rr = (n << 11) - q1 * mb
    ge2 = rr >= mb
    ok = (rr >= 0) & (rr < 2 * mb)
    q = q1 + ge2
    rem = rr - np.where(ge2, mb, 0)
    return q, rem != 0, ok, rr, q1


def fp16_div(a, b, with_ok=False):
    """Returns (result_bits, flags) for FP16 a / b, RNE, full subnormals, tininess after rounding."""
    a = np.asarray(a, dtype=np.int64)
    b = np.asarray(b, dtype=np.int64)
    a, b = np.broadcast_arrays(a, b)
    sa, Ea, ma, za, ia, na, sna = unpack(a)
    sb, Eb, mb, zb, ib, nb, snb = unpack(b)
    s = sa ^ sb

    q, rem_nz, ok, _, _ = nr_core(ma, mb)
    ge = ma >= mb
    E = Ea - Eb + BIAS - np.where(ge, 0, 1)

    # Tininess after rounding: round to 11 bits with unbounded exponent, check E stays <= 0
    keep_u = q >> 1
    rnd_u = q & 1
    inc_u = rnd_u & (rem_nz | (keep_u & 1))
    carry_u = (keep_u + inc_u) >> MW
    tiny = (E + carry_u) <= 0

    # Denormalise for subnormal results (shift right into exponent 0)
    sh = np.clip(1 - E, 0, 13)
    shifted_out = (q & ((1 << sh) - 1)) != 0
    qd = q >> sh
    E_res = np.where(E <= 0, 0, E)

    keep = qd >> 1
    rnd = qd & 1
    stk = rem_nz | shifted_out
    inexact = (rnd == 1) | stk
    keep = keep + (rnd & (stk | (keep & 1)))

    # Rounding carry: normal 2^11 -> renormalise; subnormal 2^10 -> becomes smallest normal
    ovf_m = keep >> MW
    keep = np.where(ovf_m == 1, keep >> 1, keep)
    E_res = np.where(ovf_m == 1, E_res + 1, E_res)
    E_res = np.where((E <= 0) & ((keep >> (MW - 1)) == 1), 1, E_res)

    overflow = E_res >= EMAX
    res = (s << 15) | (E_res << 10) | (keep & FMASK)
    res = np.where(overflow, (s << 15) | INF, res)
    underflow = tiny & inexact
    flags = (overflow * (FLAG_OVERFLOW | FLAG_INEXACT)) | (underflow * FLAG_UNDERFLOW) | (inexact * FLAG_INEXACT)

    # Special cases override the arithmetic path
    invalid = (za & zb) | (ia & ib) | sna | snb
    any_nan = na | nb | invalid
    divz = zb & ~za & ~ia & ~na
    inf_res = (ia & ~ib & ~nb) | divz
    zero_res = (za & ~zb & ~nb & ~na) | (ib & ~ia & ~na)

    res = np.where(zero_res, s << 15, res)
    res = np.where(inf_res, (s << 15) | INF, res)
    res = np.where(any_nan, QNAN, res)
    special = any_nan | inf_res | zero_res
    flags = np.where(special, 0, flags)
    flags = flags | (invalid * FLAG_INVALID) | (divz * FLAG_DIVZERO)
    if with_ok:
        return res.astype(np.int64), flags.astype(np.int64), (ok | special)
    return res.astype(np.int64), flags.astype(np.int64)


if __name__ == "__main__":
    tests = [(0x3C00, 0x4000, "1/2"), (0x4200, 0x3C00, "3/1"), (0x3C00, 0x4200, "1/3"),
             (0x0001, 0x3C00, "min_sub/1"), (0x7BFF, 0x0001, "max/min_sub"),
             (0x0000, 0x0000, "0/0"), (0x3C00, 0x0000, "1/0"), (0x7C00, 0x7C00, "inf/inf")]
    print("ROM:", SEED_ROM.tolist())
    for a, b, name in tests:
        r, f = fp16_div(a, b)
        with np.errstate(all="ignore"):
            ref = np.uint16(a).view(np.float16) / np.uint16(b).view(np.float16)
        print(f"{name:12s} 0x{int(r):04X}  flags={int(f):05b}  ({np.uint16(int(r)).view(np.float16)} vs numpy {ref})")
