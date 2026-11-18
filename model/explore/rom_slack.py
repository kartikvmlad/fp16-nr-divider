"""For every ROM entry: which 7-bit seeds keep the estimate error in {0, 1} for ALL mantissa pairs
of that interval (entries are independent: errors only depend on the entry's own interval)?
The slack lets us pick a cheaper-to-synthesise table than the minimax one."""
import numpy as np
import sys
sys.path.insert(0, "..")
from fp16_div_model import SEED_ROM, SY, HID

MA = np.arange(1024, 2048, dtype=np.int64)


def err_range(i, y0):
    mb = np.arange(HID + 16 * i, HID + 16 * i + 16, dtype=np.int64)
    MBg, MAg = np.meshgrid(mb, MA, indexing="ij")
    mb_, ma_ = MBg.ravel(), MAg.ravel()
    n = np.where(ma_ >= mb_, ma_, 2 * ma_)
    t = mb_ * y0
    e = ((1 << SY) - t) >> 4
    q0 = (n * y0) >> 4
    dq = ((q0 >> 4) * e) >> 9
    q1 = (q0 + dq) >> 2
    qt = (n << 11) // mb_
    d = qt - q1
    return d.min(), d.max()


allowed = []
for i in range(64):
    ok = [y for y in range(64, 128) if (lambda r: r[0] >= 0 and r[1] <= 1)(err_range(i, y))]
    allowed.append(ok)
    print(i, int(SEED_ROM[i]), ok)
np.save("rom_allowed.npy", np.array([(min(a), max(a)) for a in allowed]))
