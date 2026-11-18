import numpy as np, itertools, sys
MB = np.arange(1024,2048,dtype=np.int64)
MA = np.arange(1024,2048,dtype=np.int64)
mb = np.repeat(MB, 1024); ma = np.tile(MA, 1024)
N = np.where(ma>=mb, ma, 2*ma)
Qt = (N<<11)//mb

def build_rom(idx_shift, ybits, SY):
    nidx = 1<<(11-idx_shift)  # entries
    rom=[]
    for i in range(nidx):
        lo = 1024 + (i<<idx_shift); hi = lo + (1<<idx_shift) - 1
        best=None
        for y in range(1<<(ybits-1), (1<<ybits)):
            m = np.arange(lo,hi+1)
            e = np.abs((1<<SY) - m*y).max()
            if best is None or e<best[0]: best=(e,y)
        rom.append(best[1])
    return np.array(rom)

def run(idx_shift=4, ybits=8, SY=18, et_drop=5, q0_extra=0):
    rom = build_rom(idx_shift, ybits, SY)
    Y0 = rom[(mb-1024)>>idx_shift]
    T = mb*Y0
    e = (1<<SY) - T
    et = e >> et_drop
    # Q0 with q0_extra fractional bits
    sh = SY - 11 - q0_extra
    Q0 = (N*Y0) >> sh
    dQ = (Q0*et) >> (SY - et_drop)
    Q1f = Q0 + dQ
    Q1 = Q1f >> q0_extra
    err = Qt - Q1
    return err.min(), err.max(), np.bincount(err-err.min())

for args in [(4,8,18,5,0),(4,8,18,5,2),(4,8,18,4,2),(4,8,18,3,3),(5,8,18,5,2),(4,9,19,5,2),(4,10,20,6,2),(3,8,18,5,2)]:
    mn,mx,h = run(*args)
    print(args, mn, mx, h)
