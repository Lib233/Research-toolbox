"""Journal-style scientific figure plates.

 visual-only revision. Measurements, sample grouping and confidence
interval definitions are unchanged; never fabricate experiments or smooth data.
Layouts inspired by the *compositional grammar* of the supplied open-access
robotics/adhesion papers, not copied artwork or images from those papers.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import ticker
from scipy.stats import t
from .figure_engine import PALETTES, FONT_FAMILIES, FigureOptions, INK

SUBTEXT = '#526170'
RULE = '#C8D1D9'
DEFAULT_COLOR = PALETTES['论文经典']


def _label(value):
    return str(value).replace('_', ' ')


def _colors(options):
    return (options or FigureOptions()).colors


def _canvas(layout='editorial', options=None):
    """Layout with intentional hierarchy and exact physical export width.

    The panels remain in a,b,c,d order for GUI axis-label overrides.
    """
    opts = options or FigureOptions()
    fig = plt.figure(figsize=(183/25.4, 128/25.4), facecolor='white')
    if layout == 'balanced':
        g = fig.add_gridspec(2, 2, left=.085,right=.967,bottom=.113,top=.887,
                             width_ratios=[1.02,1],height_ratios=[1,1],wspace=.39,hspace=.67)
        axes = [fig.add_subplot(g[0,0]),fig.add_subplot(g[0,1]),
                fig.add_subplot(g[1,0]),fig.add_subplot(g[1,1])]
    else:
                                                                              
        g = fig.add_gridspec(2, 3, left=.088,right=.971,bottom=.113,top=.896,
                             width_ratios=[1,1,1.07],height_ratios=[1.10,.96],
                             wspace=.60,hspace=.67)
        axes = [fig.add_subplot(g[0,:2]),fig.add_subplot(g[0,2]),
                fig.add_subplot(g[1,0]),fig.add_subplot(g[1,1:])]
    fig._toolbox_grid_locked = True
    fig._toolbox_layout_version = 'v3.2-editorial-grid'
    for letter,ax in zip('abcd',axes):
        ax.set_facecolor('white')
        for side in ('right','top'):
            ax.spines[side].set_visible(False)
        for side in ('bottom','left'):
            ax.spines[side].set_color(INK)
            ax.spines[side].set_linewidth(.72)
        ax.tick_params(direction='out',labelsize=6.6,length=2.9,width=.58,pad=2,
                       color=INK,labelcolor=SUBTEXT)
        ax.xaxis.label.set_fontsize(7.15)
        ax.yaxis.label.set_fontsize(7.15)
        ax.xaxis.labelpad=4.0
        ax.yaxis.labelpad=3.8
        ax.text(-.085,1.135,letter,transform=ax.transAxes,
                fontsize=10.8,fontfamily=FONT_FAMILIES,fontweight='bold',
                color=INK,ha='left',va='bottom',clip_on=False)
                                                                         
        ax.plot([0,.085],[1.065,1.065],color=opts.colors['abcd'.index(letter)%len(opts.colors)],
                lw=1.8,solid_capstyle='round',transform=ax.transAxes,clip_on=False,zorder=5)
        ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=5))
        ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=6))
        ax.grid(False)
    return fig, axes


def _labels(ax,title,x,y):
    ax.set_title(title,loc='left',fontsize=7.55,pad=16.5,color=INK,
                 fontfamily=FONT_FAMILIES,fontweight='medium')
    ax.set_xlabel(x,fontfamily=FONT_FAMILIES)
    ax.set_ylabel(y,fontfamily=FONT_FAMILIES)


def _panel_legend(ax, *, loc='upper right', ncol=1):
    leg=ax.legend(loc=loc,ncol=ncol,frameon=False,fontsize=6.5,
                  handlelength=1.9,labelspacing=.35,columnspacing=.85,
                  borderaxespad=.22)
    if leg:
        for txt in leg.get_texts():txt.set_fontfamily(FONT_FAMILIES)
    return leg


def _sample_points(ax, df, col, groups, colors):
    """Raw independent specimen measurements + sample mean and t-based 95% CI."""
    rng=np.random.default_rng(1703)
    for i,g in enumerate(groups):
        v=df.loc[df.condition==g,col].to_numpy(float)
        if not len(v):continue
        c=colors[i%len(colors)]
        dx=rng.uniform(-.14,.035,len(v))
        ax.scatter(i+dx,v,s=22,facecolors=c,edgecolors='white',linewidths=.42,
                   zorder=5,alpha=.94)
        mean=float(np.mean(v))
        ax.hlines(mean,i-.22,i+.20,color=INK,lw=1.5,zorder=6)
        if len(v)>1:
            margin=t.ppf(.975,len(v)-1)*v.std(ddof=1)/np.sqrt(len(v))
            ax.errorbar(i+.21,mean,yerr=margin,fmt='none',ecolor=INK,
                        elinewidth=1.0,capsize=3.0,capthick=.8,zorder=4)
    ax.set_xticks(range(len(groups)),[f'{_label(g)}\n(n = {len(df.loc[df.condition==g])})' for g in groups])
    ax.xaxis.set_major_locator(ticker.FixedLocator(list(range(len(groups)))))
    ax.set_xlim(-.54,len(groups)-.46)
    ax.margins(y=.16)


def force_storyboard(metrics:pd.DataFrame,traces:pd.DataFrame,options=None):
    """Four panels: corrected cycle traces; specimen-level descriptive comparisons."""
    if metrics.empty:raise ValueError('缺少有效力学样本')
                                                                              
                                                                                      
    specimen=(metrics.groupby(['condition','sample_id'],sort=False,as_index=False)
              [['peak_force_N','separation_work_mJ']].mean())
    groups=list(metrics.condition.drop_duplicates())
    if len(groups)>6:raise ValueError('四联图一次最多显示6组，更多请先筛选')
    colors=_colors(options)
    fig,(a,b,c,d)=_canvas('editorial',options)
    subkeys=['sample_id']+(['cycle_id'] if 'cycle_id' in traces else [])
    for i,g in enumerate(groups):
        sub=traces[traces.condition==g]
        shown=0
        for _,part in sub.groupby(subkeys,sort=False):
            pull=part[part.pull_phase].sort_values('time_s')
            if len(pull)<3:continue
            dx=pull.displacement_mm.to_numpy(float)
            yy=pull.adhesive_tensile_force_N.to_numpy(float)*1e3
            a.plot(dx-dx[0],yy,lw=1.30,color=colors[i%len(colors)],
                   linestyle=['-','--','-.',':'][i%4],alpha=.72,
                   label=f'{_label(g)}' if shown==0 else '_nolegend_')
            shown+=1
            if shown>=7:break
    a.axhline(0,lw=.55,c=RULE,zorder=0)
    _labels(a,'逐轮测试｜经零点校正的力—位移曲线','相对位移 (mm)','正向校正拉伸力 (mN)')
    if a.lines:_panel_legend(a,loc='upper right')
    _sample_points(b,specimen,'peak_force_N',groups,colors)
    b.yaxis.set_major_formatter(ticker.FuncFormatter(lambda z,pos:f'{z*1000:g}'))
    _labels(b,'每块独立试样的平均峰值','实验条件','拉离过程峰值拉伸力 (mN)')
    _sample_points(c,specimen,'separation_work_mJ',groups,colors)
    _labels(c,'各独立试样的正向力—位移积分均值','实验条件','拉离过程正向力—位移积分 (mJ)')
    for i,g in enumerate(groups):
        ss=specimen.loc[specimen.condition==g]
        d.scatter(ss.peak_force_N*1e3,ss.separation_work_mJ,s=33,
                  facecolors=colors[i%len(colors)],edgecolors='white',linewidths=.56,
                  alpha=.93,marker=['o','D','s','^','v','P'][i%6],label=_label(g))
    _labels(d,'独立试样均值  |  峰值与机械功','拉离过程峰值拉伸力 (mN)','拉离过程正向力—位移积分 (mJ)')
    _panel_legend(d,loc='upper left')
    return fig



def single_force_storyboard(metrics:pd.DataFrame,traces:pd.DataFrame,options=None):
    """Single-file analysis plate: actual trace, selected window, peak and numerical integral."""
    if metrics.empty or traces.empty:
        raise ValueError('没有可绘制的力学记录')
    fig,(a,b,c,d)=_canvas('balanced',options)
    colors=_colors(options)
    example=traces
    keys=['condition','sample_id']+(['cycle_id'] if 'cycle_id' in traces else [])
    groups=list(traces.groupby(keys,sort=False,dropna=False))
    example=groups[0][1].sort_values('time_s')
    raw=example['force_N'].to_numpy(float)
    corrected=example['baseline_corrected_force_N'].to_numpy(float)
    time=example['time_s'].to_numpy(float)
    selected=example['pull_phase'].astype(bool).to_numpy()
    a.plot(time,raw,color=colors[0],lw=1.25,label='按读数符号调整后的力')
    a.plot(time,corrected,color=colors[1],lw=1.35,label='扣除力传感器零点后')
    a.axhline(0,color=RULE,lw=.75)
    _labels(a,'首条记录｜测力零点校正前后','时间 (s)','力 (N)')
    _panel_legend(a)
    b.plot(time,corrected,color=colors[0],lw=1.3,label='零点校正后力')
    b.fill_between(time,0,corrected,where=selected,color=colors[1],alpha=.23,label='所选分析时间窗')
    b.axhline(0,color=RULE,lw=.75)
    _labels(b,'首条记录｜拉离过程分析时间窗','时间 (s)','力 (N)')
    _panel_legend(b)
    valid=example.loc[example.pull_phase].sort_values('time_s')
    x=valid.displacement_mm.to_numpy(float)
    f=valid.adhesive_tensile_force_N.to_numpy(float)
    x=x-x[0]
    c.plot(x,f,color=colors[0],lw=1.5)
    c.fill_between(x,0,f,color=colors[0],alpha=.2)
    peak_ix=int(np.argmax(f))
    c.scatter([x[peak_ix]],[f[peak_ix]],color=colors[1],s=25,zorder=5)
    _labels(c,'首条记录｜正向力—位移积分范围','相对位移 (mm)','正向拉伸力 (N)')
    d.scatter(metrics.peak_force_N.to_numpy(float),metrics.separation_work_mJ.to_numpy(float),
              c=colors[0],s=33,edgecolors='white',linewidths=.4)
    _labels(d,'逐轮结果｜峰值力与正向积分','拉离过程峰值拉伸力 (N)','拉离过程正向力—位移积分 (mJ)')
    fig.text(.07,.025,'前三图只展示第一条测试；全部测试数值以 adhesion_metrics.csv 和 force_trace_corrected.csv 为准。',
             fontsize=6.6,color=SUBTEXT)
    return fig

def track_storyboard(df:pd.DataFrame,preview=None,mm_per_pixel=None,options=None):
    colors=_colors(options)
    fig,(a,b,c,d)=_canvas('balanced',options)
    det=df.loc[df.detected].copy()
    valid=df.dropna(subset=['climb_speed_mm_s'])
    if preview is not None:
        import cv2
        a.imshow(cv2.cvtColor(preview,cv2.COLOR_BGR2RGB),interpolation='nearest',aspect='equal')
        a.set_axis_off()
        if mm_per_pixel and mm_per_pixel>0:
            bar_mm=round(max(1,preview.shape[1]*mm_per_pixel*.18),1)
            bar_px=bar_mm/mm_per_pixel
            if bar_px<preview.shape[1]*.7:
                x0=preview.shape[1]*.09;y0=preview.shape[0]*.90
                a.plot([x0,x0+bar_px],[y0,y0],c='white',lw=3.,solid_capstyle='butt')
                a.text(x0,y0-9,f'{bar_mm:g} mm',color='white',fontsize=7.0,
                       fontfamily=FONT_FAMILIES,va='bottom',weight='bold')
    _labels(a,'视频首帧  |  核实标尺与 ROI','','')
    if len(det):
        xx=df.x_mm.where(df.detected);yy=df.y_up_mm.where(df.detected)
        b.plot(xx,yy,lw=1.7,color=colors[0],alpha=.92)
        b.scatter([det.x_mm.iloc[0]],[det.y_up_mm.iloc[0]],marker='o',s=47,
                  facecolors='white',edgecolors=colors[2],linewidths=1.5,zorder=4,label='起点')
        b.scatter([det.x_mm.iloc[-1]],[det.y_up_mm.iloc[-1]],marker='X',s=46,
                  color=colors[1],zorder=4,label='终点')
        _panel_legend(b,loc='best')
        b.set_aspect('equal',adjustable='datalim')
    _labels(b,'运动轨迹  |  二维投影','水平位置 (mm)','竖直位置 (mm)')
    if len(det):
        first=det.iloc[0]
        shifted=(df.y_up_mm-first.y_up_mm).where(df.detected)
        c.plot(df.time_s,shifted,color=colors[0],lw=1.65)
        if (~df.detected).any():
            missing=df.loc[~df.detected,'time_s'].to_numpy(float)
            c.scatter(missing,np.full(len(missing),c.get_ylim()[0]),marker='|',
                      color=colors[1],s=24,label='未检出帧')
    _labels(c,'净竖直位移  |  缺帧断线','时间 (s)','竖直位移 (mm)')
    if len(valid):
        d.plot(df.time_s,df.climb_speed_mm_s,color=colors[1],lw=1.6)
        d.axhline(0,color=RULE,linewidth=.65,linestyle='--')
    _labels(d,'瞬时竖直速度','时间 (s)','攀爬速度 (mm/s)')
    return fig


def statistical_storyboard(specimens:pd.DataFrame,value_label='测量值（原始单位）',options=None):
    if not {'condition','value'}.issubset(specimens):raise ValueError('缺少统计样本列')
    groups=list(specimens.condition.drop_duplicates())
    if len(groups)>6:raise ValueError('科研四联图最多支持6组，建议拆成独立图')
    colors=_colors(options)
    fig,(a,b,c,d)=_canvas('editorial',options)
    _sample_points(a,specimens,'value',groups,colors)
    _labels(a,'独立样本比较  |  原始点、均值、95% CI','实验条件',value_label)
    arr=[specimens.loc[specimens.condition==g,'value'].to_numpy(float) for g in groups]
    rng=np.random.default_rng(4)
    for i,v in enumerate(arr):
        shade=colors[i%len(colors)]
        b.boxplot([v],positions=[i],widths=.44,showfliers=False,patch_artist=True,
                  boxprops={'facecolor':shade,'alpha':.16,'edgecolor':shade,'linewidth':1.05},
                  medianprops={'color':INK,'linewidth':1.45},
                  whiskerprops={'color':SUBTEXT,'linewidth':.95},
                  capprops={'color':SUBTEXT,'linewidth':.85})
        b.scatter(i+rng.uniform(-.105,.105,len(v)),v,s=19,c=shade,
                  edgecolors='white',linewidths=.40,alpha=.93,zorder=3)
    b.set_xticks(range(len(groups)),[_label(g) for g in groups]);b.set_xlim(-.53,len(groups)-.47)
    _labels(b,'分布  |  箱线图','实验条件',value_label)
    for i,v in enumerate(arr):
        x=np.sort(v);y=np.arange(1,len(x)+1)/len(x)
        c.step(x,y,where='post',color=colors[i%len(colors)],linewidth=1.7,
               linestyle=['-','--','-.',':'][i%4],label=_label(groups[i]))
    _labels(c,'经验累积分布','测量值','累积比例')
    _panel_legend(c,loc='upper left')
                                                                                 
    for i,v in enumerate(arr):
        q=np.quantile(v,[.25,.5,.75])
        y=len(arr)-i-1
        d.plot([q[0],q[2]],[y,y],linewidth=9,color=colors[i%len(colors)],
               alpha=.19,solid_capstyle='round',zorder=1)
        d.plot([q[0],q[2]],[y,y],linewidth=2.2,color=colors[i%len(colors)],
               alpha=.92,zorder=2)
        d.scatter([q[1]],[y],marker='D',s=40,facecolors='white',
                  edgecolors=colors[i%len(colors)],linewidths=1.4,zorder=5)
    d.set_yticks(range(len(arr)),[_label(g) for g in groups[::-1]])
    d.tick_params(axis='y',length=0)
    d.spines['left'].set_visible(False)
    d.set_ylim(-.7,len(arr)-.3)
    _labels(d,'分位范围  |  中位数与 Q1–Q3',value_label,'实验条件')
    return fig
