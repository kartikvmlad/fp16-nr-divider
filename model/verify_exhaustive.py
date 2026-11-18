"""ALL 2^32 operand pairs through the numpy model (model/fp16_div_model.py).

  * result bits are compared with numpy float16 division (every NaN counted as the canonical NaN;
    float16 division through float32 is exact enough: 24 >= 2*11 + 2, double rounding is harmless)
  * result bits + flags are folded into the same order-independent 64-bit checksum as the C program
    model/c/exhaustive (C compares the model port against the exact integer reference on every pair),
    so equal checksums tie the numpy model to the exact reference on all pairs, flags included.

    python verify_exhaustive.py [expected_checksum_hex]
"""
import sys
import numpy as np
from multiprocessing import Pool
from fp16_div_model import fp16_div

K1, K2 = np.uint64(0x9E3779B97F4A7C15), np.uint64(0xD1B54A32D192ED03)


def chunk(ahi):
    a = (np.arange(1 << 4, dtype=np.int64) + (ahi << 4))[:, None] * np.ones((1, 1 << 16), dtype=np.int64)
    b = np.ones((1 << 4, 1), dtype=np.int64) * np.arange(1 << 16, dtype=np.int64)[None, :]
    a, b = a.ravel(), b.ravel()
    res, flags = fp16_div(a, b)
    with np.errstate(all="ignore"):
        ref = a.astype(np.uint16).view(np.float16) / b.astype(np.uint16).view(np.float16)
    refbits = ref.view(np.uint16).astype(np.int64)
    refbits = np.where(np.isnan(ref), 0x7E00, refbits)
    bad = int(np.count_nonzero(res != refbits))
    idx = ((a << 16) | b).astype(np.uint64)
    w = idx * K1 + K2
    h = np.sum(((res | (flags << 16)).astype(np.uint64) + np.uint64(1)) * w, dtype=np.uint64)
    return bad, int(h)


if __name__ == "__main__":
    with Pool() as p:
        out = p.map(chunk, range(4096), chunksize=16)
    bad = sum(o[0] for o in out)
    h = sum(o[1] for o in out) % (1 << 64)
    print(f"pairs=4294967296 value mismatches vs numpy float16: {bad}")
    print(f"checksum_model_py={h:016x}")
    if len(sys.argv) > 1:
        exp = int(sys.argv[1], 16)
        print("checksum matches C exact-reference checksum:", h == exp)
        sys.exit(0 if (h == exp and bad == 0) else 1)
