import numpy as np
MB = np.arange(1024,2048,dtype=np.int64); MA = MB.copy()
mb = np.repeat(MB, 1024); ma = np.tile(MA, 1024)
N = np.where(ma>=mb, ma, 2*ma); Qt = (N<<11)//mb
def rom(yb, onesided, idx_shift=4):
    SY=10+yb; out=[]
    for i in range(1<<(11-idx_shift)):
        lo=1024+(i<<idx_shift); m=np.arange(lo,lo+(1<<idx_shift))
        if onesided:
            y=(1<<SY)//m.max()
        else:
            best=None
            for y in range(1<<(yb-1),1<<yb):
                e=np.abs((1<<SY)-m*y).max()
                if best is None or e<best[0]: best=(e,y)
            y=best[1]
        out.append(y)
    return np.array(out)
def run(yb, onesided, etd, qx, q0t):
    SY=10+yb; r=rom(yb,onesided); Y0=r[(mb-1024)>>4]
    T=mb*Y0
    et = ((1<<SY)-1-T)>>etd          # one s complement variant
    Q0=(N*Y0)>>(SY-11-qx)
    shq=12+qx-q0t
    Q0t=Q0>>shq
    dQ=(Q0t*et)>>(SY-etd-shq)
    Q1=(Q0+dQ)>>qx
    e=Qt-Q1
    return e.min(),e.max(),et.min(),et.max(),Y0.min(),Y0.max()
print("centered", [ (a, run(7,False,*a)) for a in [(4,2,10),(4,2,14),(4,3,10)]])
for yb in (7,8,9):
  for etd in (3,4,5):
    for qx in (2,3):
      print("onesided",yb,etd,qx, run(yb,True,etd,qx,10), run(yb,True,etd,qx,14))
