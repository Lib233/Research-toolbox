"""Compact scientific evidence figures. Descriptive; never modify original observations.

Independent units are displayed as independent units, not technical repeats.
Line gaps and failed detections remain missing rather than fabricated by smoothing.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rc_context

INK='#243344'; MUTED='#607386'; BLUE='#226889'; ORANGE='#C56B4A'; TEAL='#218A83'
STYLE={'font.family':['DejaVu Sans'], 'font.size':6.8,'axes.labelsize':6.8,
       'xtick.labelsize':6.2,'ytick.labelsize':6.2,'legend.fontsize':6.2,
       'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
       'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,
       'axes.grid':False,'savefig.facecolor':'white','axes.unicode_minus':False}

def _polish(ax):
    ax.tick_params(direction='out',length=2.8,width=.6,colors=INK)
    for spine in ('left','bottom'): ax.spines[spine].set_color(INK)

def specimen_figure(independent,metric='peak_force_N'):
    if metric not in independent:raise ValueError('所选指标不存在：'+metric)
    d=independent[['condition','sample_id',metric]].copy()
    d[metric]=pd.to_numeric(d[metric],errors='coerce')
    d=d[np.isfinite(d[metric])]
    if d.empty:raise ValueError('没有可展示的独立试样。')
    groups=list(dict.fromkeys(d.condition.astype(str)))
    units={'peak_force_N':'N','separation_work_mJ':'mJ','peak_nominal_stress_kPa':'kPa','work_per_nominal_area_J_m2':'J/m²'}
    with rc_context(STYLE):
        fig=plt.figure(figsize=(183/25.4,105/25.4),facecolor='white',layout='constrained')
        grid=fig.add_gridspec(1,2,width_ratios=[1.5,1],wspace=.18)
        ax=fig.add_subplot(grid[0]);right=fig.add_subplot(grid[1]);rng=np.random.default_rng(2026)
        groupmeans=[]
        for i,grp in enumerate(groups):
            vals=d.loc[d.condition.astype(str)==grp,metric].to_numpy(float)
            jig=rng.uniform(-.13,.13,size=len(vals))
            ax.scatter(np.full(len(vals),i)+jig,vals,s=16,edgecolor='white',linewidth=.4,
                       zorder=3,color=BLUE if i%2==0 else ORANGE,alpha=.88)
            mean=float(np.mean(vals));sem=float(np.std(vals,ddof=1)/np.sqrt(len(vals))) if len(vals)>1 else np.nan
            if np.isfinite(sem):
                from scipy.stats import t
                ci=t.ppf(.975,len(vals)-1)*sem
                ax.errorbar(i,mean,yerr=ci,fmt='o',markersize=3.3,color=INK,lw=1.2,capsize=3,zorder=4)
            groupmeans.append((grp,len(vals),mean))
        ax.set_xticks(range(len(groups)),[f'{g}\nn={int(n)}' for g,n,_ in groupmeans]);ax.set_ylabel(f'{metric} ({units.get(metric,"original unit")})')
        ax.set_title('a  独立试样观测',loc='left',fontweight='bold',pad=10)
        right.barh(np.arange(len(groupmeans)),[mean for _,_,mean in groupmeans],height=.42,color=[BLUE if i%2==0 else ORANGE for i in range(len(groupmeans))],alpha=.84)
        right.set_yticks(np.arange(len(groupmeans)),[g for g,_,_ in groupmeans]);right.invert_yaxis()
        right.set_xlabel(f'Mean ({units.get(metric,"original unit")})')
        right.set_title('b  各条件组均值（描述性）',loc='left',fontweight='bold',pad=10)
        for a in (ax,right):_polish(a)
        fig.suptitle('Experimental response • raw independent observations retained',x=.04,ha='left',fontsize=8.5,fontweight='bold')
        fig.text(.04,.015,'Error bars: 95% t CI of specimen means, if n ≥ 2. Group means do not establish significance.',fontsize=6.0,color=MUTED)
        return fig

def motion_figure(frames,bouts,pairs,focus=None):
    d=frames.copy();d['time_s']=pd.to_numeric(d.time_s)
    names=list(dict.fromkeys(d.target_point.astype(str)))
    names=names[:5]                                             
    with rc_context(STYLE):
        fig=plt.figure(figsize=(183/25.4,121/25.4),facecolor='white',layout='constrained')
        gs=fig.add_gridspec(2,2,height_ratios=[1.4,1],width_ratios=[1.5,1.0],hspace=.25,wspace=.22)
        main=fig.add_subplot(gs[0,:]);ax=fig.add_subplot(gs[1,0],sharex=main);geo=fig.add_subplot(gs[1,1],sharex=main)
        for i,n in enumerate(names):
            one=d[d.target_point.astype(str)==n].sort_values('time_s')
            main.plot(one.time_s,one.projected_speed_px_s,lw=1.0,alpha=.83,label=n,color=[BLUE,ORANGE,TEAL,'#806BB0','#8892A0'][i])
            if not bouts.empty:
                for b in bouts[bouts.target_point.astype(str)==n].itertuples(index=False):
                    ax.hlines(i,float(b.start_s),float(b.end_s),linewidth=4,color=TEAL)
        ax.set_yticks(range(len(names)),names)
        ax.set_ylim(-.7,max(len(names)-.25,.8))
        ax.set_xlabel('时间（秒）');ax.set_title('b  投影低速候选时段',loc='left',fontweight='bold',pad=8)
        ax.text(.01,.03,'Candidate ≠ confirmed contact or gait',transform=ax.transAxes,fontsize=5.6,color=MUTED)
        if not pairs.empty:
            for (a,b),g in list(pairs.groupby(['point_a','point_b'],sort=False))[:3]:
                geo.plot(g.time_s,g.projection_distance_px,lw=1.1,label=f'{a}–{b}')
            geo.legend(loc='upper right',frameon=False,fontsize=5.7)
        else:geo.text(.5,.5,'No pair selected',transform=geo.transAxes,ha='center',va='center',color=MUTED)
        geo.set_xlabel('时间（秒）');geo.set_ylabel('Projected pair distance (px)')
        geo.set_title('c  相对几何关系',loc='left',fontweight='bold',pad=8)
        main.set_title('a  已测标记点运动（缺测保留）',loc='left',fontweight='bold',pad=8)
        main.set_ylabel('二维投影速度（像素/秒）');main.legend(loc='upper right',ncol=min(5,len(names)),frameon=False)
        if focus:
            for a in [main,ax,geo]:a.set_xlim(*focus)
        for a in [main,ax,geo]:_polish(a)
        fig.suptitle('Motion relationships | direct measurements and screening candidates',x=.04,ha='left',fontsize=8.1,fontweight='bold')
        fig.text(.04,.006,'Two-dimensional projection only; candidate intervals are defined by the selected speed threshold. Validate against video.',fontsize=5.8,color=MUTED)
        return fig
