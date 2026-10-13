"""Two optimization routes: safe-typed equation, and experimental surrogate with cross validation."""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution, minimize, dual_annealing, NonlinearConstraint
from scipy.spatial.distance import cdist
from scipy.stats import qmc
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold,GroupKFold,cross_val_predict
from sklearn.metrics import r2_score, mean_absolute_error
from .safeexpr import calculate
from .common import safe_numeric
from .design_validation import design_groups, compare_fold_predictions, restrict_design_bounds

IDENT=r'^[a-zA-Z_][a-zA-Z_0-9]*$'
def parse_bounds(text):
    """One row per param; name,min,max. Semicolon-separated also accepted."""
    rows=[r.strip() for r in text.replace(';','\n').splitlines() if r.strip()]
    params=[]
    for row in rows:
        item=[x.strip() for x in row.split(',')]
        if len(item)!=3 or not re.fullmatch(IDENT,item[0]):
            raise ValueError(f'参数边界写法：name,min,max；错误行：{row}')
        lo,hi=float(item[1]),float(item[2])
        if not np.isfinite([lo,hi]).all() or not lo<hi: raise ValueError(f'{row} 的下界必须小于上界')
        params.append((item[0],lo,hi))
    if not 1<=len(params)<=5 or len(set(r[0] for r in params))!=len(params):
        raise ValueError('支持1到5个参数；名称不能重复。')
    return params

def _constraints(text):return [x.strip() for x in text.replace(';','\n').splitlines() if x.strip()]

def _constraint_margin(e,vars):
    match=re.fullmatch(r'(.+?)\s*(>=|<=|>|<)\s*(.+)',e)
    if not match:raise ValueError('约束用 a <= 2 或 b >= 1 的形式，每行一条。')
    a=calculate(match[1],vars);b=calculate(match[3],vars)
    return (a-b) if match[2] in ('>=','>') else (b-a)

def _violation(exps,vars):
    """Expressions are relational e.g. force >= 0.2; penalty scales to literal threshold."""
    viol=0.0
    for e in exps:
        match=re.fullmatch(r'(.+?)\s*(>=|<=|>|<)\s*(.+)',e)
        if not match:raise ValueError('约束用 a <= 2 或 b >= 1 的形式，每行一条。')
        a=calculate(match[1],vars);b=calculate(match[3],vars)
        denom=max(1.,abs(b))
        if match[2] in ('>=','>'):viol+=max(0,b-a)**2/denom**2
        else:viol+=max(0,a-b)**2/denom**2
    return viol

def _finite_formula(expression,variables):
    try:return np.isfinite(calculate(expression,variables))
    except (ValueError,ZeroDivisionError,OverflowError):return False

