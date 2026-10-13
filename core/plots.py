"""Native analysis figures, optimized for readable paper graphics, without invented statistics."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from .figure_engine import create_axes, FigureOptions, PALETTES


def track_figure(df):
    fig,ax=create_axes(FigureOptions())
    d=df[df.detected].dropna(subset=['x_mm','y_up_mm'])
    if not d.empty:
        ax.plot(d.x_mm,d.y_up_mm,color=PALETTES['色盲友好'][0],linewidth=1.45,alpha=.85)
        ax.scatter([d.x_mm.iloc[0]],[d.y_up_mm.iloc[0]],c=PALETTES['色盲友好'][2],s=38,marker='o',zorder=4,label='起点')
        ax.scatter([d.x_mm.iloc[-1]],[d.y_up_mm.iloc[-1]],c=PALETTES['色盲友好'][1],s=44,marker='X',zorder=4,label='终点')
    ax.set(xlabel='水平位置 (mm)',ylabel='竖直位置 (mm)',title='二维投影轨迹')
    ax.set_aspect('equal',adjustable='datalim')
    if not d.empty:ax.legend(loc='best',frameon=False)
    return fig


def force_figure(df):
    fig,ax=create_axes(FigureOptions())
    groups=list(df.condition.unique());colors=FigureOptions().colors
    for i,(condition,sid) in enumerate(df.groupby(['condition','sample_id'],sort=False).groups):
        sub=df[(df.condition==condition)&(df.sample_id==sid)].sort_values('displacement_mm')
        c=colors[groups.index(condition)%len(colors)]
        ax.plot(sub.displacement_mm,sub.force_N,color=c,linewidth=1,alpha=.40)
    for i,g in enumerate(groups):
        ax.plot([],[],color=colors[i%len(colors)],lw=2,label=f'{g}（原始试样曲线）')
    ax.set(xlabel='位移 (mm)',ylabel='仪器力读数 (N)',title='原始力—位移曲线')
    if groups:ax.legend(loc='best',frameon=False)
    return fig


def groups_figure(specimens):
    fig,ax=create_axes(FigureOptions())
    groups=list(specimens.condition.unique());colors=FigureOptions().colors;rng=np.random.default_rng(17)
    for i,g in enumerate(groups):
        y=specimens[specimens.condition==g].value.to_numpy(float)
        c=colors[i%len(colors)]
        if not len(y):continue
        ax.scatter(i+rng.uniform(-.11,.11,size=len(y)),y,color=c,s=20,alpha=.75,zorder=3,edgecolors='white',linewidths=.25)
        ax.plot([i-.22,i+.22],[np.mean(y)]*2,color=c,lw=1.5)
        if len(y)>=2:
            sem=np.std(y,ddof=1)/np.sqrt(len(y))
            ci=stats.t.ppf(.975,len(y)-1)*sem
            ax.errorbar(i,np.mean(y),yerr=ci,fmt='none',ecolor=c,capsize=3,elinewidth=1)
    ax.set_xticks(range(len(groups)),[str(g) for g in groups]);ax.set_xlim(-.6,max(len(groups)-.4,.6))
    ax.set(xlabel='实验组',ylabel='测量值（源数据单位）',title='独立试样数值及组均值 95% CI')
    return fig
