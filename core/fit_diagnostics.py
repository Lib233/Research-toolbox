"""Model comparison and approximate uncertainty from Jacobian.
For robust regressions covariance of ordinary residuals is NOT a formal robust SE;
report it as exploratory only and never a coverage guarantee.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import t
from scipy.optimize import least_squares
from .fitting import MODELS,fit_curve

def compare_models(data,x_col,y_col,models=None,robust=False):
    from scipy.stats import pearsonr
    used=models or list(MODELS)
    table=[];predictions={}
    for name in used:
        try:
            summ,pred=fit_curve(data,x_col,y_col,name,robust)
            n=len(pred);k=len(summ['parameters']);sse=float(np.sum(pred.residual**2))
            if sse<=0:sse=1e-30
                                                                              
            aic=n*np.log(sse/n)+2*k
            aicc=aic+2*k*(k+1)/(n-k-1) if n>k+1 else float('nan')
            bic=n*np.log(sse/n)+np.log(n)*k
            table.append({'model':name,'AIC':aic,'AICc':aicc,'BIC':bic,'R2':summ['R2'],
                          'RMSE':summ['RMSE'],'parameter_count':k,'notes':'同一数据与iid残差假定；低AICc不保证物理正确'})
            predictions[name]=pred
        except (ValueError,FloatingPointError):continue
    if not table:raise ValueError('没有任何模型成功拟合')
    return pd.DataFrame(table).sort_values('AICc',na_position='last'),predictions

def parameter_ci(data,x_col,y_col,model='linear',robust=False):
    if model not in MODELS:raise ValueError('未知模型')
    summary,pred=fit_curve(data,x_col,y_col,model,robust)
    x=pred.x.to_numpy(float);y=pred.measured.to_numpy(float); names,fn=MODELS[model]
    p=np.array([summary['parameters'][name] for name in names]);n=len(x);k=len(p)
    if n<=k:raise ValueError('自由度不足，无法估计参数区间')
    from scipy.optimize._numdiff import approx_derivative
    J=approx_derivative(lambda params:fn(x,params),p)
    cov_rank=int(np.linalg.matrix_rank(J));dof=n-k
    if cov_rank<k:raise ValueError('雅可比奇异，无法可靠计算参数置信区间')
    sse=np.sum((y-fn(x,p))**2)
    covariance=np.linalg.pinv(J.T@J)*sse/dof
    se=np.sqrt(np.maximum(np.diag(covariance),0));factor=t.ppf(.975,dof)
    result=[{'parameter':name,'estimate':float(val),'approx_se':float(err),
             'approx_ci95_low':float(val-factor*err),'approx_ci95_high':float(val+factor*err)}
            for name,val,err in zip(names,p,se)]
    return pd.DataFrame(result),{'degrees_freedom':dof,'jacobian_rank':cov_rank,
     'warning':'雅可比线性近似区间；仅在独立、同方差、模型正确与普通最小二乘近似下有效。稳健拟合时仅供探索参考。'}
