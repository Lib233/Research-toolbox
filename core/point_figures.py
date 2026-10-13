"""Research diagrams for manual landmark tracking; figures only, no physics inference."""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def plot_points(df,preview,meta,scale):
    fig,axs=plt.subplots(1,2,figsize=(11,4.7),layout='constrained')
    ax,ay=axs
    if preview is not None:
        import cv2
        ax.imshow(cv2.cvtColor(preview,cv2.COLOR_BGR2RGB),origin='upper')
        ax.set(xlabel='图像水平坐标（像素）',ylabel='图像竖直坐标（像素）',title='人工标注的原始视频帧')
    else:
        ax.set(xlabel='图像水平坐标（像素）',ylabel='图像竖直坐标（像素）',title='原始图像坐标系')
        ax.set_xlim(0,meta['video_width_px']);ax.set_ylim(meta['video_height_px'],0)
    for name,g in df.groupby('point_id',sort=False):
        good=g[g.detected.astype(bool)].sort_values('frame')
                                                                                      
        seg=(~g.sort_values('frame').detected.astype(bool)).cumsum()
        ordered=g.sort_values('frame')
        for _,part in ordered[ordered.detected].groupby(seg[ordered.detected]).groups.items():
            p=ordered.loc[part]
            if not p.empty:ax.plot(p.x_px,p.y_px,lw=1.2,alpha=.7)
        if not good.empty:
            ay.plot(g.time_s,g.x_mm,label=f'{name}: x',linewidth=1.1)
            ay.plot(g.time_s,g.y_up_mm,label=f'{name}: y up',linewidth=1.1,linestyle='--')
            ax.scatter(good.x_px.iloc[0],good.y_px.iloc[0],s=35,marker='o')
    ay.set(xlabel='按视频帧率换算的时间（秒）',ylabel='投影位置（毫米）',title='各特征点二维位置')
    ay.grid(alpha=.2);ay.legend(fontsize=8,loc='best')
    fig.suptitle('Tracked user-defined features · missing intervals are not filled',fontsize=11)
    return fig

def plot_kinematics(df,geo):
    fig,axes=plt.subplots(2,1,figsize=(10,6.5),layout='constrained')
    for name,g in df.groupby('point_id',sort=False):
        axes[0].plot(g.time_s,g.speed_mm_s,label=name,lw=1.1)
    axes[0].set(xlabel='时间（秒）',ylabel='二维相邻帧平均速率（毫米/秒）',title='标记点运动速率')
    axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
    if not geo.empty:
        axes[1].plot(geo.time_s,geo.orientation_unwrapped_deg,label='2-D segment orientation',lw=1.1)
        axes[1].set(ylabel='连续展开的投影角（度）',title=f'二维连线方向：{geo.point_a.iloc[0]} → {geo.point_b.iloc[0]}')
    else:
        axes[1].text(.5,.5,'Select 2 distinct physical landmarks for relative geometry',ha='center',va='center',transform=axes[1].transAxes)
        axes[1].set(title='至少需要两个有效点才能计算相对几何',yticks=[])
    axes[1].set(xlabel='时间（秒）');axes[1].grid(alpha=.2)
    return fig
