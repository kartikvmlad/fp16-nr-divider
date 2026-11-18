import numpy as np
MB = np.arange(1024,2048,dtype=np.int64); MA = MB.copy()
mb = np.repeat(MB, 1024); ma = np.tile(MA, 1024)
N = np.where(ma>=mb, ma, 2*ma); Qt = (N<<11)//mb
def rom(yb):
    SY=10+yb; out=[]
    for i in range(64):
        lo=1024+(i<<4); m=np.arange(lo,lo+16); best=None
        for y in range(1<<(yb-1),1<<yb):
            e=np.abs((1<<SY)-m*y).max()
            if best is None or e<best[0]: best=(e,y)
        out.append(best[1])
    return np.array(out)
R7=rom(7)
def run(variant,qx,q0t,bias,etd=4,yb=7):
    SY=10+yb; Y0=R7[(mb-1024)>>4]
    T=mb*Y0
    et=((1<<SY)-(1 if variant=="ones" else 0)-T)>>etd
    Q0=(N*Y0)>>(SY-11-qx); shq=12+qx-q0t; Q0t=Q0>>shq
    dQ=(Q0t*et)>>(SY-etd-shq)
    Q1=(Q0+dQ+bias)>>qx
    e=Qt-Q1
    return e.min(),e.max()
for v in ("floor","ones"):
  for qx in (2,3):
    for q0t in (10,12):
      for b in range(-2,4):
        r=run(v,qx,q0t,b)
        print(v,qx,q0t,b,r, "OK" if r[1]-r[0]<=1 else "")
