"""Worked examples for docs/info.md: every intermediate value of the quotient datapath, from the model.

    python examples.py
"""
import numpy as np
from fp16_div_model import fp16_div, recip_terms, SEED_ROM, unpack, nr_core, SY

CASES = [
    ("1.0 / 3.0", 0x3C00, 0x4200),
    ("10.0 / 1.5", 0x4900, 0x3E00),
    ("1.5 / 1.0009765625", 0x3E00, 0x3C01),
    ("65504 / 0.5", 0x7BFF, 0x3800),
    ("1.0 / 65504", 0x3C00, 0x7BFF),
    ("min subnormal / 2", 0x0001, 0x4000),
    ("1.0 / 3.0 (negative)", 0xBC00, 0x4200),
    ("0 / 0", 0x0000, 0x0000),
]

print(f"{'case':22s} {'a':>6s} {'b':>6s} | {'ma':>5s} {'mb':>5s} {'N':>5s} {'Y0':>4s} {'e':>5s} {'Q1':>5s} {'R':>5s} {'Q':>5s} | {'result':>6s} flags")
for name, a, b in CASES:
    r, f = fp16_div(a, b)
    _, _, ma, za, ia, na, _ = unpack(np.int64(a))
    _, _, mb, zb, ib, nb, _ = unpack(np.int64(b))
    ma, mb = int(ma), int(mb)
    if za or zb or ia or ib or na or nb:
        print(f"{name:22s} {a:04X}   {b:04X}   | special operand: result 0x{int(r):04X} flags {int(f):05b}")
        continue
    y0, t, e = recip_terms(np.int64(mb))
    q, rem_nz, ok, rr, q1 = nr_core(np.int64(ma), np.int64(mb))
    n = ma if ma >= mb else 2 * ma
    print(f"{name:22s} {a:04X}   {b:04X}   | {ma:5d} {mb:5d} {n:5d} {int(y0):4d} {int(e):5d} {int(q1):5d} {int(rr):5d} {int(q):5d} | 0x{int(r):04X} {int(f):05b}")
