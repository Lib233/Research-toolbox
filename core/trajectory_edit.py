"""Merge user-verified tracking points; preserve original data and correction audit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def apply_track_corrections(track,edits,mm_per_pixel,climb_axis='up'):
    if not {'frame','time_s','x_px','y_px','x_mm','y_up_mm','detected'}.issubset(track):raise ValueError('跟踪源表缺少必要的时间与位置字段')
    required={'frame','人工_x_px','人工_y_px'}
    if not required.issubset(edits):raise ValueError('人工修正表需要 frame,人工_x_px,人工_y_px')
    if not np.isfinite(mm_per_pixel) or mm_per_pixel<=0:raise ValueError('像素标定必须为正')
    c=edits.copy();c['frame']=pd.to_numeric(c.frame,errors='raise').astype(int)
    if c.frame.duplicated().any():raise ValueError('人工修正有重复帧')
    for col in ('人工_x_px','人工_y_px'):c[col]=pd.to_numeric(c[col],errors='coerce')
    choose=c.dropna(subset=['人工_x_px','人工_y_px'])[['frame','人工_x_px','人工_y_px']]
    if choose.empty:raise ValueError('还没有填写任何有效人工修正坐标')
    if not set(choose.frame).issubset(track.frame):raise ValueError('包含视频以外的帧号')
    if climb_axis not in ('up','down','left','right'):raise ValueError('攀爬正方向非法')
                                                                               
    valid=track[['y_px','y_up_mm']].dropna()
    if valid.empty:raise ValueError('轨迹没有任何已检测帧，无法校准原图纵坐标')
    inferred_heights=valid.y_px.to_numpy(float)+valid.y_up_mm.to_numpy(float)/mm_per_pixel
    frame_height=float(np.median(inferred_heights))
    if np.ptp(inferred_heights)>1e-3:raise ValueError('跟踪表标定比例或原图高度不一致')
    d=track.copy();d['original_x_px']=d.x_px;d['original_y_px']=d.y_px
    d['manual_corrected']=False
    change=[]
    for _,r in choose.iterrows():
        index=d.index[d.frame==r.frame]
        if len(index)!=1:raise ValueError('跟踪表帧号必须唯一')
        ix=index[0];oldx=float(d.at[ix,'x_px']);oldy=float(d.at[ix,'y_px'])
        x=float(r['人工_x_px']);y=float(r['人工_y_px'])
        d.at[ix,'x_px']=x;d.at[ix,'y_px']=y;d.at[ix,'x_mm']=x*mm_per_pixel
        d.at[ix,'y_up_mm']=(frame_height-y)*mm_per_pixel;d.at[ix,'detected']=True;d.at[ix,'manual_corrected']=True
        change.append({'frame':int(r.frame),'original_x_px':oldx,'original_y_px':oldy,
                       'corrected_x_px':x,'corrected_y_px':y})
                                                                                    
    dt=d.time_s.diff();dx=d.x_mm.diff();dy=d.y_up_mm.diff()
    good=d.detected.astype(bool)&d.detected.shift(1,fill_value=False)&(dt>0)
    d['speed_mm_s']=np.where(good,np.hypot(dx,dy)/dt,np.nan)
    velocity={'up':dy,'down':-dy,'right':dx,'left':-dx}[climb_axis]/dt
    d['climb_speed_mm_s']=np.where(good,velocity,np.nan)
    d['position_validated']=d['manual_corrected']
    d['tracking_source']=np.where(d['manual_corrected'],'manual_checked',d.get('tracking_source','automatic'))
    return d,pd.DataFrame(change)