def optimize_equation(bounds_text,expression,goal='min',algorithm='DE',constraints='',seed=42,maxiter=200):
    params=parse_bounds(bounds_text)
    if goal not in ('min','max'):raise ValueError('目标请选择min或max。')
    if algorithm not in ('DE','SLSQP','DualAnnealing'):raise ValueError('算法不支持。')
    if not expression.strip():raise ValueError('请输入目标函数表达式。')
    exps=_constraints(constraints)
    names=[r[0] for r in params];bounds=[(lo,hi) for _,lo,hi in params]
    sign=1 if goal=='min' else -1
    mid={name:(lo+hi)/2 for name,lo,hi in params}
                                                                                                      
    _violation(exps,mid)
    sample_points=[mid]+[{k:float(v) for k,v in zip(names,row)} for row in np.random.default_rng(seed).uniform(
        [a for a,b in bounds],[b for a,b in bounds],size=(64,len(bounds)))]
    if not any(_finite_formula(expression,p) for p in sample_points):
        raise ValueError('公式在测试的参数范围内无法算出有效数值。请检查根号、对数或分段区间。')
    iteration_history=[];n_eval=0;best_eval=np.inf
    def record_iter(z):
        variable=dict(zip(names,map(float,z)))
        try: val=float(calculate(expression,variable));feasible=_violation(exps,variable)<=1e-10
        except ValueError:val=float('nan');feasible=False
        iteration_history.append({'iteration':len(iteration_history)+1,'objective_value':val,
            'best_feasible_objective':(-best_eval if goal=='max' else best_eval) if np.isfinite(best_eval) else None,
            'feasible':bool(feasible),'evaluations_so_far':n_eval})
    def callback_de(xk,convergence=0):record_iter(xk);return False
    def callback_slsqp(xk):record_iter(xk)
    def callback_anneal(x,f,context):record_iter(x);return False
    def objective(z):
        nonlocal n_eval,best_eval
        n_eval+=1
        v=dict(zip(names,map(float,z)))
        try:
            raw=float(calculate(expression,v));penalty=_violation(exps,v)
            if penalty<=1e-10:best_eval=min(best_eval,sign*raw)
            return sign*raw+1e6*penalty
        except ValueError:return 1e18
    true_constraints=[]
    for exp in exps:
        def margin(z, ex=exp): return _constraint_margin(ex,dict(zip(names,map(float,z))))
        true_constraints.append(margin)
    if algorithm=='DE':
        kwargs={'constraints':[NonlinearConstraint(fun,0,np.inf) for fun in true_constraints]} if true_constraints else {}
        res=differential_evolution(objective,bounds,seed=seed,maxiter=int(maxiter),tol=1e-7,polish=True,popsize=12,callback=callback_de,**kwargs)
    elif algorithm=='DualAnnealing':
        res=dual_annealing(objective,bounds,seed=seed,maxiter=int(maxiter),no_local_search=False,callback=callback_anneal)
    else:
        cons=[{'type':'ineq','fun':fn} for fn in true_constraints]
        res=minimize(objective,np.array([(a+b)/2 for a,b in bounds]),method='SLSQP',bounds=bounds,
               constraints=cons,callback=callback_slsqp,options={'maxiter':int(maxiter),'ftol':1e-12})
    variables=dict(zip(names,[float(x) for x in res.x]))
    if not iteration_history:record_iter(res.x)
    violation=_violation(exps,variables)
    final=calculate(expression,variables)
    if violation>1e-8:status='NO_FEASIBLE_SOLUTION'
    elif res.success:status='CANDIDATE_CONVERGED'
    else:status='CANDIDATE_NOT_CONVERGED'
    return {'status':status,'algorithm':algorithm,'goal':goal,'objective_value':float(final),
            'parameters':variables,'constraint_violation':float(violation),'evaluations':int(res.nfev),
            'converged':bool(res.success),'message':str(res.message), 'random_seed':seed,
            'iteration_history':iteration_history,
            'warning':'数值候选不等于实验可行。DE/SLSQP使用显式约束（仍需查constraint_violation）；DualAnnealing使用惩罚约束，非凸问题不保证全局最优。'}

def _pareto(values,goals):
    """Filter nondominated candidates; values rows, columns; higher better normalization."""
    v=np.asarray(values,float)*np.array([1 if g=='max' else -1 for g in goals])
    keep=np.ones(len(v),dtype=bool)
    for i in range(len(v)):
        if not keep[i]: continue
        dom=np.all(v>=v[i],axis=1)&np.any(v>v[i],axis=1)
        if np.any(dom):keep[i]=False
    return keep

