"""Optional, explicit scientifically defined follow-on calculations.

Holm pairwise independent Welch comparisons do not replace design review.
Spectrogram only on sufficiently regular uniformly sampled signals.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats,signal


def independent_posthoc_holm(specimens:pd.DataFrame,condition='condition',value='value'):
    """Exploratory pairwise Welch t-tests with Holm step-down FWER correction.

    Operates on ONE row per independent physical specimen, never per raw repeat.
    """
    if condition not in specimens or value not in specimens:raise ValueError('缺少分组或试样测量列。')
    blocks=[(str(name),pd.to_numeric(g[value],errors='coerce').dropna().to_numpy(float))
            for name,g in specimens.groupby(condition,sort=False)]
    if len(blocks)<3:raise ValueError('Holm事后比较至少需要3组。')
    if len(blocks)>20:raise ValueError('当前事后比较最多20组；请先制定主要科学比较计划。')
    if min(len(x) for _,x in blocks)<2:raise ValueError('每组至少两件独立试样。')
    rec=[]
    for i,(ga,a) in enumerate(blocks):
        for gb,b in blocks[i+1:]:
            stat,p=stats.ttest_ind(a,b,equal_var=False)
            if not np.isfinite(p):
                p=np.nan
            rec.append(dict(group_a=ga,group_b=gb,n_a=len(a),n_b=len(b),
                mean_a=float(np.mean(a)),mean_b=float(np.mean(b)),
                mean_diff_a_minus_b=float(np.mean(a)-np.mean(b)),
                welch_t=float(stat) if np.isfinite(stat) else np.nan,
                p_uncorrected=float(p),p_holm=np.nan))
    r=pd.DataFrame(rec)
    valid=r.p_uncorrected.notna()
    inds=r.index[valid].to_numpy()
    if len(inds):
        ordered=inds[np.argsort(r.loc[inds,'p_uncorrected'].to_numpy(float))]
        total=len(ordered); running=0.
        for rank,ix in enumerate(ordered):
            running=max(running,(total-rank)*float(r.at[ix,'p_uncorrected']))
            r.at[ix,'p_holm']=min(running,1.)
    r['interpretation']='探索性独立试样两两Welch比较，Holm控制本文件所列完整检验族的FWER；不取代事先设计和实际工程意义判断。'
    return r


def validated_spectrogram(samples:pd.DataFrame, max_records=50000):
    """One-sided spectral *power*, original units squared/Hz, not amplitude."""
    if not {'time_s','filtered_value'} <= set(samples):raise ValueError('时频图需要时间与滤波数值列。')
    s=samples[['time_s','filtered_value']].copy()
    if len(s)<64:return None
    if len(s)>max_records:return None                                           
    t=pd.to_numeric(s.time_s,errors='raise').to_numpy(float)
    v=pd.to_numeric(s.filtered_value,errors='raise').to_numpy(float)
    if not np.isfinite(t).all() or not np.isfinite(v).all():return None
    d=np.diff(t)
    if np.any(d<=0):return None
    median=float(np.median(d))
    if np.max(np.abs(d-median))/median>.02:return None
    fs=1./median
    window=min(256,len(s))
    f,ts,pow=signal.spectrogram(v,fs=fs,window='hann',nperseg=window,
        noverlap=window//2, detrend='constant',scaling='density',mode='psd')
    ts=ts+float(t[0]);grid=pd.DataFrame({'time_s':np.tile(ts,len(f)),
        'frequency_Hz':np.repeat(f,len(ts)),'power_density':pow.reshape(-1)})
    return grid,(f,ts,pow)
