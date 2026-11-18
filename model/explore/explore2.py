import numpy as np, itertools
MB = np.arange(1024,2048,dtype=np.int64)
MA = np.arange(1024,2048,dtype=np.int64)
mb = np.repeat(MB, 1024); ma = np.tile(MA, 1024)
N = np.where(ma>=mb, ma, 2*ma)
Qt = (N<<11)//mb
_rom_cache={}
def build_rom(idx_shift, ybits, SY):
    key=(idx_shift,ybits,SY)
    if key in _rom_cache: return _rom_cache[key]
    nidx = 1<<(11-idx_shift); rom=[]
    for i in range(nidx):
        lo = 1024 + (i<<idx_shift); m = np.arange(lo,lo+(1<<idx_shift))
        best=None
        for y in range(1<<(ybits-1), 1<<ybits):
            e = np.abs((1<<SY) - m*y).max()
            if best is None or e<best[0]: best=(e,y)
        rom.append(best[1])
    _rom_cache[key]=np.array(rom); return _rom_cache[key]
def run(ybits, et_drop, qx, q0t, idx_shift=4):
    SY = 10+ybits
    rom = build_rom(idx_shift, ybits, SY)
    Y0 = rom[(mb-1024)>>idx_shift]
    e = (1<<SY) - mb*Y0
    et = e >> et_drop
    Q0 = (N*Y0) >> (SY - 11 - qx)          # 12+qx bits
    Q0t = Q0 >> (12+qx-q0t) if q0t<12+qx else Q0
    shq = 12+qx-q0t if q0t<12+qx else 0
    # dQ = Q0*e/2^SY  in units of 2^-qx :  = Q0t*2^shq * et*2^et_drop / 2^SY
    dQ = (Q0t*et) >> (SY - et_drop - shq)
    Q1 = (Q0 + dQ) >> qx
    err = Qt - Q1
    return err.min(), err.max(), et.min(), et.max(), Y0.min(), Y0.max()
res=[]
for yb in (7,8):
  for ed in (4,5,6,7):
    for qx in (0,1,2,3):
      for q0t in (6,7,8,9,12+3):
        r = run(yb,ed,qx,q0t)
        if r[0]>=0 and r[1]<=1: res.append((yb,ed,qx,q0t,r))
for r in res: print(r)
print("---- spread search")
out=[]
for yb in (6,7,8):
  for ed in (4,5,6,7):
    for qx in (0,1,2,3):
      for q0t in (5,6,7,8,9,10,12+qx):
        r = run(yb,ed,qx,q0t)
        out.append((r[1]-r[0], yb,ed,qx,q0t,r))
out.sort(key=lambda t:(t[0],-t[4]))
for o in out[:60]:
    if o[0]<=1: print(o)
