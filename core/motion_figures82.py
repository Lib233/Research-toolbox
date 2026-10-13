""" data-driven research displays: raw vs optional trend, gaps, identities, time."""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize

COLORS=plt.get_cmap('tab10')

def _window(df,start=None,end=None):
    good=df.copy()
    if start is not None:good=good[good.time_s>=start]
    if end is not None:good=good[good.time_s<=end]
    return good

def _segments(g):
    g=g.sort_values('frame')
                                                          
    idx=g.index.to_numpy(); t=g.time_s.to_numpy(float);v=g.detected.fillna(False).to_numpy(bool)
    dt=np.diff(t); dtref=np.median(dt[dt>0]) if np.any(dt>0) else np.nan
    blocks=[];chunk=[]
    for i in range(len(g)):
        contiguous=i>0 and v[i-1] and t[i]>t[i-1] and (not np.isfinite(dtref) or t[i]-t[i-1]<=1.6*dtref)
        if v[i] and (not chunk or contiguous):chunk.append(idx[i])
        else:
            if chunk:blocks.append(chunk)
            chunk=[idx[i]] if v[i] else []
    if chunk:blocks.append(chunk)
    return blocks

def _time_lines(ax,data,xcol,ycol,norm,cmap='viridis',width=2):
    for ids in _segments(data):
        g=data.loc[ids];pts=g[[xcol,ycol]].to_numpy(float)
        if len(pts)<2:continue
        pairs=np.stack([pts[:-1],pts[1:]],axis=1)
        collection=LineCollection(pairs,cmap=cmap,norm=norm,linewidths=width,alpha=.92)
        collection.set_array((g.time_s.to_numpy(float)[:-1]+g.time_s.to_numpy(float)[1:])/2)
        ax.add_collection(collection)

def plot_temporal_tracks(df,preview=None,meta=None,scale=.05,focus_start=None,focus_end=None,show_ref=False):
    """Time-coloured actual XY path, separate point identities, no gap bridging."""
    d=_window(df,focus_start,focus_end)
    fig,axs=plt.subplots(1,2,figsize=(13.2,5.0),layout='constrained',width_ratios=[1.13,1])
    a,b=axs
    if preview is not None:
        import cv2
        a.imshow(cv2.cvtColor(preview,cv2.COLOR_BGR2RGB),origin='upper',alpha=.48)
        h,w=preview.shape[:2];a.set_xlim(0,w);a.set_ylim(h,0)
    elif meta:
        a.set_xlim(0,meta['video_width_px']);a.set_ylim(meta['video_height_px'],0)
    ids=list(dict.fromkeys(d.point_id))
    t=d.time_s.to_numpy(float)
    norm=Normalize(vmin=float(np.nanmin(t)) if len(t) else 0,vmax=float(np.nanmax(t))+1e-6 if len(t) else 1)
    for i,name in enumerate(ids):
        g=d[d.point_id==name].sort_values('frame')
        _time_lines(a,g,'x_px','y_px',norm,width=2.2)
        good=g[g.detected.astype(bool)]
        if good.empty:continue
        a.plot(good.x_px.iloc[0],good.y_px.iloc[0],marker='o',color=COLORS(i%10),markersize=7,mec='white')
        a.plot(good.x_px.iloc[-1],good.y_px.iloc[-1],marker='X',color=COLORS(i%10),markersize=8,mec='white')
        a.annotate(str(name),xy=(good.x_px.iloc[0],good.y_px.iloc[0]),xytext=(8,7),textcoords='offset points',fontsize=9,
                   color=COLORS(i%10),weight='bold',bbox=dict(facecolor='white',alpha=.8,edgecolor='none',pad=1))
        b.plot(g.time_s,g.x_mm,label=f'{name} · x',lw=1.05,color=COLORS(i%10),alpha=.85)
        b.plot(g.time_s,g.y_up_mm,label=f'{name} · y↑',lw=1.05,color=COLORS(i%10),ls='--',alpha=.7)
    a.set(xlabel='视频原图水平坐标（像素）',ylabel='视频原图竖直坐标（像素）',title='A  按时间着色的轨迹｜○ 起点、× 终点')
    a.set_aspect('equal',adjustable='box')
    b.set(xlabel='时间（秒）',ylabel='二维投影位置（毫米）',title='B  各点投影位置（失检保留空白）')
    b.legend(fontsize=7,ncol=2,frameon=False,loc='best');b.grid(alpha=.2)
    fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap='viridis'),ax=a,fraction=.035,pad=.025,label='视频时间（秒）')
    fig.suptitle('Image features defined by the researcher · not automatically identified anatomy',fontsize=11)
    return fig

