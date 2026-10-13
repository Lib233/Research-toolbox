"""Specimen-aware comparisons and batch-aware mixed models.

This code NEVER treats measurements or frames as separate biological/physical specimens.
Use explicit sample IDs and pairing keys; results carry model assumptions.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats


def prepare_independent(df, group, sample, value, batch=None):
    required=[group,sample,value]+([batch] if batch else [])
    if len(set(required)) != len(required): raise ValueError('组别、试样、数值和批次列必须不同')
    d=df[required].copy()
    if d[required].isna().any().any(): raise ValueError('统计输入不允许缺失组别、试样、数值、批次')
    d[value]=pd.to_numeric(d[value],errors='raise')
    if not np.isfinite(d[value].to_numpy(float)).all():raise ValueError('测量必须是有限值')
                                                                                          
    grouping=[group]+([batch] if batch else [])+[sample]
    return d.groupby(grouping,as_index=False,sort=False)[value].mean()


def paired_comparison(df, condition='condition', sample_id='sample_id', value='value', seed=42, boot=2000):
    """Paired t-test + signed rank (when applicable); pair by physical specimen ID."""
    d=prepare_independent(df,condition,sample_id,value)
    groups=list(d[condition].unique())
    if len(groups)!=2:raise ValueError('配对分析需要恰好两组')
    wide=d.pivot(index=sample_id,columns=condition,values=value)
    missing=int(wide.isna().any(axis=1).sum())
    complete=wide[groups].dropna()
    if len(complete)<3:raise ValueError('至少需要3对完整的独立试样')
    delta=complete[groups[0]].to_numpy(float)-complete[groups[1]].to_numpy(float)
    if np.std(delta,ddof=1)==0:
        raise ValueError('配对差异没有方差，无法执行推断；可报告确定的原始差异')
    t,p=stats.ttest_1samp(delta,0)
    ci=stats.t.interval(.95,df=len(delta)-1,loc=float(np.mean(delta)),scale=float(stats.sem(delta)))
    rng=np.random.default_rng(seed); means=np.mean(rng.choice(delta,(boot,len(delta)),replace=True),axis=1)
    try: wp=float(stats.wilcoxon(delta,zero_method='wilcox').pvalue)
    except ValueError:wp=float('nan')
    return {'group_a':str(groups[0]),'group_b':str(groups[1]),'n_pairs':len(complete),
      'excluded_incomplete_pairs':missing,'mean_paired_difference':float(np.mean(delta)),
      'paired_t_p':float(p),'paired_t':float(t),'paired_t_ci95':[float(ci[0]),float(ci[1])],
      'wilcoxon_p':wp,'cohens_dz':float(np.mean(delta)/np.std(delta,ddof=1)),
      'bootstrap_mean_difference_ci95':np.percentile(means,[2.5,97.5]).tolist(),
      'assumption':'独立成对试样；t检验要求成对差值近似正态；本报告未自动验证研究设计的正确性。'}


def multiple_group_comparison(specimens,condition='condition',value='value'):
    data=[g[value].to_numpy(float) for _,g in specimens.groupby(condition,sort=False)]
    if len(data)<3:raise ValueError('多组检验至少需要3组')
    if min(map(len,data))<2:raise ValueError('每组至少2个独立试样')
    try: F,ap=stats.f_oneway(*data)
    except Exception:F,ap=float('nan'),float('nan')
    H,kp=stats.kruskal(*data)
    lev,lp=stats.levene(*data,center='median')
    return {'groups':len(data),'n_each':[len(x) for x in data],'anova_F':float(F),
       'anova_p':float(ap),'kruskal_H':float(H),'kruskal_p':float(kp),
       'brown_forsythe_stat':float(lev),'brown_forsythe_p':float(lp),
       'note':'ANOVA/Kruskal均需独立样本；选择哪一个必须基于实验设计、分布和事前分析计划。'}


def mixed_effects(df,condition='condition',sample_id='sample_id',value='value',batch='batch'):
    """MixedLM random intercept by specimen, batch as fixed factor. statsmodels optional.

    For repeated measures, specimen is unique within batch; no row-level pseudo-replicate.
    """
    import statsmodels.formula.api as smf
    import statsmodels.api as sm
    required=[condition,sample_id,value,batch]
    if any(x not in df for x in required):raise ValueError('混合效应模型需要 condition、sample_id、value、batch 四类列')
    d=df[required].dropna().copy()
    d[value]=pd.to_numeric(d[value],errors='raise')
    if not np.isfinite(d[value].to_numpy(float)).all():raise ValueError('含非有限数据')
    if len(d)<12 or d[sample_id].nunique()<4 or d[condition].nunique()<2:
        raise ValueError('混合效应模型数据不足（至少12次测量、4个试样、2组）')
    d.columns=['condition','sample_id','value','batch']
    d['physical_id']=d['batch'].astype(str)+'::'+d['sample_id'].astype(str)
                                                                               
    import warnings
    from numpy.linalg import LinAlgError
    model=smf.mixedlm('value ~ C(condition) + C(batch)',d,groups=d['physical_id'])
    fitted=None
    for method in ('lbfgs','powell','nm'):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                fitted=model.fit(reml=True,method=method,maxiter=400,disp=False)
            if fitted.converged:break
        except (LinAlgError,ValueError,ZeroDivisionError):continue
    if fitted is None:raise ValueError('混合效应拟合奇异或未收敛；请先检查组别/批次与随机效应结构')
    if not fitted.converged:raise ValueError('混合效应模型未收敛；请检查试样/批次与随机效应方差')
    ci=fitted.conf_int(); terms=[]
    for name,val in fitted.params.items():
        terms.append({'term':str(name),'estimate':float(val), 'ci95_low':float(ci.loc[name,0]),
                      'ci95_high':float(ci.loc[name,1]), 'p_value':float(fitted.pvalues.get(name,float('nan')))})
    return {'model':'random specimen intercept + fixed batch + condition',
            'rows':len(d),'specimens':d.physical_id.nunique(),'batches':d.batch.nunique(),
            'converged':bool(fitted.converged),'terms':terms,
            'warning':'批次作为固定效应；复杂多层、交叉效应及小样本自由度校正需由统计人员确认。'}


def measurement_uncertainty(value,components,distribution='normal',confidence=.95):
    """Root-sum-square of independent standard uncertainties. No automatic covariance assumption."""
    try:
        measured=float(value)
        level=float(confidence)
        u=np.asarray(components,dtype=float)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError('测量值、置信水平和不确定度分量必须是有效数字') from exc
    if not np.isfinite(measured):raise ValueError('测量值必须是有限数字')
    if not np.isfinite(level) or not 0<level<1:
        raise ValueError('置信水平必须严格介于 0 与 1 之间（例如 0.95）')
    if u.ndim!=1 or u.size==0 or not np.isfinite(u).all() or np.any(u<0):
        raise ValueError('不确定度分量需为至少一项非负有限数值')
    if distribution!='normal':raise ValueError('本模块仅采用独立正态标准不确定度的合成规则')
    combined=float(np.sqrt(np.sum(u*u)));k=float(stats.norm.ppf((1+level)/2))
    return {'value':measured,'standard_uncertainty':combined,'coverage_factor':k,
           'expanded_uncertainty':float(k*combined),'interval':[float(value-k*combined),float(value+k*combined)],
           'assumption':'分量为互不相关的标准不确定度；存在相关性时不能直接使用此公式。'}
