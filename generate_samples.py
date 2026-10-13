"""Deterministic synthetic signals/fitting/optimization examples. NOT experimental evidence."""
from pathlib import Path
import numpy as np
import pandas as pd
P=Path(__file__).resolve().parent/'samples';P.mkdir(exist_ok=True)
r=np.random.default_rng(20261009)
t=np.arange(0,30,0.05)
pd.DataFrame({'time_s':t,'value':1.3*np.sin(2*np.pi*.4*t)+.25*np.sin(2*np.pi*3*t)+r.normal(0,.11,len(t))}).to_csv(P/'demo_signal.csv',index=False)
x=np.linspace(0,10,140);y=1.7*(1-np.exp(-.4*x))+.1+r.normal(0,.055,len(x))
pd.DataFrame({'x':x,'y':y}).to_csv(P/'demo_fit.csv',index=False)
n=64;f=r.uniform(3,25,n);p=r.uniform(.1,1.2,n)
speed=1.8+.13*f-.003*f*f+.75*p-.28*p*p+r.normal(0,.045,n)
adhesion=.18+.25*p-.06*p*p-.0015*f+r.normal(0,.014,n)
pd.DataFrame({'experiment_id':[f'run_{i:03}' for i in range(n)],'frequency_hz':f,'preload_N':p,'speed_mm_s':speed,'adhesion_N':adhesion}).to_csv(P/'demo_optimization.csv',index=False)
print('Synthetic samples generated: signal, fit, optimization')
