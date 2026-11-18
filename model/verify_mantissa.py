"""Proof by exhaustion for the quotient datapath: every (ma, mb) pair of normalised 11-bit
mantissas (2^20 pairs). The estimate Q1 must be Q or Q - 1 (so one remainder compare fixes it),
the corrected Q must equal floor(N * 2^11 / mb), rem_nz must equal (N*2^11 mod mb != 0) and the
built-in remainder check must pass. Run after touching the ROM or any width."""
import numpy as np
from fp16_div_model import nr_core, SEED_ROM, HID

mb = np.repeat(np.arange(HID, 2 * HID, dtype=np.int64), HID)
ma = np.tile(np.arange(HID, 2 * HID, dtype=np.int64), HID)
q, rem_nz, ok, rr, q1 = nr_core(ma, mb)
n = np.where(ma >= mb, ma, 2 * ma)
qt, rt = (n << 11) // mb, (n << 11) % mb
d = qt - q1
print("pairs:", ma.size)
print("Q_true - Q1 histogram (0 and 1 expected):", dict(zip(*np.unique(d, return_counts=True))))
print("Rr range: [%d, %d]  (must lie in [0, 2*mb))" % (rr.min(), rr.max()))
assert (d >= 0).all() and (d <= 1).all(), "estimate outside {Q-1, Q}"
assert (q == qt).all(), "corrected quotient wrong"
assert (rem_nz == (rt != 0)).all(), "sticky wrong"
assert ok.all(), "self-check fails without a fault"
assert ((qt >= 2048) & (qt < 4096)).all()
print("OK: all 2^20 mantissa pairs exact")
