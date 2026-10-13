"""Reusable validation safeguards for surrogate-based design.

Equal design rows must never appear in both training and validation; when an
experiment/batch grouping is supplied, all rows sharing that ID stay together.
Neither a unique row nor a unique numeric design automatically proves an
independent biological specimen.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold


def design_groups(X, explicit=None):
    x=np.asarray(X, dtype=float)
    n=len(x)
    if n==0:raise ValueError('没有实验记录')
    owner=list(range(n))
    def root(i):
        while owner[i]!=i:
            owner[i]=owner[owner[i]];i=owner[i]
        return i
    def union(i,j):owner[root(j)]=root(i)
    first={}
    for i,row in enumerate(x):
        key=tuple(row.tolist())
        if key in first:union(i,first[key])
        else:first[key]=i
    if explicit is not None:
        first={}
        for i,group in enumerate(explicit):
            if pd.isna(group) or not str(group).strip():
                raise ValueError('独立实验 ID 不能为空；如未知，请留空该参数并核实试验独立性')
            key=str(group)
            if key in first:union(i,first[key])
            else:first[key]=i
    ids=np.array([root(i) for i in range(n)])
    unique=np.unique(ids)
    if len(unique)<5:raise ValueError('防止重复设计泄漏后的独立验证组不足5组；请补充不同参数组合/独立实验')
    return ids,list(GroupKFold(n_splits=min(5,len(unique))).split(x,groups=ids))


def compare_fold_predictions(y,pred,naive):
    from sklearn.metrics import mean_absolute_error,r2_score
    y=np.asarray(y,float);pred=np.asarray(pred,float);naive=np.asarray(naive,float)
    mae=float(mean_absolute_error(y,pred));ref=float(mean_absolute_error(y,naive))
    r2=float(r2_score(y,pred))
                                                                                     
                                                                                  
    residual=np.sort(np.abs(y-pred));index=min(len(y)-1,int(np.ceil((len(y)+1)*.90))-1)
    q90=float(residual[max(0,index)])
    return {'cv_R2':r2,'cv_MAE':mae,'baseline_MAE':ref,
            'mae_improvement_over_baseline_pct':float(100*(ref-mae)/max(ref,1e-12)),
            'cv_abs_error_q90':q90,
            'cv_fraction_within_q90':float(np.mean(np.abs(y-pred)<=q90))}


def restrict_design_bounds(spec, names, observed_lo, observed_hi):
    """Optional user-specified *experimental control limits* INSIDE measured ranges.

    Rows `parameter_name,min,max`; not a symbolic expression evaluator. Missing
    parameters retain the observed range. The output is an explicit audit record.
    """
    lo=np.asarray(observed_lo,dtype=float).copy()
    hi=np.asarray(observed_hi,dtype=float).copy()
    observed_low=lo.copy(); observed_high=hi.copy()
    seen=set()
    for line in str(spec or '').replace(';','\n').splitlines():
        if not line.strip():continue
        pieces=[x.strip() for x in line.split(',')]
        if len(pieces)!=3 or pieces[0] not in names:
            raise ValueError('实验参数范围每行应为：参数列名,允许最小值,允许最大值；名称需与输入参数列一致')
        name=pieces[0]
        if name in seen:raise ValueError('实验参数范围中的参数名重复：'+name)
        seen.add(name)
        try:a,b=float(pieces[1]),float(pieces[2])
        except ValueError as exc:raise ValueError('实验参数范围必须填写数字：'+line) from exc
        if not np.isfinite(a) or not np.isfinite(b) or a>=b:
            raise ValueError('实验参数的允许最小值必须小于最大值：'+line)
        i=names.index(name)
        tolerance=1e-9*max(1.,abs(observed_low[i]),abs(observed_high[i]))
        if a<observed_low[i]-tolerance or b>observed_high[i]+tolerance:
            raise ValueError(f'{name} 的允许范围必须位于历史实测范围内 [{observed_low[i]:.7g}, {observed_high[i]:.7g}]，不能借缩放范围作外推')
        lo[i]=max(a,observed_low[i]);hi[i]=min(b,observed_high[i])
    return lo,hi
