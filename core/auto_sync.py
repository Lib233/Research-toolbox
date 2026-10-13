"""Estimate temporal delay via normalized cross correlation, never assume signals share physics."""
import numpy as np
import pandas as pd
from .common import safe_numeric
from .synchronization import synchronize_signals

def suggest_clock_offset(a,b,time_a='time_s',value_a='value',time_b='time_s',value_b='value',
                         max_offset_s=2.0,step_s=.05):
    ta=safe_numeric(a[time_a],time_a).to_numpy();tb=safe_numeric(b[time_b],time_b).to_numpy()
    ya=safe_numeric(a[value_a],value_a).to_numpy();yb=safe_numeric(b[value_b],value_b).to_numpy()
    if any(np.diff(v).min()<=0 for v in (ta,tb)):raise ValueError('时间必须递增且没有重复')
    if not np.isfinite(max_offset_s) or max_offset_s<0 or not 0<step_s<=max(.2,max_offset_s):raise ValueError('搜索范围或步长非法')
    if np.std(ya)==0 or np.std(yb)==0:raise ValueError('恒定信号无法估计时钟偏移')
    offsets=np.arange(-max_offset_s,max_offset_s+step_s*.5,step_s)
    scores=[];support=[]
    for shift in offsets:
        first=max(ta[0],tb[0]+shift);last=min(ta[-1],tb[-1]+shift)
        if last-first<10*step_s:
            scores.append(np.nan);support.append(0);continue
        t=np.arange(first,last,step_s)
        a_on=np.interp(t,ta,ya);b_on=np.interp(t,tb+shift,yb)
                                                             
        def mask(orig,grid):
            idx=np.clip(np.searchsorted(orig,grid)-1,0,len(orig)-2)
            return (orig[idx+1]-orig[idx])<=4*step_s
        keep=mask(ta,t)&mask(tb+shift,t)
        if keep.sum()<12 or np.std(a_on[keep])==0 or np.std(b_on[keep])==0:
            scores.append(np.nan);support.append(int(keep.sum()));continue
        scores.append(float(np.corrcoef(a_on[keep],b_on[keep])[0,1]));support.append(int(keep.sum()))
    scores=np.asarray(scores)
    if not np.isfinite(scores).any():raise ValueError('有效重叠不足，无法估计偏移')
    best=int(np.nanargmax(np.abs(scores)))
    candidate=float(offsets[best]);maxcorr=float(scores[best])
    table=pd.DataFrame({'shift_b_s':offsets,'correlation':scores,'paired_points':support})
    return {'suggested_shift_b_s':candidate,'correlation':maxcorr,'n_at_peak':int(support[best]),
      'warning':'仅是两个信号相似事件的相关性对齐，不代表硬件时钟同步。不同物理量可能呈负相关；周期信号可能多解，必须验证触发事件。'},table
