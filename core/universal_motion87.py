""": camera-independent, task-neutral motion relationship readout.

Measurements are 2-D image projection kinematics only.  A low projected-speed
interval does not establish physical contact, gait, lift, adhesion or a mechanism.
No interpolation across missing or nonconsecutive time samples.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

@dataclass
class MotionRelationSettings:
    targets: list[str] | None = None                                                      
    reference: str = ''                                                         
    fixed_marker: str = ''                                                       
    positive_axis: str = 'right'
    slow_threshold_px_s: float = 12.
    min_duration_s: float = .25
    mm_per_pixel: float | None = None


def _forward(dx,dy,axis):
    return {'right':dx,'left':-dx,'down':dy,'up':-dy}[axis]


def analyze_relations(tracks: pd.DataFrame, config:MotionRelationSettings):
    if config.positive_axis not in ('right','left','up','down'):
        raise ValueError('运动正方向应为 right/left/up/down。')
    if not np.isfinite(config.slow_threshold_px_s) or config.slow_threshold_px_s<=0:
        raise ValueError('低速候选阈值必须为正数。')
    if not np.isfinite(config.min_duration_s) or config.min_duration_s<=0:
        raise ValueError('最短持续时间必须为正数。')
    if config.mm_per_pixel is not None and (not np.isfinite(config.mm_per_pixel) or config.mm_per_pixel<=0):
        raise ValueError('毫米/像素标尺必须为正数。')
    if tracks.empty:raise ValueError('没有轨迹记录。')
    needed={'frame','time_s','point_id','x_px','y_px','detected'}
    if not needed.issubset(tracks):raise ValueError('轨迹表未满足标准格式，请先使用 normalized_landmarks 转换。')
    names=sorted(set(tracks.point_id.astype(str)))
    targets=list(dict.fromkeys(config.targets or [n for n in names if n!=config.fixed_marker]))
    if not targets:raise ValueError('没有可分析的运动点；请至少追踪一个点。')
    specified=set(targets)|({config.reference} if config.reference else set())|({config.fixed_marker} if config.fixed_marker else set())
    unknown=sorted(specified-set(names))
    if unknown:raise ValueError('找不到指定点：'+', '.join(unknown)+'。文件实际包含：'+', '.join(names))
    if config.reference and config.reference==config.fixed_marker:
        raise ValueError('相对运动参考点和固定控制点不应使用同一点。')
    stamps=tracks[['frame','time_s']].drop_duplicates().sort_values('frame').reset_index(drop=True)
    if len(stamps)<3:raise ValueError('至少需要三个不同的轨迹时间点。')
    step=np.diff(stamps.time_s.to_numpy(float))
    if np.any(step<=0):raise ValueError('时间戳必须递增。')
                                                                                 
                                                                                
                                                                                
    frame_steps=np.diff(stamps.frame.to_numpy(int))
    if np.any(frame_steps<=0):raise ValueError('视频帧号必须严格递增。')
    expected_stride=int(np.min(frame_steps))
    nominal=float(np.median((step/frame_steps))*expected_stride)
    g=stamps.copy()
    for name in sorted(specified):
        sub=tracks.loc[tracks.point_id==name,['frame','x_px','y_px','detected']].copy()
        sub=sub.rename(columns={'x_px':f'{name}__x','y_px':f'{name}__y','detected':f'{name}__ok'})
        g=g.merge(sub,on='frame',how='left',validate='one_to_one')
    def point(name):
        x=pd.to_numeric(g[f'{name}__x'],errors='coerce').to_numpy(float)
        y=pd.to_numeric(g[f'{name}__y'],errors='coerce').to_numpy(float)
        mask=g[f'{name}__ok'].fillna(False).astype(bool).to_numpy() &np.isfinite(x)&np.isfinite(y)
        return x,y,mask
    if config.fixed_marker:
        anchorx,anchory,anchorm=point(config.fixed_marker)
    else:
        anchorx=np.zeros(len(g));anchory=np.zeros(len(g));anchorm=np.ones(len(g),bool)
    if config.reference:
        bx,by,bm=point(config.reference)
    else:
        bx=by=bm=None
    t=g.time_s.to_numpy(float);frames=g.frame.to_numpy(int)
    continuous=np.r_[False,(np.diff(frames)==expected_stride)&(np.diff(t)>0)&(np.diff(t)<=nominal*1.6+1e-9)]
    rows=[];bouts=[];summaries=[]
    for target in targets:
        tx,ty,ok=point(target)
        seen=ok&anchorm
        x=(tx-anchorx);y=(ty-anchory)
        valid_speed=seen&np.r_[False,seen[:-1]]&continuous
        delta=np.r_[np.nan,np.diff(t)]
        speed=np.full(len(g),np.nan)
        speed[valid_speed]=np.hypot(np.diff(x,prepend=np.nan)[valid_speed],np.diff(y,prepend=np.nan)[valid_speed])/delta[valid_speed]
        direction=np.full(len(g),np.nan)
        direction[valid_speed]=_forward(np.diff(x,prepend=np.nan)[valid_speed],np.diff(y,prepend=np.nan)[valid_speed],config.positive_axis)/delta[valid_speed]
        status=np.full(len(g),'UNKNOWN',dtype=object)
        status[valid_speed & (speed>config.slow_threshold_px_s)]='MOVING'
        slow=valid_speed & (speed<=config.slow_threshold_px_s)
        status[slow]='SLOW_UNCONFIRMED'
        if config.reference:
            relative_ok=seen&bm
            rx=tx-bx;ry=ty-by
            pdist=np.hypot(rx,ry);pangle=np.degrees(np.arctan2(ry,rx))
            pdist[~relative_ok]=np.nan;pangle[~relative_ok]=np.nan
        else:
            pdist=pangle=np.full(len(g),np.nan)
        start_ids=np.where(slow & ~np.r_[False,slow[:-1]])[0]
        end_ids=np.where(slow & ~np.r_[slow[1:],False])[0]
        for st,en in zip(start_ids,end_ids):
            origin=st-1
            if origin<0:continue
            duration=float(t[en]-t[origin])
            if duration+1e-9<config.min_duration_s:continue
            status[st:en+1]='LOW_PROJECTED_SPEED_CANDIDATE'
            drift=float(np.hypot(x[en]-x[origin],y[en]-y[origin]))
            if bm is not None and bm[origin] and bm[en] and anchorm[origin] and anchorm[en]:
                ref_shift=float(_forward((bx[en]-anchorx[en])-(bx[origin]-anchorx[origin]),
                                           (by[en]-anchory[en])-(by[origin]-anchory[origin]),config.positive_axis))
            else:ref_shift=np.nan
            bouts.append(dict(target_point=target,start_frame=int(frames[origin]),end_frame=int(frames[en]),
                 start_s=float(t[origin]),end_s=float(t[en]),duration_s=duration,
                 endpoint_drift_px=drift,reference_forward_change_px=ref_shift,
                 n_observed_intervals=int(en-st+1)))
        out=pd.DataFrame({'frame':frames,'time_s':t,'target_point':target,'position_x_px':np.where(seen,x,np.nan),
               'position_y_px':np.where(seen,y,np.nan),'valid_position':seen,
               'projected_speed_px_s':speed,'forward_speed_px_s':direction,'state':status,
               'distance_to_reference_px':pdist,'angle_to_reference_deg':pangle})
        if config.mm_per_pixel is not None:
            k=config.mm_per_pixel
            for c in ('position_x_px','position_y_px','projected_speed_px_s','distance_to_reference_px'):
                out[c.replace('_px_s','_mm_s').replace('_px','_mm')]=out[c]*k
        rows.append(out)
        observed=float(np.sum(delta[valid_speed]))
        held=float(np.sum(delta[status=='LOW_PROJECTED_SPEED_CANDIDATE']))
        summaries.append(dict(target_point=target,observed_duration_s=observed,
                 low_speed_candidate_duration_s=held,
                 low_speed_fraction_of_observed=held/observed if observed else np.nan,
                 candidate_count=int(sum(b['target_point']==target for b in bouts)),
                 valid_record_fraction=float(np.mean(seen)),
                 interpretation='仅图像投影速度阈值候选，不代表接触、附着、步态或生物学运动机制。'))
    frame_df=pd.concat(rows,ignore_index=True)
    bout_df=pd.DataFrame(bouts,columns=['target_point','start_frame','end_frame','start_s','end_s','duration_s',
                     'endpoint_drift_px','reference_forward_change_px','n_observed_intervals'])
    summary_df=pd.DataFrame(summaries)
                                                                                                    
    relation=[]
    for i,a in enumerate(targets):
        for b in targets[i+1:]:
            ax,ay,am=point(a);cx,cy,cm=point(b)
            good=am&cm
            dist=np.hypot(cx-ax,cy-ay);dist[~good]=np.nan
            ang=np.degrees(np.arctan2(cy-ay,cx-ax));ang[~good]=np.nan
            relation.append(pd.DataFrame({'frame':frames,'time_s':t,'point_a':a,'point_b':b,
                   'projection_distance_px':dist,'projection_angle_deg':ang,
                   'pair_valid':good}))
    pairs=pd.concat(relation,ignore_index=True) if relation else pd.DataFrame(columns=[
        'frame','time_s','point_a','point_b','projection_distance_px','projection_angle_deg','pair_valid'])
    if config.mm_per_pixel is not None and len(pairs):pairs['projection_distance_mm']=pairs.projection_distance_px*config.mm_per_pixel
    return frame_df,bout_df,summary_df,pairs


def plot_relations87(frames,bouts,summary,pairs,signal=None):
    fig,axes=plt.subplots(3,1,figsize=(10.5,8.0),sharex=True,layout='constrained',
                         gridspec_kw={'height_ratios':[1.3,1.1,1]})
    names=list(summary.target_point)
    for i,name in enumerate(names):
        d=frames[frames.target_point==name].sort_values('frame')
        axes[0].scatter(d.time_s,d.projected_speed_px_s,label=name,s=7,alpha=.65)
        colors=np.where(d.state=='LOW_PROJECTED_SPEED_CANDIDATE','#13897d',
                        np.where(d.state=='MOVING','#d38653','#9CA3AF'))
        axes[1].scatter(d.time_s,np.full(len(d),i),c=colors,s=10,marker='s')
    axes[0].set(ylabel='二维投影速度（像素/秒）',title='图像平面运动速度（缺测不连线）')
    axes[0].legend(fontsize=8,ncol=min(4,len(names)));axes[0].grid(alpha=.17)
    axes[1].set_yticks(range(len(names)),names)
    axes[1].set(title='蓝绿：低速候选；橙色：运动；灰色：无有效观测')
    axes[1].grid(axis='x',alpha=.15)
    if len(pairs):
        group=pairs.groupby(['point_a','point_b'],sort=False)
        for (a,b),d in list(group)[:5]:
            axes[2].scatter(d.time_s,d.projection_distance_px,s=5,alpha=.5,label=f'{a} – {b}')
        axes[2].set(ylabel='二维点对投影距离（像素）',title='点对相对运动（二维投影）')
        axes[2].legend(fontsize=8,ncol=2)
                                                                                    
        observed=pairs.projection_distance_px.to_numpy(float)
        observed=observed[np.isfinite(observed)]
        if len(observed) and np.ptp(observed)<1e-7:
            mid=float(np.median(observed))
            pad=max(abs(mid)*.05,.25)
            axes[2].set_ylim(mid-pad,mid+pad)
        axes[2].ticklabel_format(useOffset=False,axis='y')
    else:
        one=frames[frames.target_point==names[0]].sort_values('frame')
        axes[2].plot(one.time_s,one.position_x_px,color='#284c70',lw=1.0)
        axes[2].set(ylabel='相对水平坐标（像素）',title='相对参考标记的坐标变化（如已指定）')
    if signal is not None and len(signal):
        sec=axes[2].twinx();d=signal.drop_duplicates('frame').sort_values('time_s')
        sec.plot(d.time_s,d.external_force_value,color='#BA7353',alpha=.5,lw=.8)
        sec.set_ylabel('External signal (original unit)')
    axes[2].set_xlabel('时间（秒）');axes[2].grid(alpha=.15)
    return fig


def report_relations87(config,frames,bouts,summary,pairs):
    lines=['# 通用运动关系分析 · ','',
       '本报告描述二维像素投影数据，不直接证明吸附、接触、起飞、三维扑翼角或运动机理。',
       '输入特征点：'+', '.join(summary.target_point.astype(str)),
       '运动参考点：'+(config.reference or '未指定')+'；固定画面参考点：'+(config.fixed_marker or '未指定（假设相机固定）'),
       f'低速初筛阈值：{config.slow_threshold_px_s:g} px/s；连续最短时间：{config.min_duration_s:g} s。',
       '', '## 结果怎样看',
       '1. `motion_relation_frames.csv`：每一有效采样的坐标、速度和质量状态。缺失值不插值。',
       '2. `motion_relation_bouts.csv`：各目标达到阈值的低速候选时间段，适合进一步对照原视频。',
       '3. `motion_relation_pairs.csv`：任意选中点对间的二维投影距离、方向角。角度不是三维姿态。',
       '4. `FIGURE_motion_relation_overview`：直接展示点速度、阶段候选和相对几何关系。','',
       '## 科学解释边界',
       '爬行：足端低速可作为可能支撑阶段的线索，但不能证明真实附着。',
       '扑翼：翅根与翅尖的二维投影距离/角度可定量描述；高频运动可能因帧率低发生混叠。',
       '机械机构：标记的参考点和输出点可以用于研究输入—输出的二维轨迹关系，但要先确认几何标定。',
       '所有实验结论必须由原视频或独立传感器核验；低速段标签不是运动模态分类器。','']
    for r in summary.itertuples(index=False):
        lines.append(f'- **{r.target_point}**：有效位置比例 {r.valid_record_fraction:.1%}；'
                     f'低速候选 {r.candidate_count} 段（{r.low_speed_candidate_duration_s:.3f} s）。')
    return '\n'.join(lines)+'\n'
