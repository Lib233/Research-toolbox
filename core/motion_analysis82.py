""": defensible, segment-aware 2-D landmark analysis.

Raw positions NEVER overwritten; gaps and rejected points are NEVER filled.
The smoothed values are optional visual/kinematic estimates, not measured positions.
Period finding is screening, not a biological mode classifier.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter, find_peaks


def _segments(rows, max_gap_factor=1.6):
    """Consecutive detected rows split by loss, omitted frames or nonmonotonic time."""
                                                                                             
    time=rows.time_s.to_numpy(float)
    frames=rows.frame.to_numpy(int)
    good=rows.detected.fillna(False).to_numpy(bool) & np.isfinite(time)
    gaps=np.diff(time)
    positive=gaps[gaps>0]
    typical=float(np.median(positive)) if len(positive) else np.nan
    valid_step=(np.diff(time)>0)
    if np.isfinite(typical):valid_step &= (np.diff(time)<=typical*max_gap_factor)
    valid_step &= (np.diff(frames)>0)
    blocks=[];block=[]
    for i in range(len(rows)):
        if good[i] and (not block or (good[i-1] and valid_step[i-1])):
            block.append(i)
        else:
            if block:blocks.append(block)
            block=[i] if good[i] else []
    if block:blocks.append(block)
    return blocks


def annotate_motion(track:pd.DataFrame, smooth_window:int=11, polyorder:int=2,
                    max_speed_mm_s:float=0., fb_warning_px:float=1.0):
    """Add non-destructive smoothed position/velocity and potential-review indicators.

    Savitzky-Golay is limited to uninterrupted detections; smoothing is refused
    when fewer than 5 samples or nonuniform frame timing. Review flags are NOT
    deleted measurements. Returns (annotated long-form, review rows).
    """
    if smooth_window<0 or (smooth_window and smooth_window<5) or (smooth_window and smooth_window%2==0):
        raise ValueError('平滑窗口须为 0（关闭）或至少 5 的奇数。')
    if polyorder<1 or polyorder>3:raise ValueError('平滑多项式阶数应为 1–3。')
    if not np.isfinite(max_speed_mm_s) or max_speed_mm_s<0:raise ValueError('速度核查阈值必须是非负数。')
    if not np.isfinite(fb_warning_px) or fb_warning_px<=0:raise ValueError('光流前后向复核阈值必须大于0。')
    parts=[]
    for name,g in track.groupby('point_id',sort=False):
        d=g.sort_values('frame').copy().reset_index(drop=True)
        for col in ['x_mm_smooth','y_up_mm_smooth','speed_smooth_mm_s','vx_smooth_mm_s','vy_smooth_mm_s']:
            d[col]=np.nan
        d['smooth_applied']=False
        d['quality_review']=''
        d['segment_id']=pd.NA
                                                                               
        speed=pd.to_numeric(d.speed_mm_s,errors='coerce').to_numpy(float)
        vv=speed[np.isfinite(speed)]
        med=float(np.median(vv)) if len(vv)>=5 else np.nan
        mad=float(1.4826*np.median(np.abs(vv-med))) if len(vv)>=5 else np.nan
        robust_limit=(med+7*mad) if len(vv)>=12 and mad>1e-8 else np.inf
        for n,indices in enumerate(_segments(d),1):
            d.loc[indices,'segment_id']=n
            if not smooth_window or len(indices)<max(smooth_window,polyorder+3):continue
            ti=d.loc[indices,'time_s'].to_numpy(float)
            dt=np.diff(ti);delta=float(np.median(dt))
            if delta<=0 or not np.allclose(dt,delta,rtol=.045,atol=1e-8):continue
            for raw,smoothed,velocity in [('x_mm','x_mm_smooth','vx_smooth_mm_s'),('y_up_mm','y_up_mm_smooth','vy_smooth_mm_s')]:
                vals=d.loc[indices,raw].to_numpy(float)
                d.loc[indices,smoothed]=savgol_filter(vals,smooth_window,polyorder,mode='interp')
                d.loc[indices,velocity]=savgol_filter(vals,smooth_window,polyorder,deriv=1,delta=delta,mode='interp')
            d.loc[indices,'speed_smooth_mm_s']=np.hypot(d.loc[indices,'vx_smooth_mm_s'],d.loc[indices,'vy_smooth_mm_s'])
            d.loc[indices,'smooth_applied']=True
        flags=[]
        for r in d.itertuples(index=False):
            issues=[]
            if not bool(r.detected):issues.append('缺失：未获得坐标')
            if np.isfinite(getattr(r,'fb_error_px',np.nan)) and r.fb_error_px>=fb_warning_px:
                issues.append('前后向光流误差接近阈值')
            if np.isfinite(r.speed_mm_s) and max_speed_mm_s>0 and r.speed_mm_s>max_speed_mm_s:
                issues.append('超出人工设置的速度核查上限')
            if np.isfinite(r.speed_mm_s) and r.speed_mm_s>robust_limit:
                issues.append('相对该点轨迹的速度尖峰（可能是真实快速动作）')
            if bool(getattr(r,'manual_corrected',False)):
                issues.append('人工修正，建议复核相邻帧速度')
            flags.append('；'.join(issues))
        d['quality_review']=flags
        parts.append(d)
    out=pd.concat(parts,ignore_index=True) if parts else track.copy()
    issues=out[out.quality_review!=''][['frame','time_s','point_id','detected','quality_review','x_px','y_px','speed_mm_s']].copy()
    return out,issues.sort_values(['frame','point_id']).reset_index(drop=True)


def relative_motion(track:pd.DataFrame,reference:str):
    """Subtract visible image landmark reference on SAME frame; never interpolate."""
    ids=list(dict.fromkeys(track.point_id))
    if not reference:return pd.DataFrame()
    if reference not in ids:raise ValueError(f'参考点 {reference} 不属于现有的点名：{ids}')
    ref=track.loc[track.point_id==reference,['frame','detected','x_mm','y_up_mm']].rename(
        columns={'detected':'reference_detected','x_mm':'reference_x_mm','y_up_mm':'reference_y_up_mm'})
    out=track[['frame','time_s','point_id','detected','x_mm','y_up_mm']].merge(ref,on='frame',how='left',validate='many_to_one')
    valid=out.detected.fillna(False)&out.reference_detected.fillna(False)
    out['reference_point_id']=reference
    out['relative_x_mm']=(out.x_mm-out.reference_x_mm).where(valid)
    out['relative_y_mm']=(out.y_up_mm-out.reference_y_up_mm).where(valid)
    out['relative_distance_mm']=np.hypot(out.relative_x_mm,out.relative_y_mm)
    out['relative_speed_mm_s']=np.nan
                                                                                      
    for name,group in out.groupby('point_id',sort=False):
        ordered=group.sort_values('frame')
        good=ordered.relative_x_mm.notna()&ordered.relative_y_mm.notna()
        prev=good.shift(1,fill_value=False)
        dt=ordered.time_s.diff()
        usable=good&prev&(dt>0)
        dx=ordered.relative_x_mm.diff();dy=ordered.relative_y_mm.diff()
        out.loc[ordered.index[usable],'relative_speed_mm_s']=(np.hypot(dx[usable],dy[usable])/dt[usable]).values
    return out.sort_values(['frame','point_id']).reset_index(drop=True)


def multiple_pairs(track:pd.DataFrame,spec:str,default_a:str='',default_b:str=''):
    """semicolon/newline separated A,B pairs, physically interpreted only as 2D projections."""
    from .point_tracking import pair_geometry
    if not spec.strip():
        if not (default_a or default_b):
            ids=list(dict.fromkeys(track.point_id));pairs=[(ids[0],ids[1])] if len(ids)>1 else []
        else:
            ids=list(dict.fromkeys(track.point_id));pairs=[(default_a or ids[0],default_b or ids[1])]
    else:
        pairs=[]
        for chunk in spec.replace('\n',';').split(';'):
            chunk=chunk.strip()
            if not chunk:continue
            names=[x.strip() for x in chunk.split(',')]
            if len(names)!=2 or not all(names):raise ValueError('点对填写格式示例：body,foot_L; wing_hinge,wing_tip')
            if names[0]==names[1]:raise ValueError('点对的两个点不能相同。')
            if tuple(names) not in pairs:pairs.append(tuple(names))
    if len(pairs)>24:raise ValueError('一次最多分析 24 对特征点；请先筛选实际研究的连接关系。')
    pieces=[]
    for a,b in pairs:
        ge=pair_geometry(track,a,b)
        if not ge.empty:
            ge['pair_name']=a+' → '+b
            pieces.append(ge)
    return pd.concat(pieces,ignore_index=True) if pieces else pd.DataFrame()


def screen_cycles(geometry:pd.DataFrame,max_frequency_hz:float=5.,column='separation_mm'):
    """Conservative exploratory periodicity screen, NOT a gait or wingbeat classifier."""
    if not np.isfinite(max_frequency_hz) or max_frequency_hz<=0:raise ValueError('最高待检查频率必须是正数。')
    rows=[]
    if geometry.empty:return pd.DataFrame(columns=['pair_name','status','estimated_frequency_hz','median_period_s','cycles_seen','period_cv','interpretation'])
    for name,g in geometry.groupby('pair_name',sort=False):
        g=g.sort_values('frame')
        t=g.time_s.to_numpy(float);v=g[column].to_numpy(float)
        finite=np.isfinite(v)&np.isfinite(t)
        row=dict(pair_name=name,estimated_frequency_hz=np.nan,median_period_s=np.nan,cycles_seen=0,period_cv=np.nan,
                 status='NO_EVIDENCE',interpretation='未形成足够连续、可核查的周期性证据')
        if finite.sum()<30:
            row['status']='INSUFFICIENT_POINTS';rows.append(row);continue
                                                                           
        idx=np.where(finite)[0];splits=np.split(idx,np.where(np.diff(idx)>1)[0]+1)
        best=max(splits,key=len)
        if len(best)<30:rows.append(row);continue
        tt=t[best];yy=v[best];dt=np.diff(tt)
        if not np.all(dt>0) or not np.allclose(dt,np.median(dt),rtol=.05):
            row['status']='IRREGULAR_TIMING';rows.append(row);continue
        fps=1/float(np.median(dt));min_frames=int(np.ceil(6))
        if fps < 6*max_frequency_hz:
                                                                                                
            frequency_limit=fps/6.
        else:frequency_limit=max_frequency_hz
        if frequency_limit<=0:rows.append(row);continue
                                                                                       
        coef=np.polyfit(tt,yy,1);z=yy-np.polyval(coef,tt)
        if len(z)>=9:z=savgol_filter(z,9,2)
        amplitude=float(np.percentile(z,90)-np.percentile(z,10))
        if amplitude<1e-8:row['status']='LOW_AMPLITUDE';rows.append(row);continue
        prom=max(float(np.std(z))*.45,amplitude*.23)
        distance=max(min_frames,int(np.floor(fps/frequency_limit)))
        peaks,_=find_peaks(z,prominence=prom,distance=distance)
        if len(peaks)<4:
            row['status']='FEW_CYCLES';rows.append(row);continue
        periods=np.diff(tt[peaks]);cv=float(np.std(periods,ddof=1)/np.mean(periods)) if len(periods)>1 else np.nan
        period=float(np.median(periods))
        if period<=0:rows.append(row);continue
        f=1/period
        row.update(estimated_frequency_hz=f,median_period_s=period,cycles_seen=len(periods),period_cv=cv)
        if cv>.3:
            row['status']='IRREGULAR_PERIOD';row['interpretation']='峰间时间波动较大；不宜称为稳定周期运动'
        elif f>frequency_limit*(1+1e-6):
            row['status']='SAMPLING_LIMIT';row['interpretation']='候选频率接近或超过当前采样质量界限'
        else:
            row['status']='TENTATIVE_PERIOD';row['interpretation']='可能存在重复二维投影变化；需确认采样率、信噪比及更多周期'
        rows.append(row)
    return pd.DataFrame(rows)
