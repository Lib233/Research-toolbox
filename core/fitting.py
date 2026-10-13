"""Curve fitting with bounds, residuals and numerical identifiability warnings."""
import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from .common import safe_numeric

MODELS={
 'linear': (['a','b'],lambda x,p:p[0]*x+p[1]),
 'quadratic': (['a','b','c'],lambda x,p:p[0]*x*x+p[1]*x+p[2]),
 'exponential': (['a','b','c'],lambda x,p:p[0]*np.exp(np.clip(p[1]*x,-80,80))+p[2]),
 'saturation': (['a','b','c'],lambda x,p:p[0]*(1-np.exp(np.clip(-np.abs(p[1])*x,-80,80)))+p[2]),
}

def fit_curve(df,x_col='x',y_col='y',model='linear',robust=True):
    if model not in MODELS:raise ValueError('未知模型')
    x=safe_numeric(df[x_col],x_col).to_numpy();y=safe_numeric(df[y_col],y_col).to_numpy()
    names,fn=MODELS[model]; p=len(names)
    if len(x)<max(p+2,6):raise ValueError('数据点数不足，至少需要 max(参数数+2,6) 个。')
    if len(np.unique(x))<p:raise ValueError('自变量不同取值不足以拟合此模型。')
    if model=='linear': guess=[0,float(y.mean())]
    elif model=='quadratic':guess=[0,0,float(y.mean())]
    elif model=='exponential':guess=[float(y.max()-y.min()),0.01,float(y.min())]
    else: guess=[float(y.max()-y.min()),.5,float(y.min())]
    scale=np.maximum(np.abs(guess),1)
    result=least_squares(lambda z:(fn(x,z)-y)/max(np.std(y),1e-8),guess,
              x_scale=scale, loss='soft_l1' if robust else 'linear',max_nfev=10000)
    pred=fn(x,result.x)
    if not result.success or not np.isfinite(pred).all():raise ValueError('拟合未正常收敛，请改用更简单的模型或核对数值范围。')
    residual=y-pred;sse=float(np.sum(residual**2));sst=float(np.sum((y-y.mean())**2))
    r2=1-sse/sst if sst>0 else float('nan')
    rank=int(np.linalg.matrix_rank(result.jac));warning=[]
    if rank<p:warning.append('模型雅可比矩阵秩不足，部分参数可能无法唯一辨识。')
    if model in ('exponential','saturation'):warning.append('非线性模型对初值与取值范围敏感；检查残差与外推风险。')
    params={name:float(v) for name,v in zip(names,result.x)}
    summary={'model':model,'parameters':params,'n_points':len(x),'RMSE':float(np.sqrt(np.mean(residual**2))),
             'R2':float(r2),'robust_loss':bool(robust),'jacobian_rank':rank,'warnings':warning,
             'disclaimer':'拟合参数置信区间未自动提供；相关残差/独立性问题需单独检查。'}
    return summary,pd.DataFrame({'x':x,'measured':y,'predicted':pred,'residual':residual})
