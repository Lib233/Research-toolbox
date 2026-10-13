"""Marker-guided, multi-point 2-D tracking with explicit manual anchors.

Scientific limits: estimates refer to tracked IMAGE FEATURES (not necessarily the
body centre of mass); no invisible-frame filling, identity inference, or 3-D
reconstruction. LK subpixel numerics are not guaranteed subpixel physical accuracy.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import math
import cv2
import numpy as np
import pandas as pd

FIELDS = {'frame', 'point_id', 'x_px', 'y_px'}

@dataclass
class PointTrackConfig:
    mm_per_pixel: float
    climb_axis: str = 'up'
    step: int = 1
    max_frames: int = 3000
    window_px: int = 25
    pyramid_levels: int = 3
    fb_limit_px: float = 1.5
    min_eigenvalue: float = 1e-4
                                                    
    roi: tuple[int,int,int,int] | None = None
    stationary_threshold_mm_s: float = 0.15
    cancel_event: object | None = None                                         

def prepare_anchors(anchors: pd.DataFrame, width: int, height: int) -> pd.DataFrame:
    if not FIELDS.issubset(anchors.columns):
        raise ValueError('人工标点文件需要 frame、point_id、x_px、y_px 四列。')
    d = anchors[list(FIELDS)].copy()
    d['point_id'] = d.point_id.astype(str).str.strip()
    if d.point_id.eq('').any() or d.point_id.str.contains(r'[/\\\n\r\t]', regex=True).any():
        raise ValueError('特征点名称不得为空或包含路径分隔符/换行。')
    for col in ('frame','x_px','y_px'):
        d[col] = pd.to_numeric(d[col],errors='raise')
        if not np.isfinite(d[col].to_numpy(float)).all():
            raise ValueError(f'{col} 不能包含空白、无穷或无法识别的数字。')
    if (d.frame < 0).any() or not np.all(d.frame == np.floor(d.frame)):
        raise ValueError('frame 必须是从 0 开始的非负整数帧号。')
    d['frame'] = d.frame.astype(int)
    if ((d.x_px < 0)|(d.x_px >= width)|(d.y_px < 0)|(d.y_px >= height)).any():
        raise ValueError(f'手工点坐标超出了原视频 {width}×{height} 像素范围。')
    if d.duplicated(['frame','point_id']).any():
        raise ValueError('同一个特征点在同一视频帧出现了多个不同标注；请保留一条。')
    if d.empty: raise ValueError('请至少在一帧标记一个物理特征点。')
    return d.sort_values(['frame','point_id']).reset_index(drop=True)

def _validate(config: PointTrackConfig):
    c = config
    if not math.isfinite(c.mm_per_pixel) or c.mm_per_pixel <= 0:raise ValueError('必须填写经实际标定的正数 mm/像素。')
    if c.climb_axis not in ('up','down','left','right'):raise ValueError('运动正方向无效。')
    if c.step < 1 or c.max_frames < 1 or c.window_px < 5 or c.window_px > 101 or c.window_px % 2 == 0:
        raise ValueError('采样间隔、最大帧数、LK窗口设置不正确。')
    if not math.isfinite(c.stationary_threshold_mm_s) or c.stationary_threshold_mm_s < 0:
        raise ValueError('停顿判定速度阈值必须是非负数（mm/s）。')
    if c.pyramid_levels < 0 or c.pyramid_levels > 6 or c.fb_limit_px <= 0 or c.min_eigenvalue <= 0:
        raise ValueError('LK金字塔层数/前后向误差/特征质量阈值设置无效。')

def _recompute_one_track(df, scale, height, axis):
    d = df.sort_values('frame').copy()
    d['x_mm'] = d.x_px * scale
    d['y_up_mm'] = (height - d.y_px)*scale
    d['speed_mm_s'] = np.nan
    d['climb_speed_mm_s'] = np.nan
    d['acceleration_mm_s2'] = np.nan
                                                                            
    prev = d[['frame','detected','time_s','x_mm','y_up_mm']].shift(1)
    prev_detected=d.detected.astype(bool).shift(1,fill_value=False)
    valid=d.detected.astype(bool)&prev_detected&(d.time_s>prev.time_s)
    dx = d.x_mm - prev.x_mm; dy = d.y_up_mm - prev.y_up_mm; dt = d.time_s-prev.time_s
    speed = np.hypot(dx,dy)/dt
    signed = {'up':dy, 'down':-dy, 'right':dx, 'left':-dx}[axis]/dt
    d.loc[valid,'speed_mm_s'] = speed.loc[valid]
    d.loc[valid,'climb_speed_mm_s'] = signed.loc[valid]
    prev_speed=d.speed_mm_s.shift(1)
    acceleration=(d.speed_mm_s-prev_speed)/dt
    d.loc[valid & prev_speed.notna(), 'acceleration_mm_s2'] = acceleration.loc[valid & prev_speed.notna()]
    first=d[d.detected.astype(bool)]
    d['net_dx_from_first_mm']=d.x_mm-first.x_mm.iloc[0] if not first.empty else np.nan
    d['net_dy_from_first_mm']=d.y_up_mm-first.y_up_mm.iloc[0] if not first.empty else np.nan
    d['cumulative_path_mm']=np.where(d.detected.astype(bool),
                 (d.speed_mm_s.fillna(0)*dt.fillna(0)).cumsum(),np.nan)
    return d

def recompute_kinematics(track, mm_per_pixel, frame_height, climb_axis='up'):
    if not math.isfinite(mm_per_pixel) or mm_per_pixel<=0:raise ValueError('比例尺必须是正数。')
    if frame_height<=0 or climb_axis not in ('up','down','left','right'):raise ValueError('高度/方向非法。')
    if not {'frame','time_s','point_id','x_px','y_px','detected'}.issubset(track.columns):
        raise ValueError('逐点轨迹缺少必要字段。')
    data=track.copy()
    if data.duplicated(['point_id','frame']).any():raise ValueError('同一点出现重复帧记录。')
    return pd.concat([_recompute_one_track(g, mm_per_pixel, frame_height, climb_axis)
                      for _,g in data.groupby('point_id',sort=False)],ignore_index=True)

def track_marked_points(video_path: str|Path, anchors: pd.DataFrame, c: PointTrackConfig):
    """Return long-form per-point samples, source preview and capture metadata.

    Each anchor resets LK in the specified frame. LK forward-backward consistency
    controls loss; lost points stay lost until another manually verified anchor.
    Every frame is processed even when output sampling step >1.
    """
    _validate(c)
    cap=cv2.VideoCapture(str(video_path))
    if not cap.isOpened():raise ValueError('视频无法打开，请检查路径或本机解码器。')
    try:
        fps=float(cap.get(cv2.CAP_PROP_FPS))
        if not np.isfinite(fps) or fps<=0:raise ValueError('视频帧率无效，无法计算速度。')
        ok,first=cap.read()
        if not ok:raise ValueError('视频没有可读取的画面。')
        h,w=first.shape[:2]
        points=prepare_anchors(anchors,w,h)
        if c.roi is not None:
            l,t,r,b=c.roi
            if not(0<=l<r<=w and 0<=t<b<=h):raise ValueError('ROI 不在原视频范围内。')
            if ((points.x_px<l)|(points.x_px>=r)|(points.y_px<t)|(points.y_px>=b)).any():
                raise ValueError('标点在 ROI 之外。请修改 ROI 或重新标点。')
        ids=list(dict.fromkeys(points.point_id.tolist()))
        starts={(int(row.frame),str(row.point_id)):(float(row.x_px),float(row.y_px)) for row in points.itertuples(index=False)}
        first_seed=min(points.frame)
        total_known=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if points.frame.max()>=c.max_frames:
            raise ValueError('人工标点所在帧超过了本轮最多处理帧数；请增大最大帧数，以免遗漏人工锚点。')
        if total_known>0 and points.frame.max()>=total_known:
            raise ValueError('部分人工标点的帧号超出视频总帧数。')
        cap.set(cv2.CAP_PROP_POS_FRAMES,0)
        last={name:None for name in ids};quality={name:None for name in ids};prev=None
        rows=[];frame_id=0;preview=None
        lk_args=dict(winSize=(c.window_px,c.window_px),maxLevel=c.pyramid_levels,
                     criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,40,0.008),
                     flags=0,minEigThreshold=c.min_eigenvalue)
        while frame_id<c.max_frames:
            if frame_id%8==0 and c.cancel_event is not None and c.cancel_event.is_set():
                raise RuntimeError('用户请求停止视频追踪；本轮结果未完成，不应解释为完整轨迹。')
            ok,frame=cap.read()
            if not ok:break
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
                                                                                                 
            if prev is not None:
                active=[name for name in ids if last[name] is not None]
                if active:
                    src=np.asarray([last[name] for name in active],np.float32).reshape(-1,1,2)
                    new,st,err=cv2.calcOpticalFlowPyrLK(prev,gray,src,None,**lk_args)
                    back,bst,_=cv2.calcOpticalFlowPyrLK(gray,prev,new, None,**lk_args) if new is not None else (None,None,None)
                    for j,name in enumerate(active):
                        valid=(new is not None and back is not None and st[j,0]==1 and bst[j,0]==1)
                        if valid:
                            x,y=map(float,new[j,0]); fb=float(np.linalg.norm(src[j,0]-back[j,0]))
                            valid=np.isfinite([x,y,fb]).all() and 0<=x<w and 0<=y<h and fb<=c.fb_limit_px
                            if c.roi is not None:
                                l,t,r,b=c.roi;valid=valid and l<=x<r and t<=y<b
                        if valid:
                            last[name]=(x,y);quality[name]=(float(fb),float(err[j,0]))
                        else:
                            last[name]=None;quality[name]=None
                                                                                        
            for name in ids:
                key=(frame_id,name)
                if key in starts:last[name]=starts[key];quality[name]=(0.,np.nan)
            if frame_id % c.step==0 or any((frame_id,name) in starts for name in ids):
                for name in ids:
                    pair=last[name];manual=(frame_id,name) in starts
                    fb,lk=quality[name] if quality[name] is not None else (np.nan,np.nan)
                    rows.append(dict(frame=frame_id,time_s=frame_id/fps,point_id=name,
                        detected=pair is not None,x_px=pair[0] if pair else np.nan,
                        y_px=pair[1] if pair else np.nan,frame_width_px=w,frame_height_px=h,
                        tracking_source='人工锚点' if manual else ('LK光流' if pair else '追踪丢失'),
                        position_validated=manual,manual_corrected=False,
                        fb_error_px=fb,lk_error=lk,
                        quality_flag='人工标记' if manual else ('前后向检查通过' if pair else '未检出（不插值）')))
                if preview is None and frame_id>=first_seed:
                    preview=frame.copy()
                    for j,name in enumerate(ids):
                        if last[name] is not None:
                            x,y=last[name];cv2.circle(preview,(round(x),round(y)),6,(0,220,255),2)
                            cv2.putText(preview,name[:18],(round(x)+9,round(y)-7),cv2.FONT_HERSHEY_SIMPLEX,.5,(250,250,250),2)
            prev=gray;frame_id+=1
        if frame_id==0:raise ValueError('未读取到视频帧。')
        d=recompute_kinematics(pd.DataFrame(rows),c.mm_per_pixel,h,c.climb_axis)
        d['projected_motion_label']='位置待核对'
        valid_speed=d.climb_speed_mm_s.notna()
        d.loc[valid_speed & (d.climb_speed_mm_s>c.stationary_threshold_mm_s),'projected_motion_label']='沿正方向移动'
        d.loc[valid_speed & (d.climb_speed_mm_s<-c.stationary_threshold_mm_s),'projected_motion_label']='沿负方向移动'
        d.loc[valid_speed & (d.climb_speed_mm_s.abs()<=c.stationary_threshold_mm_s),'projected_motion_label']='投影近似不动'
        d.loc[~d.detected.astype(bool),'projected_motion_label']='位置丢失'
        meta=dict(video_width_px=w,video_height_px=h,video_fps=fps,frames_read=frame_id,
                  num_points=len(ids),point_ids=ids,anchors_used=len(starts),
                  algorithm='cv2.calcOpticalFlowPyrLK + forward/backward rejection',
                  fps_note='使用容器报告的恒定FPS;可变帧率视频需要外部可靠时间戳校正')
        return d,preview,meta
    finally:cap.release()

def point_summary(df:pd.DataFrame):
    records=[]
    for name,g in df.groupby('point_id',sort=False):
        good=g[g.detected.astype(bool)].sort_values('time_s')
        if len(good):
            dx=float(good.x_mm.iloc[-1]-good.x_mm.iloc[0]);dy=float(good.y_up_mm.iloc[-1]-good.y_up_mm.iloc[0])
        else:dx=dy=float('nan')
        records.append(dict(point_id=name,frames_sampled=len(g),detected_frames=len(good),
           detection_rate=len(good)/len(g),manual_anchor_frames=int(g.position_validated.fillna(False).sum()),
           path_length_mm=float((g.speed_mm_s*g.time_s.diff()).sum()) if len(good) else np.nan,
           net_dx_mm=dx,net_dy_mm=dy,
           mean_speed_mm_s=float(g.speed_mm_s.mean()) if g.speed_mm_s.notna().any() else np.nan,
           missing_frames=int((~g.detected.astype(bool)).sum())))
    return pd.DataFrame(records)

def pair_geometry(df:pd.DataFrame, a:str|None=None,b:str|None=None):
    """2D vector from landmark A to B; oriented angle is measured against image X axis.
    A hinge + B tip can describe projected segment rotation, but *not* 3D wingbeat.
    """
    ids=list(dict.fromkeys(df.point_id))
    if len(ids)<2:return pd.DataFrame()
    a=a or ids[0];b=b or ids[1]
    if a==b or a not in ids or b not in ids:raise ValueError('两点几何计算必须选择两个不同的有效特征点。')
    left=df[df.point_id==a][['frame','time_s','detected','x_mm','y_up_mm']]
    right=df[df.point_id==b][['frame','detected','x_mm','y_up_mm']]
    d=left.merge(right,on='frame',suffixes=('_a','_b'))
    valid=d.detected_a.astype(bool)&d.detected_b.astype(bool)
    dx=(d.x_mm_b-d.x_mm_a).where(valid)
    dy=(d.y_up_mm_b-d.y_up_mm_a).where(valid)
    d['point_a']=a;d['point_b']=b
    d['separation_mm']=np.hypot(dx,dy)
    d['orientation_deg']=np.degrees(np.arctan2(dy,dx))
    d['orientation_unwrapped_deg']=np.nan
    d['angular_velocity_deg_s']=np.nan
                                                                          
    block=(~valid).cumsum()
    for _,ix in d[valid].groupby(block[valid]).groups.items():
        idx=list(ix)
        angles=np.degrees(np.unwrap(np.radians(d.loc[idx,'orientation_deg'].to_numpy(float))))
        d.loc[idx,'orientation_unwrapped_deg']=angles
        if len(idx)>1:
            dt=np.diff(d.loc[idx,'time_s'].to_numpy(float));da=np.diff(angles)
            d.loc[idx[1:],'angular_velocity_deg_s']=np.where(dt>0,da/dt,np.nan)
    return d[['frame','time_s','point_a','point_b','separation_mm','orientation_deg','orientation_unwrapped_deg','angular_velocity_deg_s']]

def apply_point_corrections(track:pd.DataFrame, edits:pd.DataFrame, mm_per_pixel:float, climb_axis='up'):
    if not {'frame','point_id','frame_height_px','time_s','detected','x_px','y_px'}.issubset(track.columns):
        raise ValueError('请提供多点模式生成的 frame_trajectory.csv（带 point_id 与 frame_height_px）。')
    if track.frame_height_px.nunique()!=1:raise ValueError('逐帧轨迹的原视频高度不一致。')
    height=int(track.frame_height_px.iloc[0]);width=int(track.frame_width_px.iloc[0])
    marks=prepare_anchors(edits,width,height)
    d=track.copy()
    d['original_x_px']=d.x_px.copy();d['original_y_px']=d.y_px.copy()
    if 'manual_corrected' not in d:d['manual_corrected']=False
    if 'position_validated' not in d:d['position_validated']=False
    changes=[]
    for r in marks.itertuples(index=False):
        select=(d.frame==r.frame)&(d.point_id==r.point_id)
        if int(select.sum())!=1:raise ValueError(f'帧 {r.frame} 的 {r.point_id} 不在追踪表中；请在视频追踪中减小取帧间隔，或按已存在帧标注。')
        ix=d.index[select][0]
        oldx=float(d.at[ix,'x_px']);oldy=float(d.at[ix,'y_px'])
        d.at[ix,'x_px']=r.x_px;d.at[ix,'y_px']=r.y_px;d.at[ix,'detected']=True
        d.at[ix,'manual_corrected']=True;d.at[ix,'position_validated']=True
        d.at[ix,'tracking_source']='人工校正';d.at[ix,'quality_flag']='人工核验坐标'
        changes.append(dict(frame=r.frame,point_id=r.point_id,original_x_px=oldx,original_y_px=oldy,
                       corrected_x_px=r.x_px,corrected_y_px=r.y_px))
    d=recompute_kinematics(d,mm_per_pixel,height,climb_axis)
    if 'projected_motion_label' in d:
        d['projected_motion_label']='未计算'
        valid=d.climb_speed_mm_s.notna()
        d.loc[valid & (d.climb_speed_mm_s>0.15),'projected_motion_label']='沿正方向移动'
        d.loc[valid & (d.climb_speed_mm_s<-0.15),'projected_motion_label']='沿负方向移动'
        d.loc[valid & (d.climb_speed_mm_s.abs()<=0.15),'projected_motion_label']='投影近似不动'
        d.loc[~d.detected.astype(bool),'projected_motion_label']='位置丢失'
    return d,pd.DataFrame(changes)

def evaluate_point_reference(track:pd.DataFrame, references:pd.DataFrame,
                             anchors:pd.DataFrame, mm_per_pixel:float):
    """Independent manually checked coordinates at frames NOT used as LK anchors.

    Only rows with detected predictions contribute to localization error;
    all missing predictions are reported separately (no optimistic omission).
    """
    if not FIELDS.issubset(references.columns):
        raise ValueError('独立人工精度核对表必须有 frame,point_id,x_px,y_px 四列。')
    width=int(track.frame_width_px.iloc[0]);height=int(track.frame_height_px.iloc[0])
    refs=prepare_anchors(references,width,height)
    anchor_keys=set(zip(anchors.frame.astype(int),anchors.point_id.astype(str)))
    refs=refs[[ (int(r.frame),str(r.point_id)) not in anchor_keys for r in refs.itertuples(index=False)]].copy()
    if refs.empty:
        return dict(status='NO_INDEPENDENT_REFERENCE',n_reference_frames=0,
                    warning='人工参考点全部是训练锚点；不能据此评估自动跟踪的真实误差。'),pd.DataFrame()
    got=track[['frame','point_id','detected','x_px','y_px']]
    merged=refs.merge(got,on=['frame','point_id'],how='left',suffixes=('_manual','_tracked'))
    merged['valid_comparison']=merged.detected.fillna(False).astype(bool)
    merged['error_px']=np.where(merged.valid_comparison,
        np.hypot(merged.x_px_manual-merged.x_px_tracked,merged.y_px_manual-merged.y_px_tracked),np.nan)
    merged['error_mm']=merged.error_px*mm_per_pixel
    v=merged.error_mm.dropna()
    res=dict(status='LABELED_SAMPLE_ONLY',n_reference_frames=len(merged),n_compared=len(v),
        n_missing_tracking=int((~merged.valid_comparison).sum()),
        mae_position_mm=float(v.mean()) if len(v) else np.nan,
        rmse_position_mm=float(np.sqrt(np.mean(v*v))) if len(v) else np.nan,
        p95_position_mm=float(np.percentile(v,95)) if len(v) else np.nan,
        warning='仅在独立人工标注的抽样帧上核对二维位置误差；锚点帧已排除。未标记帧仍可能出错。')
    return res,merged
