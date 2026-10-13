""": experiment-facing, reviewable 2-D movement evidence.

Neither landmark displacement nor LK optical flow proves takeoff, attachment,
biological gait, 3-D wing kinematics, or physical calibration. All inference
here is explicitly a candidate for verification against the original video.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize


def select_primary(df, requested=''):
    ids=list(dict.fromkeys(df.point_id.astype(str)))
    if not ids:raise ValueError('未找到已标注的特征点。')
    if requested:
        if requested not in ids:raise ValueError(f'主要运动点“{requested}”不存在；已识别到：{", ".join(ids)}。请填写真实标记点名。')
        return requested,False
    candidates=('body','body_center','body_centre','thorax','center','centre','robot_center','robot_center_demo','躯干','身体','机身')
    for s in candidates:
        match=next((n for n in ids if n.lower()==s.lower()),None)
        if match:return match,True
    if len(ids)>1:
        raise ValueError('已标记多个点但没有明确的身体主点。请在“主要整体运动点名”填写一个真实标记名称，例如 body；不要让翅尖 P1 自动代表身体。可选点名：'+', '.join(ids))
    return ids[0],True


def movement_evidence(track:pd.DataFrame,primary:str,baseline_end_s:float=5.,min_motion_px:float=3.,sustain_frames:int=5):
    """Screen sustained departure from a stable *projected* image position.

    Uses a robust baseline estimated ONLY from detected points before baseline_end_s.
    Rejects insufficient / unstable baselines. This is NOT automatic takeoff
    recognition; a motion event can be caused by animal, camera or identity drift.
    """
    if not math.isfinite(baseline_end_s) or baseline_end_s<=0:raise ValueError('基线结束时刻应大于零秒。')
    if not math.isfinite(min_motion_px) or min_motion_px<=0:raise ValueError('最小位移阈值应大于0像素。')
    if not isinstance(sustain_frames,int) or sustain_frames<3:raise ValueError('连续判定点数至少为3。')
    g=track[track.point_id.astype(str)==primary].sort_values('frame').copy().reset_index(drop=True)
    if g.empty:raise ValueError('选择的主要特征点没有轨迹数据。')
    det=g.detected.fillna(False).astype(bool).to_numpy()
    x=pd.to_numeric(g.x_px,errors='coerce').to_numpy(float)
    y=pd.to_numeric(g.y_px,errors='coerce').to_numpy(float)
    t=pd.to_numeric(g.time_s,errors='coerce').to_numpy(float)
    valid=det & np.isfinite(x)&np.isfinite(y)&np.isfinite(t)
    base=valid & (t<=baseline_end_s)
    out=g[['frame','time_s','point_id','detected','x_px','y_px']].copy()
    for col in ('baseline_x_px','baseline_y_px','displacement_from_baseline_px','speed_px_s'):
        out[col]=np.nan
    out['movement_candidate']=False
    out['quality_note']=''
    out.loc[~valid,'quality_note']='该帧没有可信位置'
    total_duration_s=float(t[np.isfinite(t)][-1]) if np.isfinite(t).any() else None
    last_good_s=float(t[np.where(valid)[0][-1]]) if valid.any() else None
    remaining=(total_duration_s-last_good_s) if total_duration_s is not None and last_good_s is not None else None
    report=dict(primary_point=primary,frames_sampled=len(g),detected_frames=int(valid.sum()),
                last_tracked_time_s=last_good_s, video_analysis_end_s=total_duration_s,untracked_tail_s=remaining,
                detection_rate=float(np.mean(valid)) if len(g) else 0.,
                baseline_end_s=baseline_end_s,minimum_displacement_px=min_motion_px,
                required_consecutive_samples=sustain_frames,movement_candidate_time_s=None,
                status='NOT_ASSESSED',threshold_px=None,baseline_samples=int(base.sum()),
                interpretation='不能仅凭二维位置认定起飞、离台或吸附状态。')
    if base.sum()<max(8,sustain_frames+2):
        report.update(status='BASELINE_INSUFFICIENT',interpretation='基线内有效标点不足，无法可靠检测持续移动；请核对主点和基线时段。')
        return out,report
    bx,by=float(np.median(x[base])),float(np.median(y[base]))
    rb=np.hypot(x[base]-bx,y[base]-by)
    noise=float(1.4826*np.median(np.abs(rb-np.median(rb))))
    spread=float(np.quantile(rb,.9))
    cutoff=max(min_motion_px,spread+5*max(noise,.15))
    report.update(baseline_x_px=bx,baseline_y_px=by,baseline_jitter_robust_px=noise,threshold_px=cutoff)
    if not np.isfinite(cutoff):
        report['status']='INVALID_BASELINE';return out,report
    out['baseline_x_px']=bx;out['baseline_y_px']=by
    disp=np.hypot(x-bx,y-by)
    out['displacement_from_baseline_px']=np.where(valid,disp,np.nan)
    dt=np.diff(t);dxy=np.hypot(np.diff(x),np.diff(y))
    adjacent=valid[1:]&valid[:-1]&(dt>0)&np.isfinite(dxy)
    speed=np.full(len(g),np.nan)
    speed[1:]=np.divide(dxy,dt,out=np.full(len(dt),np.nan),where=adjacent)
    out['speed_px_s']=speed
                                                                              
                                                                              
    trusted=valid.copy()
    if 'fb_error_px' in g:
        fb=pd.to_numeric(g.fb_error_px,errors='coerce').to_numpy(float)
        trusted &= (~np.isfinite(fb))|(fb<=1.5)
    if 'quality_review' in g:
        issues=g.quality_review.fillna('').astype(str).to_numpy()
        trusted &= np.array([not any(k in v for k in ('追踪丢失','前后向光流误差','超出人工设置的速度核查上限')) for v in issues])
    typical_step=float(np.median(dt[dt>0])) if np.any(dt>0) else np.nan
    consecutive=0;candidate=None;candidate_idx=None
    for i in range(len(g)):
        if t[i]<=baseline_end_s or not trusted[i] or disp[i]<cutoff:
            consecutive=0;continue
        if i>0 and (not trusted[i-1] or t[i]<=t[i-1] or
                     (np.isfinite(typical_step) and t[i]-t[i-1] > 1.6*typical_step)):
            consecutive=1
        else:consecutive+=1
        if consecutive>=sustain_frames:
            candidate_idx=i-sustain_frames+1;candidate=float(t[candidate_idx]);break
    if candidate is not None:
        out.loc[candidate_idx:,'movement_candidate']=True
        report.update(status='SUSTAINED_PROJECTED_MOTION_CANDIDATE',movement_candidate_time_s=candidate,
                      interpretation='检测到相对初始参考位置的持续二维移动候选；必须回看原视频确认是否为身体运动、相机运动或跟踪漂移。')
    else:
        report.update(status='NO_SUSTAINED_MOTION_DETECTED',interpretation='未找到符合当前阈值的持续二维移动；不能据此断言目标完全静止。')
    return out,report


def _blocks(g):
    d=g.sort_values('frame').copy()
    valid=(d.detected.fillna(False).to_numpy(bool)
           & np.isfinite(pd.to_numeric(d.x_px,errors='coerce').to_numpy(float))
           & np.isfinite(pd.to_numeric(d.y_px,errors='coerce').to_numpy(float)))
    ts=d.time_s.to_numpy(float);idxs=d.index.to_numpy();dt=np.diff(ts);dt0=np.median(dt[dt>0]) if np.any(dt>0) else np.nan
    blocks=[];cur=[]
    for i in range(len(d)):
        cont=i>0 and valid[i-1] and valid[i] and ts[i]>ts[i-1] and (not np.isfinite(dt0) or ts[i]-ts[i-1]<=1.6*dt0)
        if not valid[i]:
            if cur:blocks.append(cur);cur=[]
        elif not cur or cont:cur.append(idxs[i])
        else:blocks.append(cur);cur=[idxs[i]]
    if cur:blocks.append(cur)
    return blocks


def plot_experiment_story(df,preview,evidence,report,scale_verified=False,scale=.05,focus_start=None,focus_end=None,manual_event_s=None,manual_event_name=''):
    """Four human-readable panels, with a real video crop and data quality cues."""
    name=report['primary_point'];base=df[df.point_id.astype(str)==name].sort_values('frame').copy()
    show=base.copy()
    if focus_start is not None:show=show[show.time_s>=focus_start]
    if focus_end is not None:show=show[show.time_s<=focus_end]
    if show.empty:show=base.copy()
    units='mm' if scale_verified else 'px（未核实标尺）'
    sf=float(scale) if scale_verified else 1.
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','Noto Sans CJK SC','DejaVu Sans']
    fig,ax=plt.subplots(2,2,figsize=(13.4,9.2))
    fig._toolbox_grid_locked=True
    fig.subplots_adjust(left=.085,right=.90,bottom=.09,top=.89,hspace=.53,wspace=.33)
    a,b,c,d=ax.ravel()
    good=base[base.detected.fillna(False)]
    if preview is not None:
        import cv2
        im=cv2.cvtColor(preview,cv2.COLOR_BGR2RGB)
        a.imshow(im)
        if len(good):
            center=good.iloc[0];cx=float(center.x_px);cy=float(center.y_px)
            pad=max(100,int(min(im.shape[:2])*.14))
            a.set_xlim(max(0,cx-pad),min(im.shape[1],cx+pad))
            a.set_ylim(min(im.shape[0],cy+pad),max(0,cy-pad))
            for j,(pt,grp) in enumerate(df.groupby('point_id',sort=False)):
                first=grp[grp.detected.fillna(False)]
                if first.empty:continue
                r=first.iloc[0]
                a.scatter([r.x_px],[r.y_px],s=65,facecolors='none',edgecolors=f'C{j%10}',linewidths=2)
                a.annotate(str(pt),(r.x_px,r.y_px),xytext=(6,-10),textcoords='offset points',fontsize=8,weight='bold')
        a.set(ylabel='原视频 Y (px)')
    else:a.text(.5,.5,'无视频帧预览；请以原视频核对',ha='center',va='center',transform=a.transAxes)
    a.set_title('a  视频局部：人工特征点位置',loc='left',weight='bold')
                                                                           
    goodshow=show[show.detected.fillna(False)]
    if len(goodshow):
        tt=goodshow.time_s.to_numpy(float)
        norm=Normalize(float(np.nanmin(tt)),float(np.nanmax(tt))+.001)
        for block in _blocks(show):
            z=show.loc[block];coords=z[['x_px','y_px']].to_numpy(float)
            if len(coords)>1:
                seg=np.stack([coords[:-1],coords[1:]],axis=1)
                lc=LineCollection(seg,cmap='viridis',norm=norm,linewidth=1.8)
                lc.set_array((z.time_s.to_numpy(float)[1:]+z.time_s.to_numpy(float)[:-1])/2)
                b.add_collection(lc)
        b.scatter([goodshow.x_px.iloc[0]],[goodshow.y_px.iloc[0]],c='#0B837F',s=55,edgecolor='white',zorder=4,label='起点')
        b.scatter([goodshow.x_px.iloc[-1]],[goodshow.y_px.iloc[-1]],marker='X',c='#CE684F',s=67,zorder=4,label='终点')
        xx=goodshow.x_px.to_numpy(float);yy=goodshow.y_px.to_numpy(float)
        span=max(float(np.ptp(xx)),float(np.ptp(yy)),4.)
        b.set_xlim(np.min(xx)-.12*span,np.max(xx)+.12*span)
        b.set_ylim(np.max(yy)+.12*span,np.min(yy)-.12*span)
        b.set_aspect('equal',adjustable='box')
        from mpl_toolkits.axes_grid1.inset_locator import inset_axes
        cax=inset_axes(b,width='3%',height='60%',loc='center right',borderpad=1.2)
        fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap='viridis'),cax=cax,label='时间 (s)')
    b.legend(loc='upper right',fontsize=8,frameon=False)
    b.set(ylabel='原图 Y (px)')
    b.set_title('b  主要点运动路线：'+name,loc='left',weight='bold')
    e=evidence.copy()
    if focus_start is not None:e=e[e.time_s>=focus_start]
    if focus_end is not None:e=e[e.time_s<=focus_end]
    c.plot(e.time_s,e.displacement_from_baseline_px*sf,color='#205D7C',lw=1.5,label='原始点位移')
    cutoff=report.get('threshold_px')
    if cutoff is not None:c.axhline(float(cutoff)*sf,color='#A6A6A6',ls='--',lw=1,label='检测阈值（待核实）')
    onset=report.get('movement_candidate_time_s')
    if onset is not None and np.isfinite(onset):
        c.axvline(float(onset),color='#B96F3A',ls='--',lw=1.2,label=f'运动候选 {onset:.2f}s')
    if manual_event_s is not None:
        c.axvline(float(manual_event_s),color='#0C7E7A',ls='-.',lw=1.8,label='人工确认：'+(manual_event_name or '实验事件'))
    c.set(xlabel='视频时间 (s)',ylabel=f'相对基线二维距离 ({units})')
    c.set_title('c  何时开始明显移动？（候选）',loc='left',weight='bold')
    c.grid(alpha=.17);c.legend(fontsize=7.5,frameon=False,loc='best')
    d.plot(e.time_s,e.speed_px_s*sf,color='#677681',lw=.8,alpha=.65,label='相邻帧原始速度')
    if 'quality_review' in show:
        bad=show[show.quality_review.fillna('')!='']
        if len(bad):d.scatter(bad.time_s,pd.to_numeric(bad.speed_mm_s,errors='coerce')*(1 if scale_verified else 1/scale),
                              c='#C95E47',s=13,marker='x',label='需人工复核')
    if onset is not None and np.isfinite(onset):d.axvline(float(onset),color='#B96F3A',ls='--',lw=1)
    if manual_event_s is not None:d.axvline(float(manual_event_s),color='#0C7E7A',ls='-.',lw=1.5)
    d.set(xlabel='视频时间 (s)',ylabel=f'二维位置变化速率 ({"mm/s" if scale_verified else "px/s；非真实速度"})')
    d.set_title('d  速度及可疑跳点',loc='left',weight='bold')
    d.grid(alpha=.17);d.legend(fontsize=7.5,frameon=False)
    fig.suptitle('二维视频运动分析｜主要身体点与复核证据（不自动证明起飞或三维扑翼）',fontsize=13,weight='bold',y=.965)
    return fig


def write_guide(report,scale_verified,figure_name='FIGURE_motion_multipanel.png'):
    status={'SUSTAINED_PROJECTED_MOTION_CANDIDATE':'发现持续二维移动候选',
            'NO_SUSTAINED_MOTION_DETECTED':'未发现满足阈值的持续移动',
            'BASELINE_INSUFFICIENT':'基线有效数据不足',
            'INVALID_BASELINE':'基线不可用'}.get(report.get('status'),'待复核')
    return f'''视频追踪  · 从这里开始阅读\n\n本次方法：手工命名特征点 + LK 光流自动追踪（不是旧版阈值轮廓中心）\n主要分析点：{report['primary_point']}（请确认该点代表你希望研究的身体部位）\n追踪检出比例：{report['detection_rate']:.1%}（只是检出率，不是位置准确率）
最后一个有效位置：{report.get('last_tracked_time_s')} 秒；本次分析时间末端：{report.get('video_analysis_end_s')} 秒
末端缺少有效轨迹的时长：{report.get('untracked_tail_s')} 秒；若运动发生在这段时间，则不能根据这份追踪计算运动轨迹和速度！
人工核对的实验事件：{report.get('manual_event_name','未填写')}，时刻：{report.get('manual_event_time_s','未填写')} 秒（来自研究者观测，不是程序自动识别）\n二维运动初筛：{status}\n候选开始时刻：{report.get('movement_candidate_time_s') if report.get('movement_candidate_time_s') is not None else '未确定'} s\n结果解释：{report['interpretation']}\n空间标尺：{'已经由用户确认，仍需检查标定平面' if scale_verified else '尚未确认；请先按像素解读。导出的 mm/mm/s 只是按输入比例换算的暂定值！'}\n\n建议阅读顺序：\n1. review_overlay.mp4：确认标记一直跟对同一个物理部位；如有误先重标锚点，不要解释曲线。\n2. motion_review_queue.csv：回到有突跳、缺失或光流偏差的原视频帧核对。\n3. {figure_name}：a 局部原视频，b 主点路线，c 位移候选，d 原始速度和需复核帧。\n4. motion_event_summary.csv：正式记录跟踪点、阈值、基线、候选事件与质量警告。\n5. 多点相对运动和点对图：检查足端与身体、翅尖与翅根的投影关系。\n\n注意：运动候选 ≠ 已证明起飞、离开平台、产生吸附或进入某种步态。\n对于快速扑翼，低帧率/运动模糊/遮挡可能让 LK 漂移或频率发生混叠。\n结果文件保留原始坐标，不会用平滑替代或凭空补齐缺失帧。\n'''
