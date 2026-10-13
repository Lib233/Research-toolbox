"""Publication-first plotting. All raw points are preserved; no statistical independence is inferred.

Nature-inspired layout is not journal approval. Explicitly check the target journal's instructions.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties

                                                                           
                                                                        
                                                                                
def _installed(name):
    return any(f.name.lower() == name.lower() for f in font_manager.fontManager.ttflist)

def _pick(candidates):
    return next((family for family in candidates if _installed(family)), candidates[-1])

WESTERN_FACE = _pick(['Times New Roman', 'Times', 'Liberation Serif', 'DejaVu Serif'])
CHINESE_FACE = _pick(['SimSun', '宋体', 'NSimSun', 'Songti SC', 'STSong',
                      'Noto Serif CJK SC', 'Source Han Serif SC',
                      'AR PL UMing CN', 'AR PL SungtiL GB', 'DejaVu Serif'])
FONT_FAMILIES = [WESTERN_FACE] + ([CHINESE_FACE] if CHINESE_FACE != WESTERN_FACE else [])
FONT_PROPERTIES = FontProperties(family=FONT_FAMILIES)
                                                                        
matplotlib.rcParams['font.family'] = FONT_FAMILIES
matplotlib.rcParams['axes.unicode_minus'] = False
from matplotlib import rc_context
from matplotlib.ticker import MaxNLocator, AutoMinorLocator

                                                                                   
                                                      
PALETTES = {
    '色盲友好': ['#235E80', '#CD6F52', '#2C8B86', '#8465A2', '#B29250', '#5C8199'],
    '论文经典': ['#245783', '#C75A4A', '#258B9C', '#9E7496', '#C79D4B', '#697C89'],
    '冷暖对照': ['#183F68', '#DC7958', '#1A817D', '#E2A950', '#6C75A8', '#9B667C'],
    '黑白打印': ['#1A2128', '#555D66', '#929AA2', '#343C45', '#BBC0C5'],
    '蓝绿渐层': ['#174D72', '#21889B', '#73B9AE', '#D17D50', '#89719B', '#667D8B'],
    '灰阶': ['#202731', '#59616B', '#9EA6AF', '#47515B', '#D1D4D8'],
}

                                                                                  
from cycler import cycler
matplotlib.rcParams['axes.prop_cycle']=cycler(color=PALETTES['色盲友好'])

CHARTS = ('散点图', '折线图', '柱状图', '箱线散点图', '小提琴散点图', '误差棒图', '直方图', '核密度图', '累积分布图', '回归图', '热图', 'Pareto 散点图', '科研四联图')

@dataclass(frozen=True)
class FigureOptions:
    style: str = '期刊简洁'
    palette: str = '色盲友好'
    size: str = '双栏 183 mm'
    dpi: int = 300
    show_title: bool = False
    xlabel: str = ''
    ylabel: str = ''
    panel_axes: tuple = ()

    @classmethod
    def from_config(cls,cfg):
        dpi=int(cfg.get('plot_dpi',300))
        if dpi not in (300,450,600,900): raise ValueError('图片分辨率仅支持 300 / 450 / 600 / 900 dpi')
        return cls(str(cfg.get('plot_style','期刊简洁')),str(cfg.get('plot_palette','色盲友好')),
                   str(cfg.get('plot_size','双栏 183 mm')),dpi,str(cfg.get('plot_title','否'))=='是',
                   str(cfg.get('plot_xlabel','')).strip(),str(cfg.get('plot_ylabel','')).strip(),
                   tuple(tuple(str(cfg.get(f'plot_panel_{p}_{axis}','')).strip() for axis in ('xlabel','ylabel'))
                         for p in 'abcd'))

    @property
    def dimensions(self):
        if self.size=='单栏 89 mm':return 89/25.4, 70/25.4
        if self.size=='双栏 183 mm':return 183/25.4, 118/25.4
        if self.size=='汇报 16:9':return 10,5.625
        raise ValueError('未知图片尺寸：'+self.size)

    @property
    def colors(self):
        if self.palette not in PALETTES:raise ValueError('未知色板：'+self.palette)
        return PALETTES[self.palette]

    @property
    def font_size(self):
        return 11 if self.size=='汇报 16:9' else 7.6


                                                                           
                                                                       
INK = '#1D2530'
MUTED_INK = '#475363'
HAIRLINE = '#C5CFD7'

def _params(options):
    size = options.font_size
    return {
      'font.family':FONT_FAMILIES, 'font.size':size,
      'axes.labelsize':size, 'axes.titlesize':size+.4,
      'xtick.labelsize':size-.4, 'ytick.labelsize':size-.4,
      'legend.fontsize':size-.7,
      'axes.linewidth':.75, 'axes.labelcolor':INK,
      'axes.edgecolor':INK, 'text.color':INK,
      'xtick.color':MUTED_INK, 'ytick.color':MUTED_INK,
      'xtick.major.width':.6, 'ytick.major.width':.6,
      'xtick.major.size':3.0, 'ytick.major.size':3.0,
      'lines.linewidth':1.55, 'lines.markersize':3.8,
      'savefig.facecolor':'white','figure.facecolor':'white',
      'axes.spines.top':False,'axes.spines.right':False,
      'axes.grid':False,'pdf.fonttype':42,'ps.fonttype':42,
      'svg.fonttype':'none','mathtext.fontset':'stix',
      'axes.unicode_minus':False,
    }


def _apply_mixed_font(text, size=None):
    text.set_fontfamily(FONT_FAMILIES)
    if size is not None: text.set_fontsize(size)


def _display_text(text):
                                                                
                                                                 
    return str(text).replace('_', ' ')


def _format_single(ax, opts, fig):
    if opts.xlabel: ax.set_xlabel(opts.xlabel)
    if opts.ylabel: ax.set_ylabel(opts.ylabel)


def _format_panels(fig, opts):
    for index, ax in enumerate(fig.axes[:4]):
        if index >= len(opts.panel_axes): break
        pair=opts.panel_axes[index]
        x,y=pair if len(pair)==2 else ('','')
        if x: ax.set_xlabel(x)
        if y: ax.set_ylabel(y)

def create_axes(options=FigureOptions()):
    with rc_context(_params(options)):
        fig,ax=plt.subplots(figsize=options.dimensions)
    ax.set_prop_cycle(color=options.colors)
    fig.set_facecolor('white')
    return fig,ax


def refine_figure(fig,options=FigureOptions()):
    """Style only. Never smooth, interpolate, reorder, or modify measurements."""
    grid_locked=getattr(fig,'_toolbox_grid_locked',False)
    if not grid_locked:fig.set_size_inches(*options.dimensions,forward=True)
    fig.set_facecolor('white')
    data_axes=[ax for ax in fig.axes if ax.get_label()!='<colorbar>' and ax.get_visible()]
                                                                             
                                                                          
    if grid_locked:_format_panels(fig,options)
    elif len(data_axes)==1:_format_single(data_axes[0],options,fig)
    with rc_context(_params(options)):
        for ax in fig.axes:
            ax.set_facecolor('white')
            if not grid_locked and not options.show_title and options.style!='汇报展示':ax.set_title('')
            for spine in ('top','right'):ax.spines[spine].set_visible(False)
            for spine in ('bottom','left'):
                ax.spines[spine].set_linewidth(.72)
                ax.spines[spine].set_color(INK)
            ax.tick_params(axis='both',direction='out',length=3.0,width=.6,
                           color=INK,labelcolor=MUTED_INK,labelsize=options.font_size-.4)
            ax.grid(False)
            for txt in [ax.xaxis.label,ax.yaxis.label,ax.title,ax._left_title,ax._right_title]:
                _apply_mixed_font(txt)
                txt.set_color(INK)
            for txt in ax.get_xticklabels()+ax.get_yticklabels():_apply_mixed_font(txt)
            for txt in ax.texts:_apply_mixed_font(txt)
            for ln in ax.lines:
                if float(ln.get_linewidth()) > 0:
                    ln.set_linewidth(max(.65,min(float(ln.get_linewidth()),2.2)))
            if ax.get_legend():
                legend=ax.get_legend()
                legend.set_frame_on(False)
                for txt in legend.get_texts():_apply_mixed_font(txt,options.font_size-.6)
                if legend.get_title():_apply_mixed_font(legend.get_title(),options.font_size-.4)
            if options.style in ('数据强调','工程对比风'):
                ax.grid(axis='y',color='#E0E6EA',linewidth=.44,alpha=.48,zorder=0)
        if not grid_locked:
                                        
                                               
            engine=fig.get_layout_engine() if hasattr(fig,'get_layout_engine') else None
            compatible=all(ax.get_subplotspec() is not None for ax in fig.axes)
            if engine is None and compatible:
                try:fig.tight_layout(pad=1.5)
                except Exception:pass
    return fig

def export_figure(fig,prefix,options=FigureOptions()):
    """Export lossless raster and editable vector images. PDF/SVG must retain text."""
    from .common import save_json
    p=Path(prefix);p.parent.mkdir(parents=True,exist_ok=True)
    if getattr(fig,'_toolbox_grid_locked',False):
        options=FigureOptions(style=options.style,palette=options.palette,size='双栏 183 mm',dpi=options.dpi,show_title=options.show_title,
                              xlabel=options.xlabel,ylabel=options.ylabel,panel_axes=options.panel_axes)
    with rc_context(_params(options)):
        refine_figure(fig,options)
        for fmt in ('png','tiff','pdf','svg'):
            fig.savefig(str(p)+'.'+fmt,format=fmt,dpi=options.dpi,
                 facecolor='white',bbox_inches=None,pad_inches=0,
                 **({'pil_kwargs':{'compression':'tiff_lzw'}} if fmt=='tiff' else {}))
    save_json({'style':options.style,'palette':options.palette,'size':options.size,
            'dpi':options.dpi,'effective_latin_font':WESTERN_FACE,'effective_chinese_font':CHINESE_FACE,
            'requested_fonts':'Times New Roman + 宋体（SimSun）', 'axis_title_overrides':{'x':options.xlabel,'y':options.ylabel,'panels':options.panel_axes},
            'export_formats':['png','tiff','pdf','svg'],
            'pdf_fonttype':42,'svg_fonttype':'none',
            'notice':'期刊友好模板不构成 Nature 或任何期刊的接收保证；图形含义、标定与单位需人工核查。'},str(p)+'_figure_settings.json')
    plt.close(fig)


def _numeric(frame,name):
    if not name or name not in frame:raise ValueError('找不到绘图数值列：'+str(name))
    v=pd.to_numeric(frame[name],errors='coerce')
    return v


def _sanitize(df,cols):
    d=df.copy();invalid=pd.Series(False,index=d.index)
    for c in cols:
        d[c]=_numeric(d,c)
        invalid|=~np.isfinite(d[c])
    skipped=int(invalid.sum())
    if skipped:d=d.loc[~invalid].copy()
    if len(d)<2:raise ValueError('有效绘图数据不足2行，请核对数据及所选列。')
    return d,skipped


def _get_sample_level(d,cfg,values):
    sid=cfg.get('chart_sample_id','').strip();group=cfg.get('chart_group','').strip()
    cat=group if group and group in d else cfg.get('chart_x','').strip()
    if cat not in d:raise ValueError('分组统计图需要有效的分组列或 X 类别列。')
    if sid:
        if sid not in d:raise ValueError('未找到独立样本编号列：'+sid)
        if d[[cat,sid]].isna().any().any():raise ValueError('独立样本编号和组别不允许缺失。')
        d=d.groupby([cat,sid],sort=False,as_index=False,dropna=False)[values].mean()
        kind='独立样本'
    else:kind='记录行（不代表独立样本）'
    return d,cat,kind


def _limit_levels(d,col):
    levels=list(d[col].drop_duplicates())
    if len(levels)>22:raise ValueError('超过22个类别，建议先筛选数据，或采用散点/热图展示。')
    return levels


def _color(i,options):return options.colors[i%len(options.colors)]


def make_chart(data:pd.DataFrame,cfg:dict):
    """Plot with transparent data handling. Returns fig, QC report; no inferential claims."""
    opts=FigureOptions.from_config(cfg)
    typ=cfg.get('chart_type','箱线散点图')
    if typ not in CHARTS:raise ValueError('尚不支持的图类型：'+str(typ))
    if typ=='科研四联图':
        from .storyboard import statistical_storyboard
        x=cfg.get('chart_x','').strip();y=cfg.get('chart_y','').strip()
        sid=cfg.get('chart_sample_id','').strip()
        if not x or not y or not sid:
            raise ValueError('科研四联图需要明确填写分组、响应指标、独立样本 ID，避免伪重复。')
        for name in (x,y,sid):
            if name not in data:raise ValueError('绘图数据缺少列：'+name)
        rows=data[[x,y,sid]].copy();rows[y]=pd.to_numeric(rows[y],errors='coerce')
        if rows.isna().any().any() or not np.isfinite(rows[y]).all():
            raise ValueError('科研四联图不自动删除异常行，请先用数据质检检查组、ID、数值。')
        unique=rows.groupby([x,sid],as_index=False,sort=False)[y].mean()
        specimens=unique.rename(columns={x:'condition',y:'value',sid:'sample_id'})
        if specimens.condition.nunique()<2:raise ValueError('科研四联图需要至少两个条件组')
        fig=statistical_storyboard(specimens,cfg.get('chart_ylabel') or y,options=opts)
        if cfg.get('chart_xlabel'): fig.axes[0].set_xlabel(cfg['chart_xlabel'])
        report={'chart_type':typ,'input_rows':len(data),'independent_units':len(specimens),
                'groups':{str(k):int(v) for k,v in specimens.groupby('condition').size().items()},
                'statistical_unit':'独立试样水平（按组别+试样ID求技术重复均值）',
                'warnings':['同一样本跨组的配对/重复测量设计需另行确认，不得直接按独立组推断。',
                            '图中均值95% CI基于t分布；未进行正态性假设确认，不显示p值。']}
        return fig,report
    x=cfg.get('chart_x','').strip();y=cfg.get('chart_y','').strip();g=cfg.get('chart_group','').strip()
    if typ not in ('直方图','核密度图','累积分布图') and not x:raise ValueError('请指定 X 列')
    if typ not in ('热图',) and not y:raise ValueError('请指定 Y 数值列')
    required=[y] if typ in ('直方图','核密度图','累积分布图','箱线散点图','小提琴散点图','柱状图','误差棒图') else [x,y]
    if typ=='热图':required=[c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])]
    if not required:raise ValueError('热图至少需要两个数值列。')
    d,skipped=_sanitize(data,required)
    if g and g not in d:raise ValueError('未找到分组列：'+g)
    fig,ax=create_axes(opts);summary={'chart_type':typ,'input_rows':len(data),'removed_nonfinite_rows':skipped,
      'displayed_rows':len(d),'statistical_unit':'未声明','warnings':[],'style':opts.style}
    if skipped:summary['warnings'].append(f'已排除 {skipped} 行缺失/非有限值；原始表未修改。')
    if typ in ('箱线散点图','小提琴散点图','柱状图','误差棒图'):
        dat,category,kind=_get_sample_level(d,cfg,[y]);levels=_limit_levels(dat,category)
        summary['statistical_unit']=kind
        if kind!='独立样本':summary['warnings'].append('未填写独立样本 ID：图中 n 为记录行数，不能视作生物学独立样本数。')
        elif d.groupby(cfg['chart_sample_id'])[category].nunique().gt(1).any():
            summary['warnings'].append('同一试样 ID 跨越多个条件组：可能为配对/重复测量，分组绘图不代表独立组统计。')
        arr=[dat.loc[dat[category]==v,y].to_numpy(float) for v in levels]
        seed=np.random.default_rng(17)
        for i,values in enumerate(arr):
            c=_color(i,opts)
            if typ=='箱线散点图':
                ax.boxplot(values,positions=[i],widths=.45,showfliers=False,patch_artist=True,
                  boxprops={'facecolor':c,'alpha':.2,'edgecolor':c,'linewidth':1.0},
                  medianprops={'color':INK,'linewidth':1.5},
                  whiskerprops={'color':c},capprops={'color':c})
            elif typ=='小提琴散点图':
                if len(values)<6:summary['warnings'].append(f'{levels[i]} 仅{len(values)}个数据点；小提琴核密度形状可能误导，优先选择原始散点。')
                if len(values)>=3 and np.std(values)>0:
                    coll=ax.violinplot([values],positions=[i],widths=.62,showextrema=False)['bodies'][0]
                    coll.set_facecolor(c);coll.set_edgecolor(c);coll.set_alpha(.18)
                ax.plot([i-.23,i+.23],[np.median(values)]*2,color=c,lw=1.4)
            elif typ in ('柱状图','误差棒图'):
                mean=float(np.mean(values)); sd=float(np.std(values,ddof=1)) if len(values)>1 else np.nan
                err=str(cfg.get('chart_error','95% CI'))
                if err=='SD':margin=sd
                elif err=='SEM':margin=sd/np.sqrt(len(values))
                elif err=='无':margin=np.nan
                else:margin=float(stats.t.ppf(.975,len(values)-1)*sd/np.sqrt(len(values))) if len(values)>1 else np.nan
                if typ=='柱状图':
                    ax.bar(i,mean,width=.62,edgecolor=c,color=c,alpha=.18,linewidth=1.15)
                    if np.isfinite(margin):ax.errorbar(i,mean,yerr=margin,fmt='none',ecolor='#263343',capsize=3,lw=.8)
                else:
                    ax.errorbar(i,mean,yerr=margin if np.isfinite(margin) else None,fmt='o',color=c,
                        capsize=4,markersize=5,lw=1.1)
            if typ!='误差棒图':
                jitter=seed.uniform(-.11,.11,size=len(values))
                ax.scatter(i+jitter,values,s=26,color=c,alpha=.91,edgecolors='white',linewidths=.5,zorder=5)
        ax.set_xticks(range(len(levels)),[_display_text(v) for v in levels]);ax.set_xlim(-.65,len(levels)-.35)
        ax.set_xlabel(cfg.get('chart_xlabel') or category)
        ax.set_ylabel(cfg.get('chart_ylabel') or y)
        summary['groups']={str(level):len(a) for level,a in zip(levels,arr)}
        summary['error_bar']=cfg.get('chart_error','95% CI') if typ in ('柱状图','误差棒图') else '无'
        if typ in ('柱状图','误差棒图') and any(len(v)<2 for v in arr):summary['warnings'].append('存在只有1个独立单位的组，无法计算该组的误差。')
    elif typ=='热图':
        if len(required)<2:raise ValueError('热图需要至少两列数值')
        r=d[required].corr(method='pearson');cmap='coolwarm' if opts.palette!='灰阶' else 'Greys'
        image=ax.imshow(r.values,cmap=cmap,vmin=-1,vmax=1)
        ax.set_xticks(range(len(required)),required,rotation=42,ha='right');ax.set_yticks(range(len(required)),required)
        for i in range(len(required)):
            for j in range(len(required)):
                v=r.iloc[i,j]
                if np.isfinite(v):ax.text(j,i,f'{v:.2f}',ha='center',va='center',fontsize=opts.font_size-.4,color='white' if abs(v)>.8 else '#1F2937')
        fig.colorbar(image,ax=ax,shrink=.74,label='Pearson r')
        summary['warnings'].append('热图仅为 Pearson 线性相关描述；未校正多重检验，不代表因果。')
    else:
        groups=list(d[g].drop_duplicates()) if g else [None]
        if len(groups)>16:raise ValueError('分组数过多（超过16组），请先筛选。')
        if typ in ('散点图','折线图','回归图','Pareto 散点图'):
            d[x]=_numeric(d,x);d=d.loc[np.isfinite(d[x])].copy()
            if len(d)<2:raise ValueError('X 必须为数值且至少有两条有效记录')
        if typ=='Pareto 散点图':
            from .optimization import _pareto
            goal_x=cfg.get('chart_goal_x','max');goal_y=cfg.get('chart_goal_y','max')
            xy=d[[x,y]].to_numpy(float);keep=_pareto(xy,[goal_x,goal_y]);ax.scatter(d[x],d[y],s=19,c='#9CA6B0',alpha=.42,label='候选点',linewidths=0)
            ax.scatter(d.loc[keep,x],d.loc[keep,y],s=39,facecolors='white',edgecolors=opts.colors[0],linewidths=1.15,label='非支配候选点')
            ax.legend(frameon=False)
            summary['pareto_points']=int(keep.sum());summary['warnings'].append('仅按输入点集计算非支配解；不代表真实连续最优前沿。')
        else:
            for i,group in enumerate(groups):
                sub=d[d[g]==group] if g else d
                color=_color(i,opts);label=str(group) if group is not None else None
                if typ=='散点图':ax.scatter(sub[x],sub[y],s=27,color=color,alpha=.87,label=label,edgecolors='white',linewidths=.3)
                elif typ=='折线图':
                    sub=sub.sort_values(x,kind='stable');ax.plot(sub[x],sub[y],color=color,linewidth=1.75,marker='o',markersize=2.8,label=label)
                    if sub[x].duplicated().any():summary['warnings'].append('X 包含重复值：折线图按 X 排序后连接原始观测，不作均值合并或插值。')
                elif typ=='回归图':
                    if len(sub)<3 or sub[x].nunique()<3:raise ValueError('回归图每组至少3行和3个不同的 X 值。')
                    xx=sub[x].to_numpy(float);yy=sub[y].to_numpy(float)
                    fit=stats.linregress(xx,yy)
                    ax.scatter(xx,yy,color=color,s=19,alpha=.78,label=label)
                    grid=np.linspace(xx.min(),xx.max(),140);pred=fit.intercept+fit.slope*grid
                    ax.plot(grid,pred,color=color,lw=1.6,label=(f'{label}: 线性拟合' if label else '线性拟合'))
                    sse=np.sum((yy-(fit.intercept+fit.slope*xx))**2)
                    sigma=np.sqrt(sse/(len(xx)-2))
                    band=stats.t.ppf(.975,len(xx)-2)*sigma*np.sqrt(1/len(xx)+(grid-xx.mean())**2/np.sum((xx-xx.mean())**2))
                    ax.fill_between(grid,pred-band,pred+band,color=color,alpha=.14,lw=0)
                    summary.setdefault('regressions',[]).append({'group':label,'slope':fit.slope,'intercept':fit.intercept,'r2':fit.rvalue**2,'p_slope':fit.pvalue})
                    summary['warnings'].append('阴影为普通最小二乘拟合的均值95%置信带，依赖模型残差假设；非预测区间。')
                else:
                    yy=sub[y].to_numpy(float)
                    if typ=='直方图':ax.hist(yy,bins='auto',density=False,color=color,alpha=.42,edgecolor='white',label=label)
                    if typ=='核密度图':
                        if len(yy)<3 or np.std(yy)==0:raise ValueError('核密度图每组需要3个以上且非恒定的数据。')
                        xx=np.linspace(yy.min()-yy.std(),yy.max()+yy.std(),240)
                        kde=stats.gaussian_kde(yy);ax.plot(xx,kde(xx),color=color,label=label)
                    if typ=='累积分布图':
                        xx=np.sort(yy);ax.step(xx,np.arange(1,len(xx)+1)/len(xx),where='post',color=color,label=label)
        if typ in ('直方图','核密度图','累积分布图'):
            ax.set_xlabel(cfg.get('chart_xlabel') or y)
            ax.set_ylabel(cfg.get('chart_ylabel') or {'直方图':'观测频数','核密度图':'概率密度','累积分布图':'经验累积比例'}[typ])
        else:
            ax.set_xlabel(cfg.get('chart_xlabel') or x);ax.set_ylabel(cfg.get('chart_ylabel') or y)
        if g and typ!='Pareto 散点图':ax.legend(frameon=False,title=g)
        summary['statistical_unit']='输入记录（不推定独立性）'
    if typ not in ('热图',) and opts.show_title and cfg.get('chart_title'):ax.set_title(cfg['chart_title'])
    if typ not in ('热图',):ax.tick_params(axis='x',labelrotation=0)
    refine_figure(fig,opts)
    return fig,summary