def optimize_experiments(df,parameter_cols,response_cols,goals,weights,group_col=None,seed=42,
                         response_constraint='',parameter_bounds=''):
    """Quadratic ridge regression surrogate with grouped out-of-fold validation.

    This yields a *suggested* candidate, not a proven physical optimum.
    Max 3 design variables, 2 response variables; bounded by observed parameter ranges.
    """
    if not (1<=len(parameter_cols)<=3) or not (1<=len(response_cols)<=2):
        raise ValueError('实验代理优化支持1-3个参数和1-2个输出指标。')
    if not len(set(parameter_cols+response_cols))==len(parameter_cols+response_cols):
        raise ValueError('输入参数与输出指标列不能重复。')
    if len(response_cols)!=len(goals) or len(goals)!=len(weights):raise ValueError('目标方向、权重的数量须与输出指标一致。')
    if any(g not in ('max','min') for g in goals):raise ValueError('优化方向使用 max 或 min。')
    w=np.asarray(weights,float)
    if not np.isfinite(w).all() or np.any(w<0) or w.sum()<=0:raise ValueError('目标权重必须非负且至少一个为正。')
    w=w/w.sum();n=len(df)
    if n<12:raise ValueError('代理优化至少需要12行独立实验数据；样本过少时不要让程序生成不可靠的最优参数。')
    X=np.column_stack([safe_numeric(df[c],c).to_numpy() for c in parameter_cols]);
    Y=np.column_stack([safe_numeric(df[c],c).to_numpy() for c in response_cols]);
    if any(np.unique(X[:,j]).size<3 for j in range(X.shape[1])):
        raise ValueError('每个参数至少要有3个不同的实验水平。')
    if len(np.unique(X,axis=0))<10:raise ValueError('至少需要10组不同的参数设计，避免把技术重复当作参数空间覆盖。')
    warning=[]
    if group_col and group_col.strip():
        if group_col not in df:raise ValueError(f'找不到独立实验ID列{group_col}')
        explicit=df[group_col].to_numpy()
    else:
        explicit=None
        warning.append('未提供独立实验ID：自动将相同参数组合放进同一个验证折；同批次、同试样的其他相关性仍需人工核实。')
    validation_groups,splits=design_groups(X,explicit)
    if len(np.unique(validation_groups))<8:
        warning.append('不同验证组数较少，交叉验证结果可能不稳定。')
    low=X.min(axis=0); high=X.max(axis=0);span=high-low
    original_low=low.copy();original_high=high.copy()
    low,high=restrict_design_bounds(parameter_bounds,list(parameter_cols),low,high)
    for j in range(X.shape[1]):
        if span[j]==0:raise ValueError('参数列不能固定为一个值')
    models=[];metrics=[]
    for col in range(Y.shape[1]):
        model=make_pipeline(StandardScaler(),PolynomialFeatures(degree=2,include_bias=False),Ridge(alpha=1.0))
        ycv=np.full(n,np.nan)
        naive=np.full(n,np.nan)
        for train,test in splits:
            fold=make_pipeline(StandardScaler(),PolynomialFeatures(degree=2,include_bias=False),Ridge(alpha=1.0))
            fold.fit(X[train],Y[train,col])
            ycv[test]=fold.predict(X[test])
            naive[test]=Y[train,col].mean()
        metric=compare_fold_predictions(Y[:,col],ycv,naive)
        metric.update({'response':response_cols[col],'unit':'same as response source column',
                       'validation':'grouped_by_design_and_id' if explicit is not None else 'grouped_by_same_design',
                       'independent_validation_groups':len(np.unique(validation_groups))})
        metrics.append(metric)
        if metric['cv_R2']<.3 or metric['cv_MAE']>=.98*metric['baseline_MAE']:
            warning.append(f'输出“{response_cols[col]}”留组预测表现不足（R²={metric["cv_R2"]:.2f}，MAE={metric["cv_MAE"]:.3g}，均值基线MAE={metric["baseline_MAE"]:.3g}）。不得将候选视为可靠的参数推荐。')
        model.fit(X,Y[:,col]); models.append(model)
    ymin=Y.min(axis=0);ymax=Y.max(axis=0);yrange=np.where(ymax>ymin,ymax-ymin,1.)
    def predict(x):return np.array([m.predict(np.asarray(x,float).reshape(1,-1))[0] for m in models])
    def getvars(z):return dict(zip(response_cols,predict(z)))
    if response_constraint.strip():
        if len(response_cols)!=1 and response_constraint.count('>=')+response_constraint.count('<=')+response_constraint.count('<')+response_constraint.count('>')==0:
            raise ValueError('约束格式为 output_name >= 0.2')
        _violation(_constraints(response_constraint),getvars((low+high)/2))
    def score(z):
        v=predict(z)
        desirability=np.array([(v[i]-ymin[i])/yrange[i] if goals[i]=='max' else (ymax[i]-v[i])/yrange[i]
                               for i in range(len(goals))])
        cost=-float(np.dot(w,desirability))
        if response_constraint.strip(): cost+=1e5*_violation(_constraints(response_constraint),getvars(z))
        return cost
    res=differential_evolution(score,list(zip(low,high)),seed=seed,maxiter=120,popsize=12,polish=True)
    optimum=np.asarray(res.x,float); response=predict(optimum)
    distances=cdist(((X-low)/span),((optimum-low)/span).reshape(1,-1)).ravel()
    near=int(np.argmin(distances)); nearest=float(distances[near])
    if nearest>0.35: warning.append('建议点离最近实验设计点较远（归一化距离>0.35），属于弱数据支撑区域。')
    if response_constraint.strip() and _violation(_constraints(response_constraint),dict(zip(response_cols,response)))>1e-8:
        status='PREDICTED_CONSTRAINT_NOT_MET'
    elif any(d['cv_R2']<.3 or d['cv_MAE']>=.98*d['baseline_MAE'] for d in metrics):status='LOW_MODEL_RELIABILITY'
    else:status='CANDIDATE_NEEDS_EXPERIMENTAL_VALIDATION'
                                                                                                      
    sampler=qmc.LatinHypercube(d=len(parameter_cols),seed=seed)
    trials=qmc.scale(sampler.random(n=400),low,high)
    trial_preds=np.stack([m.predict(trials) for m in models],axis=1)
    feasible=np.array([_violation(_constraints(response_constraint),dict(zip(response_cols,row)))<=1e-8
         for row in trial_preds]) if response_constraint.strip() else np.ones(len(trials),bool)
    keep=np.zeros(len(trials),bool)
    if len(response_cols)>1 and np.any(feasible):
        keep[np.where(feasible)[0]]=_pareto(trial_preds[feasible],goals)
    candidates=pd.DataFrame(trials,columns=parameter_cols)
    for i,c in enumerate(response_cols):
        candidates['predicted_'+c]=trial_preds[:,i]
        candidates['cv_abs_error_q90_'+c]=metrics[i]['cv_abs_error_q90']
        candidates['uncertainty_sd_'+c]=metrics[i]['cv_abs_error_q90']/1.645
        candidates['heuristic_low_'+c]=trial_preds[:,i]-1.96*metrics[i]['cv_abs_error_q90']/1.645
        candidates['heuristic_high_'+c]=trial_preds[:,i]+1.96*metrics[i]['cv_abs_error_q90']/1.645
    candidates['predicted_constraints_met']=feasible
    candidates['estimated_pareto']=keep
    candidates['is_optimum']=False
    best={c:float(z) for c,z in zip(parameter_cols,optimum)}
    best.update({'predicted_'+c:float(z) for c,z in zip(response_cols,response)})
    optimum_dominated=bool(np.any(np.all((trial_preds*np.array([1 if g=='max' else -1 for g in goals])) >= (response*np.array([1 if g=='max' else -1 for g in goals])),axis=1) & np.any((trial_preds*np.array([1 if g=='max' else -1 for g in goals])) > (response*np.array([1 if g=='max' else -1 for g in goals])),axis=1)))
    best_feasible=_violation(_constraints(response_constraint),dict(zip(response_cols,response)))<=1e-8 if response_constraint.strip() else True
    best.update({'estimated_pareto':bool(best_feasible and not optimum_dominated),'predicted_constraints_met':bool(best_feasible),'is_optimum':True})
    for i,c in enumerate(response_cols):
        best['cv_abs_error_q90_'+c]=metrics[i]['cv_abs_error_q90']
        best['uncertainty_sd_'+c]=metrics[i]['cv_abs_error_q90']/1.645
        best['heuristic_low_'+c]=response[i]-1.96*metrics[i]['cv_abs_error_q90']/1.645
        best['heuristic_high_'+c]=response[i]+1.96*metrics[i]['cv_abs_error_q90']/1.645
    candidates=pd.concat([pd.DataFrame([best]),candidates],ignore_index=True)
    result={'status':status,'data_rows':n,'unique_designs':len(np.unique(X,axis=0)),
            'independent_grouping':group_col if group_col else 'ONLY SAME DESIGN GROUPED - other correlation unknown',
            'independent_validation_groups':len(np.unique(validation_groups)),
            'surrogate':'standardized quadratic polynomial + Ridge(alpha=1)',
            'parameter_columns':parameter_cols,'response_columns':response_cols,'directions':goals,'weights':w.tolist(),
            'parameter_bounds_observed':{c:[float(a),float(b)] for c,a,b in zip(parameter_cols,original_low,original_high)},
            'parameter_bounds_user_allowed':{c:[float(a),float(b)] for c,a,b in zip(parameter_cols,low,high)},
            'recommended_parameters':dict(zip(parameter_cols,map(float,optimum))) if status=='CANDIDATE_NEEDS_EXPERIMENTAL_VALIDATION' else None,
            'predicted_responses':dict(zip(response_cols,map(float,response))) if status=='CANDIDATE_NEEDS_EXPERIMENTAL_VALIDATION' else None,
            'validation_metrics':metrics,'nearest_experiment_normalized_distance':nearest,
            'nearest_experiment_row_1based':near+2,'warnings':warning,
            'note':'这是基于拟合模型的建议实验点。CV分数、测量误差、物理限制和边界外风险必须人工检查；Pareto为近似候选集，非真实物理Pareto前沿。',
            'seed':seed,
            'note_v7':'二次模型给出的区间由留组误差粗略推算，属于经验参考值、不是具有保障的预测区间。验证不通过时不发布正式推荐。'}
    if status!='CANDIDATE_NEEDS_EXPERIMENTAL_VALIDATION':
        candidates['is_optimum']=False
    return result,candidates


def quadratic_out_of_fold_table(df, parameter_cols, response_cols, group_col=None):
    """Reproduce fold-local quadratic holdout predictions for independent auditing."""
    par=list(parameter_cols);resp=list(response_cols)
    X=df[par].to_numpy(float);Y=df[resp].to_numpy(float)
    groups,splits=design_groups(X,df[group_col].to_numpy() if group_col else None)
    out=df[par+resp].copy().reset_index(drop=True);out['validation_group']=groups
    for i,name in enumerate(resp):
        pred=np.full(len(X),np.nan)
        for a,b in splits:
            m=make_pipeline(StandardScaler(),PolynomialFeatures(degree=2,include_bias=False),Ridge(alpha=1.0))
            m.fit(X[a],Y[a,i]);pred[b]=m.predict(X[b])
        out['cv_predicted_'+name]=pred
        out['cv_residual_'+name]=Y[:,i]-pred
    return out
