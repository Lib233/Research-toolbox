"""Manual clock alignment for two scalar time series, with gap-aware interpolation.

No automatic physical event matching is claimed. Large missing segments remain NaN.
"""
import numpy as np
import pandas as pd
from .common import safe_numeric


def synchronize_signals(a,b,time_a='time_s',value_a='value',time_b='time_s',value_b='value',
                        shift_b_s=0.0,dt_s=0.1,max_gap_s=0.5):
    """Shift B clock by shift_b_s, then interpolate BOTH onto overlapping uniform time grid.

    Outputs: time_s, signal_A, signal_B, A_observed_nearby, B_observed_nearby.
    `max_gap_s` rejects interpolation across missing or sparse sampling gaps.
    """
    step=float(dt_s);gap=float(max_gap_s);shift=float(shift_b_s)
    if not all(np.isfinite([step,gap,shift])) or step<=0 or gap<step:
        raise ValueError('同步步长必须>0，最大插值缺口必须不小于步长。')
    def get(df,ct,cv,sh):
        t=safe_numeric(df[ct],ct).to_numpy()+sh;y=safe_numeric(df[cv],cv).to_numpy()
        if len(t)<3 or np.any(np.diff(t)<=0):raise ValueError(f'{ct}: 时间至少3点且严格递增，不能重复。')
        return t,y
    ta,va=get(a,time_a,value_a,0);tb,vb=get(b,time_b,value_b,shift)
    first=max(ta[0],tb[0]);last=min(ta[-1],tb[-1])
    if last-first<4*step:raise ValueError('同步时间轴重叠不足；检查时钟偏移量和时间单位。')
    grid=first+np.arange(int(np.floor((last-first)/step))+1)*step
    if len(grid)>2_000_000:raise ValueError('同步输出点数过多；请增大重采样步长。')
    def resample(t,y):
        interp=np.interp(grid,t,y)
        before=np.clip(np.searchsorted(t,grid,side='right')-1,0,len(t)-2)
        nextidx=before+1
        large=(t[nextidx]-t[before])>gap+1e-10
                                                                        
        exact=(np.abs(grid-t[before])<step*1e-6)|(np.abs(grid-t[nextidx])<step*1e-6)
        interp[large&~exact]=np.nan
        return interp,~(large&~exact)
    pa,ma=resample(ta,va);pb,mb=resample(tb,vb)
    df=pd.DataFrame({'time_s':grid,'signal_A':pa,'signal_B':pb,'A_gap_ok':ma,'B_gap_ok':mb})
    report={'overlap_start_s':float(first),'overlap_end_s':float(last),'rows':len(df),
            'complete_pairs':int(np.count_nonzero(np.isfinite(pa)&np.isfinite(pb))),
            'clock_shift_applied_to_B_s':shift,'resample_step_s':step,'max_interpolated_gap_s':gap,
            'warning':'只做基于已知时钟偏移的数值同步；不能替代TTL触发器、硬件时间戳或物理事件校准。'}
    return df,report
