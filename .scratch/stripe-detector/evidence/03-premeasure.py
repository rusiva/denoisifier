import time, numpy as np
from multiprocessing import Pool
from denoisifier import analyse
from denoisifier.synthetic import Emccd, generate
CASES = [(3, 10), (5, 0), (8, 6), (12, -8), (20, -10), (4, -4), (16, 10), (6, -10), (10, 3), (14, -6)]
def f(a):
    seed,m,shape=a
    p,ang=CASES[seed%10]
    s=generate(seed=seed,shape=shape,period=p,angle_deg=ang,modulation_depth=m,mottle="scorched",noise=Emccd())
    return analyse(s.frame).score
if __name__=="__main__":
    with Pool(16) as pool:
        for shape in [(256,256)]:
            t=time.time()
            z=np.array(pool.map(f,[(s,0.0,shape) for s in range(1000,1400)]))
            w=np.array(pool.map(f,[(s,0.2,shape) for s in range(1000,1200)]))
            print(shape,time.time()-t)
            q=np.quantile(z,0.99); print("m0 q50 q99 max",np.median(z),q,z.max())
            print("det at q99",(w>q).mean(), "at 154",(w>154).mean())
            for i,(p,a) in enumerate(CASES):
                ww=w[i::10]; print(p,a,np.round(np.quantile(ww,[0,.1,.5]),1),(ww>q).mean())
        t=time.time()
        z2=np.array(pool.map(f,[(s,0.0,(400,1600)) for s in range(2000,2032)]))
        w2=np.array(pool.map(f,[(s,0.2,(400,1600)) for s in range(2000,2032)]))
        print("1600x400",time.time()-t,"m0 max",z2.max(),np.median(z2),"m0.2 min",np.round(np.sort(w2)[:8],1))
