import numpy as np
MB = np.arange(1024,2048,dtype=np.int64); MA = MB.copy()
mb = np.repeat(MB, 1024); ma = np.tile(MA, 1024)
N = np.where(ma>=mb, ma, 2*ma); Qt = (N<<11)//mb
def rom(yb, idx_shift=4):
    SY=10+yb; out=[]
    for i in range(1<<(11-idx_shift)):
        lo=1024+(i<<idx_shift); m=np.arange(lo,lo+(1<<idx_shift)); best=None
        for y in range(1<<(yb-1),1<<yb):
            e=np.abs((1<<SY)-m*y).max()
            if best is None or e<best[0]: best=(e,y)
        out.append(best[1])
    return np.array(out)
def run(yb, qx, q0t, bias, etd=4):
    SY=10+yb; r=rom(yb); Y0=r[(mb-1024)>>4]
    T=mb*Y0
    u=T>>etd
    one=1<<(SY-etd)
    s=(u>=one)
    mag=np.where(s,u-one,one-1-u)
    Q0=(N*Y0)>>(SY-11-qx)
    shq=12+qx-q0t
    Q0t=Q0>>shq
    dQm=(Q0t*mag)>>(SY-etd-shq)
    Q1f=np.where(s,Q0-dQm,Q0+dQm)+bias
    Q1=Q1f>>qx
    e=Qt-Q1
    return e.min(),e.max(),mag.max()
for qx in (2,3):
  for q0t in (10,12):
    for bias in range(-2,4):
      r=run(7,qx,q0t,bias)
      if r[1]-r[0]<=1: print("yb7 qx",qx,"q0t",q0t,"bias",bias,r)
print("--- all")
for qx in (2,3,4):
  for q0t in (10,12,14):
    for bias in range(-3,4):
      r=run(7,qx,q0t,bias)
      print(qx,q0t,bias,r)
