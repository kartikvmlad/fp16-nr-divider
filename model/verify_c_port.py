"""Ties the C port used for the all-2^32 run (model/c/exhaustive) to the Fraction reference:
evaluates a few million operand pairs (every operand class of verify_reference.py plus uniformly
random bits) with the C program (integer reference + algorithm model) and compares every line
with ref_fraction (exact rational arithmetic) and with the numpy model.

    python verify_c_port.py [n_per_class]
"""
import os
import subprocess
import sys
import numpy as np
from fp16_div_model import fp16_div
from ref_exact import ref_fraction
from verify_reference import samples

n = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
rng = np.random.default_rng(1)
A, B = [], []
for _, a, b in samples(rng, n):
    A.append(a)
    B.append(b)
a = np.concatenate(A)
b = np.concatenate(B)
here = os.path.dirname(os.path.abspath(__file__))
exe = os.path.join(here, "c", "exhaustive")
pairs, out = "pairs_c_port.txt", "out_c_port.txt"
with open(pairs, "w") as f:
    f.write("\n".join(f"{x:04x} {y:04x}" for x, y in zip(a.tolist(), b.tolist())))
    f.write("\n")
subprocess.run([exe, pairs, out], check=True)
res, flags = fp16_div(a, b)
bad = 0
with open(out) as f:
    for i, line in enumerate(f):
        x, y, r1, f1, r2, f2 = (int(v, 16) for v in line.split())
        ref = ref_fraction(x, y)
        if (r1, f1) != ref or (r2, f2) != ref or (int(res[i]), int(flags[i])) != ref:
            bad += 1
            if bad <= 10:
                print("MISMATCH", hex(x), hex(y), (r1, f1), (r2, f2), (int(res[i]), int(flags[i])), ref)
os.remove(pairs)
os.remove(out)
print(f"{len(a)} pairs: C integer reference, C model and numpy model vs Fraction reference: {bad} mismatches")
sys.exit(1 if bad else 0)
