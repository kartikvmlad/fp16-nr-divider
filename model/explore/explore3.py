import numpy as np
exec(open("explore2.py").read().split("res=[]")[0])
# detailed look at the promising config: ybits 7, et_drop 4, qx 2, several q0t
for yb,ed,qx,q0t in [(7,4,2,10),(7,4,2,9),(7,4,2,8),(7,4,1,10),(7,4,1,9),(7,5,2,10),(6,4,2,10),(7,4,0,10)]:
    print(yb,ed,qx,q0t, run(yb,ed,qx,q0t))
# 32-entry ROM
for yb,ed,qx,q0t in [(7,4,2,14),(8,4,2,14)]:
    print("idx5",yb,ed,qx,q0t, run(yb,ed,qx,q0t,idx_shift=5))
