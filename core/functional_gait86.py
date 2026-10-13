""" camera-independent motion-to-experiment readout.

Classifies *image-kinematic near-stationary episodes*, NOT physical adhesion/contact.
No interpolation across missing video frames. Optional force is displayed at an
explicit user-provided clock offset; synchronization is not inferred from peaks.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


@dataclass
class BehaviorSettings:
    body: str
    feet: list[str]
    substrate: str = ''
    positive_axis: str = 'right'
    stationary_threshold_px_s: float = 12.0
    min_dwell_s: float = 0.25
    scale_mm_per_px: Optional[float] = None


def _col(df, wanted, options):
    if wanted and wanted in df.columns:return wanted
    for candidate in options:
        if candidate in df.columns:return candidate
    return None


def normalized_landmarks(df: pd.DataFrame, *, fmt='auto', time_col='time_s',
                         point_col='point_id', x_col='x_px', y_col='y_px',
                         coord_unit='px', mm_per_pixel=1.) -> pd.DataFrame:
    """Map long or {point}_x,{point}_y wide camera exports to one strict track contract."""
    df=df.copy()
    if coord_unit not in ('px','mm'):raise ValueError('坐标单位只能选择 px 或 mm。')
    if not np.isfinite(mm_per_pixel) or mm_per_pixel<=0:raise ValueError('毫米/像素必须为正数。')
    tc=_col(df,time_col,['time_s','time','Time','t'])
    if not tc:raise ValueError('找不到时间列，请指定原始文件中的时间列名。')
    fc=_col(df,'frame',['frame','Frame','frame_id'])
    pc=_col(df,point_col,['point_id','landmark','marker','Point'])
    if fmt=='auto':fmt='long' if pc else 'wide'
    if fmt not in ('long','wide'):raise ValueError('未知轨迹格式（long/wide）。')
    frames=pd.to_numeric(df[fc],errors='coerce') if fc else pd.Series(np.arange(len(df)),index=df.index)
    if fmt=='long' and fc is None:
                                                                                            
                                                                           
        tt=pd.to_numeric(df[tc],errors='coerce')
        unique_times=np.sort(tt.dropna().unique())
        frames=tt.map({v:i for i,v in enumerate(unique_times)})
    if fmt=='long':
        if not pc:raise ValueError('长表格式必须有特征点名称列。')
        xx=_col(df,x_col,['x_px','x','X','x_mm'])
        yy=_col(df,y_col,['y_px','y','Y','y_mm','y_up_mm'])
        if not xx or not yy:raise ValueError('未找到 X/Y 列；请填写导出的实际列名。')
        out=pd.DataFrame({'frame':frames,'time_s':pd.to_numeric(df[tc],errors='coerce'),
                 'point_id':df[pc].astype(str).str.strip(),
                 'x_px':pd.to_numeric(df[xx],errors='coerce'),
                 'y_px':pd.to_numeric(df[yy],errors='coerce')})
        if 'detected' in df:
            v=df.detected
            out['detected']=v.map(lambda z: str(z).strip().lower() in ('true','1','yes','ok') if pd.notna(z) else False)
        else:out['detected']=True
                                                                                      
        if yy=='y_up_mm':out['y_px']=-out['y_px'];coord_unit='mm'
        if xx=='x_mm':coord_unit='mm'
    else:
        lookup={}
        for c in df.columns:
            m=re.match(r'^(.+?)[_\s]([xyXY])(?:_(?:px|mm))?$',str(c))
            if m:lookup.setdefault(m.group(1),{})[m.group(2).lower()]=c
        labels=[n for n,cs in lookup.items() if 'x' in cs and 'y' in cs]
        if not labels:raise ValueError('宽表应包含 body_x、body_y、foot_x、foot_y 等成对列。')
        rows=[]
        for name in labels:
            rows.append(pd.DataFrame({'frame':frames,'time_s':pd.to_numeric(df[tc],errors='coerce'),
                'point_id':name,'x_px':pd.to_numeric(df[lookup[name]['x']],errors='coerce'),
                'y_px':pd.to_numeric(df[lookup[name]['y']],errors='coerce'),'detected':True}))
        out=pd.concat(rows,ignore_index=True)
    if coord_unit=='mm':out[['x_px','y_px']]=out[['x_px','y_px']]/mm_per_pixel
    if not np.all(np.isfinite(out.time_s)):raise ValueError('时间列包含空值或非数字，不能确定采样时间。')
    if out.frame.isna().any():raise ValueError('视频帧号列存在非数字。')
    if (out.point_id=='').any():raise ValueError('存在没有名称的跟踪点。')
    out['frame']=out.frame.astype(int)
    if out.duplicated(['point_id','frame']).any():raise ValueError('同一个点在同一帧出现多条记录，无法判断哪个位置正确。')
    out['detected']=out.detected.astype(bool)&out.x_px.notna()&out.y_px.notna()
    out.loc[~out.detected,['x_px','y_px']]=np.nan
    for p,g in out.groupby('point_id'):
        a=g.sort_values('frame')
        if not np.all(np.diff(a.time_s.to_numpy(float))>0):raise ValueError(f'特征点 {p} 的帧时间没有严格递增。')
    frame_times=out.groupby('frame').time_s.agg(['min','max'])
    if np.max(frame_times['max']-frame_times['min'])>1e-5:
        raise ValueError('相同帧的不同特征点使用了不一致的时间戳。')
    return out.sort_values(['frame','point_id']).reset_index(drop=True)


def _axis_value(x,y,axis):
    return {'right':x,'left':-x,'up':-y,'down':y}[axis]


def support_kinematics(track:pd.DataFrame, settings:BehaviorSettings):
    """Return per-foot samples, qualified near-stationary bouts, per-foot metrics & two-foot overlap.

    A near-stationary foot (relative to a substrate marker if supplied) is not
    evidence of actual contact or adhesion. Such claims need independent sensing.
    """
    if settings.positive_axis not in ('right','left','up','down'):raise ValueError('运动方向必须为上下左右。')
    if not np.isfinite(settings.stationary_threshold_px_s) or settings.stationary_threshold_px_s<=0:
        raise ValueError('候选近静止速度阈值须为正数（像素/秒）。')
    if not np.isfinite(settings.min_dwell_s) or settings.min_dwell_s<=0:raise ValueError('最短持续时间必须大于零。')
    if settings.scale_mm_per_px is not None and (not np.isfinite(settings.scale_mm_per_px) or settings.scale_mm_per_px<=0):
        raise ValueError('标尺比例必须为正数。')
    if settings.body in settings.feet:raise ValueError('身体主点不能同时是足端点。')
    ids=set(track.point_id.astype(str))
    required={settings.body,*settings.feet}
    if settings.substrate:required.add(settings.substrate)
    if not settings.feet:raise ValueError('至少填写一个足端点名，例如 foot_L。')
    if len(settings.feet)!=len(set(settings.feet)):raise ValueError('足端点名称不能重复。')
    unknown=required-ids
    if unknown:raise ValueError('轨迹表缺少这些点名：'+', '.join(sorted(unknown)))
    ts=track[['frame','time_s']].drop_duplicates().sort_values('frame').reset_index(drop=True)
    if len(ts)<3:raise ValueError('跟踪时间点太少，无法识别持续运动。')
    dt=np.diff(ts.time_s.to_numpy(float));dpos=dt[dt>0]
    typical=float(np.median(dpos)) if len(dpos) else np.nan
    if not np.isfinite(typical) or typical<=0:raise ValueError('无法确定有效帧间隔。')
    grid=ts.copy()
    for p in sorted(required):
        sub=track.loc[track.point_id==p,['frame','x_px','y_px','detected']].rename(
            columns={'x_px':f'{p}__x','y_px':f'{p}__y','detected':f'{p}__valid'})
        grid=grid.merge(sub,on='frame',how='left',validate='one_to_one')
    def val(k):return grid[f'{k}__valid'].fillna(False).astype(bool)
    def x(k):return pd.to_numeric(grid[f'{k}__x'],errors='coerce')
    def y(k):return pd.to_numeric(grid[f'{k}__y'],errors='coerce')
    bx=x(settings.body);by=y(settings.body)
    bm=val(settings.body)
    if settings.substrate:
        sx=x(settings.substrate);sy=y(settings.substrate);sm=val(settings.substrate)
    else:
        sx=pd.Series(0.,index=grid.index);sy=pd.Series(0.,index=grid.index);sm=pd.Series(True,index=grid.index)
    base_valid=bm&sm
    body_coord=_axis_value(bx-sx,by-sy,settings.positive_axis).where(base_valid)
    parts=[]; bouts=[]
    for foot in settings.feet:
        fx=x(foot)-sx;fy=y(foot)-sy;valid=val(foot)&sm
        d=grid[['frame','time_s']].copy()
        d['foot_point_id']=foot
        d['point_valid']=valid
        d['foot_relative_x_px']=fx.where(valid)
        d['foot_relative_y_px']=fy.where(valid)
        d['body_forward_px']=body_coord
        elapsed=d.time_s.diff();consecutive=elapsed.gt(0)&elapsed.le(typical*1.6+1e-8)
        prev_good=valid.shift(1,fill_value=False)
        good=valid&prev_good&consecutive
        speed=(np.hypot(fx.diff(),fy.diff())/elapsed).where(good)
        d['foot_surface_speed_px_s']=speed
        d['state']='UNKNOWN'
        d.loc[good&(speed>settings.stationary_threshold_px_s),'state']='MOVING'
        d.loc[good&(speed<=settings.stationary_threshold_px_s),'state']='SLOW_UNCONFIRMED'
        candidate=(d.state=='SLOW_UNCONFIRMED').to_numpy(bool)
        starts=np.where(candidate & ~np.r_[False,candidate[:-1]])[0]
        ends=np.where(candidate & ~np.r_[candidate[1:],False])[0]
        for start,end in zip(starts,ends):
                                                                                
            origin=start-1
            if origin<0:continue
            duration=float(d.time_s.iloc[end]-d.time_s.iloc[origin])
            if duration+1e-9<settings.min_dwell_s:continue
            indexes=d.index[start:end+1]
            d.loc[indexes,'state']='NEAR_STATIONARY_CANDIDATE'
            first_pos=grid.index[origin]; last_pos=grid.index[end]
            bp0=body_coord.iloc[first_pos];bp1=body_coord.iloc[last_pos]
            advance=float(bp1-bp0) if np.isfinite(bp0) and np.isfinite(bp1) else np.nan
            dist=float(np.hypot(fx.iloc[last_pos]-fx.iloc[first_pos],fy.iloc[last_pos]-fy.iloc[first_pos]))
            bouts.append({'foot_point_id':foot,'start_frame':int(d.frame.iloc[origin]),
                'end_frame':int(d.frame.iloc[end]),'start_s':float(d.time_s.iloc[origin]),
                'end_s':float(d.time_s.iloc[end]),'duration_s':duration,
                'body_forward_during_candidate_px':advance,
                'foot_endpoint_drift_px':dist,
                'n_slow_intervals':int(end-start+1)})
        parts.append(d)
    frame_table=pd.concat(parts,ignore_index=True).sort_values(['frame','foot_point_id']).reset_index(drop=True)
    bout_df=pd.DataFrame(bouts,columns=['foot_point_id','start_frame','end_frame','start_s','end_s','duration_s',
                  'body_forward_during_candidate_px','foot_endpoint_drift_px','n_slow_intervals'])
                                                                                         
    summary=[]
    for foot,g in frame_table.groupby('foot_point_id',sort=False):
        g=g.sort_values('frame').reset_index(drop=True)
        prevdt=g.time_s.diff().to_numpy(float)
        state=g.state.to_numpy(str)
        valid_interval=np.isfinite(g.foot_surface_speed_px_s.to_numpy(float))
        observed=float(np.nansum(np.where(valid_interval,prevdt,0.)))
        hold=float(np.nansum(np.where(state=='NEAR_STATIONARY_CANDIDATE',prevdt,0.)))
        b=bout_df[bout_df.foot_point_id==foot] if len(bout_df) else bout_df
        summary.append({'foot_point_id':foot,'observed_intervals_s':observed,'near_stationary_s':hold,
          'near_stationary_fraction_of_observed':hold/observed if observed>0 else np.nan,
          'n_near_stationary_bouts':len(b),
          'sum_body_forward_during_candidates_px':float(b.body_forward_during_candidate_px.sum(min_count=1)) if len(b) else np.nan,
          'note':'图像运动学近静止候选；不等于真实接触、吸附或无滑移。'})
    summary_df=pd.DataFrame(summary)
    if settings.scale_mm_per_px is not None:
        k=settings.scale_mm_per_px
        frame_table['body_forward_mm']=frame_table.body_forward_px*k
        frame_table['foot_surface_speed_mm_s']=frame_table.foot_surface_speed_px_s*k
        bout_df['body_forward_during_candidate_mm']=bout_df.body_forward_during_candidate_px*k
        bout_df['foot_endpoint_drift_mm']=bout_df.foot_endpoint_drift_px*k
        summary_df['sum_body_forward_during_candidates_mm']=summary_df.sum_body_forward_during_candidates_px*k
    overlaps=[]
    if len(settings.feet)>=2:
        for i,a in enumerate(settings.feet):
            for b in settings.feet[i+1:]:
                pa=frame_table[frame_table.foot_point_id==a][['frame','time_s','state','foot_surface_speed_px_s']]
                pb=frame_table[frame_table.foot_point_id==b][['frame','state','foot_surface_speed_px_s']]
                shared=pa.merge(pb,on='frame',suffixes=('_a','_b'))
                t=shared.time_s.diff();good=shared.foot_surface_speed_px_s_a.notna()&shared.foot_surface_speed_px_s_b.notna()
                valid_interval=good&t.gt(0)&t.le(typical*1.6+1e-8)
                total=float(t.where(valid_interval,0).sum());aa=shared.state_a=='NEAR_STATIONARY_CANDIDATE';bb=shared.state_b=='NEAR_STATIONARY_CANDIDATE'
                both=float(t.where(valid_interval&aa&bb,0).sum());one=float(t.where(valid_interval&(aa^bb),0).sum())
                overlaps.append({'point_a':a,'point_b':b,'joint_observed_time_s':total,
                    'both_near_stationary_s':both,'one_near_stationary_s':one,
                    'both_fraction':both/total if total else np.nan,
                    'exclusive_fraction':one/total if total else np.nan,
                    'note':'仅描述二维近静止候选阶段的时间关系，不证明交替附着。'})
    return frame_table,bout_df,summary_df,pd.DataFrame(overlaps,
        columns=['point_a','point_b','joint_observed_time_s','both_near_stationary_s','one_near_stationary_s','both_fraction','exclusive_fraction','note'])


def align_force_to_frames(frames:pd.DataFrame,force:pd.DataFrame, *, time_col='time_s',
                          value_col='force_N',shift_s=0.,max_gap_s=.10):
    if time_col not in force or value_col not in force:raise ValueError('外部力数据缺少选择的时间列或信号列。')
    if not np.isfinite(shift_s) or not np.isfinite(max_gap_s) or max_gap_s<=0:raise ValueError('时钟偏移与最大插值间隔无效。')
    d=force[[time_col,value_col]].copy();d.columns=['t','force_value']
    d=d.apply(pd.to_numeric,errors='coerce').dropna().sort_values('t')
    d.t=d.t+shift_s
    if d.t.duplicated().any() or len(d)<2:raise ValueError('力信号时间戳必须唯一且至少有两个有效点。')
    x=d.t.to_numpy(float);y=d.force_value.to_numpy(float)
    t=frames.time_s.to_numpy(float);loc=np.searchsorted(x,t,side='left')
    left=np.maximum(loc-1,0);right=np.minimum(loc,len(x)-1)
                                                                            
    exact=(loc<len(x))&np.isclose(x[right],t,atol=1e-9,rtol=0)
    valid=exact|((loc>0)&(loc<len(x))&((x[right]-x[left])<=max_gap_s+1e-9)&(t>=x[left])&(t<=x[right]))
    pred=np.interp(t,x,y,left=np.nan,right=np.nan);pred[~valid]=np.nan
    result=frames.copy();result['external_force_value']=pred
    result['force_clock_shift_s']=float(shift_s);result['force_interpolated_or_measured']=valid
    return result


def behavior_figures(frames,bouts,summary,force_aligned=None):
    """Produce one readable timeline; no smoothing or fabricated gaps."""
    fig,ax=plt.subplots(3,1,figsize=(10.6,7.8),sharex=True,
                        gridspec_kw={'height_ratios':[1.2,1.25,1]},layout='constrained')
    names=list(dict.fromkeys(frames.foot_point_id))
    for i,name in enumerate(names):
        g=frames[frames.foot_point_id==name].sort_values('frame')
        ax[0].scatter(g.time_s,g.foot_surface_speed_px_s,s=8,alpha=.55,label=name)
        ax[1].scatter(g.time_s,np.full(len(g),i),s=10,c=np.where(g.state=='NEAR_STATIONARY_CANDIDATE','#12857d',
                 np.where(g.state=='MOVING','#cf8158','#A8B1B9')),marker='s')
    ax[0].axhline(0,color='#CBD5E1',lw=.7)
    ax[0].set(ylabel='足端投影速度（像素/秒）',title='足端相对记录表面位置的速度')
    ax[0].legend(fontsize=8,loc='upper right');ax[0].grid(alpha=.15)
    ax[1].set_yticks(range(len(names)),names);ax[1].set_ylim(-.55,len(names)-.45)
    ax[1].set(title='蓝绿：低速候选；橙色：运动；灰色：无有效观测')
    ax[1].grid(alpha=.14,axis='x')
    gb=frames[frames.foot_point_id==names[0]].sort_values('frame')
    valid_body=gb.body_forward_px.dropna()
    origin=float(valid_body.iloc[0]) if len(valid_body) else 0.
    ax[2].plot(gb.time_s,gb.body_forward_px-origin,color='#284c70',lw=1.6,label='机身相对首个有效位置的前进位移（像素）')
    ax[2].set(xlabel='时间（秒）',ylabel='相对初始位置的前进位移（像素）',title='机身相对首个有效观测位置的位移')
    if force_aligned is not None and len(force_aligned):
        ff=force_aligned.drop_duplicates('frame');r=ax[2].twinx()
        r.plot(ff.time_s,ff.external_force_value,color='#BA7353',lw=.85,alpha=.60,label='外部信号（按用户指定时间偏移）')
        r.set_ylabel('External signal (original unit)')
    ax[2].grid(alpha=.15)
    return fig


def behavior_report(settings,summary,bouts,overlap,force_present=False):
    lines=['# 运动阶段与实验机制线索','',
     '本报告只计算可见特征点的二维运动学近静止阶段，不自动判定真实吸附、接触、无滑移或扑翼机理。',
     f'机身点：{settings.body}；足端点：{", ".join(settings.feet)}；表面参考点：{settings.substrate or "没有（默认相机固定）"}。',
     f'阈值：{settings.stationary_threshold_px_s:g} 像素/秒；最短持续 {settings.min_dwell_s:g} 秒。',
     '图像点到真实 mm 的换算只有在空间标尺经实验核实且拍摄平面适用时才可信。','',
     '## 实验意义','近静止候选可以用于比较足端交替运动、机身在足端近静止阶段的前进量，',
     '但只有独立的接触/力/电信号验证后才能讨论哪段真实吸附。','']
    for r in summary.itertuples(index=False):
        frac=r.near_stationary_fraction_of_observed
        lines.append(f'- **{r.foot_point_id}**：近静止候选 {r.near_stationary_s:.3f} s / 已观察 {r.observed_intervals_s:.3f} s；' +
                     f'占比 {frac:.1%}' if np.isfinite(frac) else f'- **{r.foot_point_id}**：暂无足够连续记录。')
        lines.append(f'  共 {r.n_near_stationary_bouts} 段候选。')
    if len(overlap):lines+=['','## 多足端时序关系','`behavior_phase_overlap.csv` 给出两足端同时近静止和仅有一足端近静止的观察时间比例。']
    if force_present:lines+=['','## 外部信号','外部时间平移完全由用户提供。插值后的曲线不证明信号事件与足端行为存在因果或真实同步。']
    lines+=['','## 下一步建议','先查看叠加视频和运动复核队列，检查点是否追踪正确；再复核阈值对结果的敏感性。',
      '实验对比时要使用真正独立试样而非把每帧当成独立样本。',
      '此工具分析的是特征点二维投影，不能代替经标定的三维接触或摩擦力测量。']
    return '\n'.join(lines)+'\n'