def plot_motion_quality(track,quality,focus_start=None,focus_end=None):
    d=_window(track,focus_start,focus_end)
    fig,axs=plt.subplots(2,1,figsize=(11.8,6.9),layout='constrained',sharex=True,height_ratios=[1.7,1])
    for i,(name,g) in enumerate(d.groupby('point_id',sort=False)):
        c=COLORS(i%10)
        axs[0].plot(g.time_s,g.speed_mm_s,color=c,alpha=.33,lw=.8,label=f'{name} raw')
        if 'speed_smooth_mm_s' in g:
            axs[0].plot(g.time_s,g.speed_smooth_mm_s,color=c,lw=1.7,label=f'{name} trend (if valid)')
        axs[1].plot(g.time_s,np.where(g.detected.astype(bool),i+1,np.nan),'.',color=c,ms=2.0)
        miss=g[~g.detected.astype(bool)]
        if len(miss):axs[1].scatter(miss.time_s,np.full(len(miss),i+1),marker='x',color='#C44135',s=18)
        flagged=g[g.quality_review.fillna('')!=''] if 'quality_review' in g else g.iloc[:0]
        if len(flagged):axs[0].scatter(flagged.time_s,flagged.speed_mm_s,facecolor='none',edgecolor='#CB4C37',s=24,lw=.7)
    axs[0].set(ylabel='二维速度（毫米/秒）',title='A  相邻帧差分速度与可选趋势线')
    axs[0].grid(alpha=.18);axs[0].legend(fontsize=7,frameon=False,ncol=3)
    axs[1].set(yticks=list(range(1,len(d.point_id.unique())+1)),yticklabels=list(dict.fromkeys(d.point_id)),
               xlabel='视频时间（秒）',title='B  检出时间轴｜红叉：缺测；空心圆：建议复核')
    axs[1].grid(alpha=.12,axis='x')
    fig.suptitle('Review abrupt movements against original frames before interpreting speed peaks',fontsize=11)
    return fig

def plot_relative_motion(relative,pairs,cycles,focus_start=None,focus_end=None):
    fig,axs=plt.subplots(2,1,figsize=(11,7),layout='constrained')
    if relative is not None and not relative.empty:
        rel=_window(relative,focus_start,focus_end)
        for i,(name,g) in enumerate(rel.groupby('point_id',sort=False)):
            if name==g.reference_point_id.iloc[0]:continue
            axs[0].plot(g.time_s,g.relative_x_mm,label=f'{name} ΔX',color=COLORS(i%10),lw=1.3)
            axs[0].plot(g.time_s,g.relative_y_mm,label=f'{name} ΔY',color=COLORS(i%10),lw=1.0,ls='--')
        axs[0].set(title='A  相对位移（目标点减参考点）',ylabel='相对二维投影位移（毫米）')
    else:
        axs[0].text(.5,.5,'Choose a stable visible reference landmark in the video settings.',ha='center',va='center',transform=axs[0].transAxes)
        axs[0].set(title='A  相对运动需要指定有效参考点',ylabel='相对位移（毫米）')
    if axs[0].get_legend_handles_labels()[0]:axs[0].legend(fontsize=8,frameon=False,ncol=3)
    axs[0].grid(alpha=.2)
    if pairs is not None and not pairs.empty:
        d=_window(pairs,focus_start,focus_end)
        for i,(name,g) in enumerate(d.groupby('pair_name',sort=False)):
            axs[1].plot(g.time_s,g.separation_mm,label=name,lw=1.1,color=COLORS(i%10))
        axs[1].set(title='B  点对投影距离（不是三维肢体长度）',ylabel='点对距离（毫米）')
    else:
        axs[1].text(.5,.5,'Choose two identifiable features to calculate projected distance.',ha='center',va='center',transform=axs[1].transAxes)
        axs[1].set(title='B  点对几何关系',ylabel='距离（毫米）')
    if axs[1].get_legend_handles_labels()[0]:axs[1].legend(fontsize=8,frameon=False,ncol=3)
    axs[1].grid(alpha=.2)
    axs[1].set_xlabel('视频时间（秒）')
    fig.suptitle('Relationships between visible features; do not infer adhesion state or 3D kinematics directly',fontsize=11)
    return fig

def plot_cycle_screen(geometry,screen,focus_start=None,focus_end=None):
    fig,axs=plt.subplots(2,1,figsize=(10.8,6.7),layout='constrained')
    if geometry is not None and not geometry.empty:
        d=_window(geometry,focus_start,focus_end)
        for i,(name,g) in enumerate(d.groupby('pair_name',sort=False)):
            axs[0].plot(g.time_s,g.separation_mm,lw=1.1,color=COLORS(i%10),label=name)
        axs[0].legend(fontsize=8,frameon=False);axs[0].grid(alpha=.2)
    axs[0].set(title='A  点对投影距离的实测变化',xlabel='时间（秒）',ylabel='距离（毫米）')
    axs[1].axis('off')
    if screen is None or screen.empty:message='No eligible pair or insufficient observations.'
    else:
        lines=[]
        for r in screen.itertuples(index=False):
            freq=(f'{r.estimated_frequency_hz:.3f} Hz' if np.isfinite(r.estimated_frequency_hz) else 'not determined')
            lines.append(f'{r.pair_name}: {r.status} | {freq} | {r.cycles_seen} peak intervals')
        message='\n'.join(lines[:12])
    axs[1].text(.03,.92,message,va='top',fontsize=9,transform=axs[1].transAxes,linespacing=1.65)
    axs[1].set_title('B  周期候选筛查（不作步态或翼拍分类）',loc='left')
    fig.suptitle('Confirm sufficient FPS / shutter speed; aliasing can mimic or hide wingbeat frequency',fontsize=11)
    return fig
