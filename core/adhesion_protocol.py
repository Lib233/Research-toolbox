"""力—位移记录的可核查拉离过程计算；不自动识别剪切或剥离规程。

正向积分：按既定测力符号及空载零点校正，沿输入位移对非负力做梯形积分。
不能自动确定接触分离的物理边界；用户须指定有效时间窗
或事先拆分位移单调的测试曲线。该积分不自动等于本征界面黏附能。
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.integrate import trapezoid

@dataclass(frozen=True)
class AdhesionProtocol:
    baseline_mode: str = 'first_fraction'                                             
    baseline_fraction: float = 0.05
    baseline_start_s: float | None = None
    baseline_end_s: float | None = None
    manual_baseline_N: float = 0.0
    pull_start_s: float | None = None
    pull_end_s: float | None = None
    cycle_column: str | None = None
    area_mm2: float | None = None


def _baseline(t,f,p):
    if p.baseline_mode=='zero':return 0.,f'仪器已零点校准（不再次扣除）',float('nan'),0
    if p.baseline_mode=='manual':
        if not np.isfinite(p.manual_baseline_N):raise ValueError('手动基线必须是有限数值')
        return float(p.manual_baseline_N),'手动输入力传感器零点偏移',float('nan'),0
    if p.baseline_mode=='time_window':
        if p.baseline_start_s is None or p.baseline_end_s is None or p.baseline_end_s<=p.baseline_start_s:
            raise ValueError('基线时间窗必须明确且结束时间大于开始时间')
        pick=(t>=p.baseline_start_s)&(t<=p.baseline_end_s)
        if pick.sum()<3:raise ValueError('基线时间窗至少需要3个采样点')
        desc=f'显式基线时间窗 {p.baseline_start_s:g}–{p.baseline_end_s:g} s'
    elif p.baseline_mode=='first_fraction':
        if not (0<p.baseline_fraction<=.5):raise ValueError('基线比例必须在 (0,0.5]')
        num=max(3,int(np.ceil(len(f)*p.baseline_fraction)))
        pick=np.arange(len(f))<num
        desc=f'起始 {p.baseline_fraction:.0%} 作为力传感器零点偏移（需要人工核实）'
    else:raise ValueError('不支持的基线模式')
    vals=f[pick]
    med=float(np.median(vals));mad=float(1.4826*np.median(np.abs(vals-med)))
    return med,desc,mad,int(pick.sum())


def analyze_adhesion_protocol(data:pd.DataFrame,p:AdhesionProtocol):
    cols=['condition','sample_id','time_s','displacement_mm','force_N']
    miss=[k for k in cols if k not in data]
    if miss:raise ValueError('缺少必要列：'+','.join(miss))
    if p.area_mm2 is not None and (not np.isfinite(p.area_mm2) or p.area_mm2<=0):raise ValueError('面积必须为正')
    if p.cycle_column and p.cycle_column not in data:raise ValueError('未找到指定循环列：'+p.cycle_column)
    if p.pull_start_s is not None and p.pull_end_s is not None and p.pull_end_s<=p.pull_start_s:
        raise ValueError('拉离过程分析时间窗结束时间必须晚于开始时间')
    d=data.copy()
    for name in ('time_s','displacement_mm','force_N'):
        d[name]=pd.to_numeric(d[name],errors='raise')
    if d[cols].isna().any().any() or not np.isfinite(d[['time_s','displacement_mm','force_N']]).all().all():
        raise ValueError('时间、力、位移和 ID 不得包含空值或非有限数')
    grouping=['condition','sample_id']+([p.cycle_column] if p.cycle_column else [])
    metrics=[];traces=[];alerts=[]
    for key,sub in d.groupby(grouping,sort=False,dropna=False):
        keys=key if isinstance(key,tuple) else (key,)
        sub=sub.sort_values('time_s').copy();tag=' / '.join(map(str,keys))
        if len(sub)<5:raise ValueError(tag+'：至少需要5个时间点')
        t=sub.time_s.to_numpy(float);disp=sub.displacement_mm.to_numpy(float);f=sub.force_N.to_numpy(float)
        if np.any(np.diff(t)<=0):raise ValueError(tag+'：时间必须严格递增')
        zero,reason,noise,nzero=_baseline(t,f,p)
        valid=np.ones(len(sub),dtype=bool)
        if p.pull_start_s is not None:valid &= t>=p.pull_start_s
        if p.pull_end_s is not None:valid &= t<=p.pull_end_s
        if valid.sum()<3:raise ValueError(tag+'：有效拉离过程分析时间窗不足3点')
        ti=t[valid];di=disp[valid];fi=f[valid]-zero
        if np.any(np.diff(di)<-1e-9):
            raise ValueError(tag+'：所选拉离过程分析时间窗的位移发生回退。请拆分循环或指定拉离过程分析起止时间，软件不会误积分加载过程。')
        if np.ptp(di)<=0:raise ValueError(tag+'：拉离过程位移没有有效变化')
        positive=np.clip(fi,0,None)
        peak_i=int(np.argmax(positive));work=float(trapezoid(positive,di))
        sample_info={'condition':keys[0],'sample_id':keys[1]}
        if p.cycle_column:sample_info['cycle_id']=keys[2]
        row={**sample_info,'n_points_total':len(sub),'n_points_pull':int(valid.sum()),
             'baseline_N':zero,'baseline_mode':p.baseline_mode,'baseline_points':nzero,
             'baseline_robust_noise_N':noise,'peak_force_N':float(positive[peak_i]),
             'displacement_at_peak_mm':float(di[peak_i]),'time_at_peak_s':float(ti[peak_i]),
             'separation_work_mJ':work,'pull_displacement_range_mm':float(np.ptp(di))}
        if p.area_mm2:
            row['peak_nominal_stress_kPa']=1000*row['peak_force_N']/p.area_mm2
            row['work_per_nominal_area_J_m2']=1000*work/p.area_mm2
        qc=[]
        if p.baseline_mode=='first_fraction':qc.append('初段零点估计尚未核实是否处于空载、无预载状态')
        if peak_i==0 or peak_i==len(fi)-1:qc.append('峰值位于拉离过程分析时间窗边缘，可能截断')
        if np.isfinite(noise) and noise>0 and row['peak_force_N']<6*noise:qc.append('峰值低于六倍基线稳健噪声，信噪比偏低')
        if len(fi)>=5 and np.max(np.abs(np.diff(fi))) > .85*max(np.ptp(fi),1e-12):
            qc.append('检测到突变力台阶；需检查传感器饱和/丢样')
        row['quality_flags']='；'.join(qc)
        metrics.append(row)
        sub['baseline_corrected_force_N']=f-zero
        sub['pull_phase']=valid
        sub['adhesive_tensile_force_N']=np.where(valid,np.clip(f-zero,0,None),np.nan)
        sub['baseline_source']=reason
        traces.append(sub)
        if qc:alerts.append(tag+'：'+'；'.join(qc))
    return pd.DataFrame(metrics),pd.concat(traces,ignore_index=True),alerts
