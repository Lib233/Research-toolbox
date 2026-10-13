"""Research Toolbox : conservative GP-driven next-experiment planning.

Critical policy: cross-validation prevents identical parameter rows and declared
experimental groups crossing folds; folds fit their OWN preprocessors. A model
that cannot beat a naive predictor does NOT issue an actionable recommendation.
Intervals/constraint probabilities are model-dependent diagnostics, NOT calibrated
physical or biological guarantees. A suggested experiment is NOT an optimum.
"""
from __future__ import annotations
import re
import warnings as pywarnings
import numpy as np
import pandas as pd
from scipy.stats import norm,qmc
from scipy.spatial.distance import cdist
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel,Matern,WhiteKernel
from .design_validation import design_groups,compare_fold_predictions,restrict_design_bounds

_CONSTRAINT=re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|>|<)\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*$')

def _constraints(spec,resp):
    out=[]
    for line in str(spec or '').replace(';','\n').splitlines():
        if not line.strip():continue
        m=_CONSTRAINT.fullmatch(line)
        if not m or m[1] not in resp:raise ValueError('约束应写为“响应列名 >= 数值”或“响应列名 <= 数值”（支持多行）')
        val=float(m[3]);
        if not np.isfinite(val):raise ValueError('约束必须为有限数值')
        out.append((resp.index(m[1]),m[2],val))
    return out

def _pareto(vals,goals):
    v=np.asarray(vals,float)*np.array([1 if x=='max' else -1 for x in goals])
    keep=np.ones(len(v),bool)
    for j in range(len(v)):
        if np.any(np.all(v>=v[j],axis=1)&np.any(v>v[j],axis=1)):keep[j]=False
    return keep

def _model(dim,seed):
    kernel=ConstantKernel(1.,(.03,30.))*Matern(length_scale=np.ones(dim),length_scale_bounds=(.08,10.),nu=2.5)+WhiteKernel(noise_level=.025,noise_level_bounds=(1e-5,1.))
    return GaussianProcessRegressor(kernel=kernel,normalize_y=True,alpha=1e-7,n_restarts_optimizer=0,random_state=seed)

def _fit(X,Y,seed):
    """Preprocessing is entirely train-fold-local."""
    lo=np.min(X,axis=0);span=np.maximum(np.ptp(X,axis=0),1e-12)
    centre=float(np.mean(Y));scale=max(float(np.std(Y)),1e-9)
    with pywarnings.catch_warnings(record=True) as caught:
        pywarnings.simplefilter('always',ConvergenceWarning)
        model=_model(X.shape[1],seed)
        model.fit((X-lo)/span,(Y-centre)/scale)
    return (model,lo,span,centre,scale),[str(w.message) for w in caught if issubclass(w.category,ConvergenceWarning)]

def _predict(bundle,X):
    model,lo,span,centre,scale=bundle
    mu,sd=model.predict((X-lo)/span,return_std=True)
    return mu*scale+centre,np.maximum(sd*scale,1e-10)

def optimize_bayesian(df,parameter_cols,response_cols,goals,weights,group_col=None,seed=42,
                      response_constraint='',n_candidates=384,parameter_bounds=''):
    par=list(parameter_cols);resp=list(response_cols)
    if not 1<=len(par)<=5 or not 1<=len(resp)<=3:raise ValueError('高斯过程支持1～5个实验参数及1～3个测量指标')
    if len(par)!=len(set(par)) or len(resp)!=len(set(resp)) or set(par)&set(resp):raise ValueError('参数列/响应列名称必须不同')
    if len(goals)!=len(resp) or any(g not in ('min','max') for g in goals):raise ValueError('优化方向必须逐项填写max/min')
    weight=np.asarray(weights,float)
    if len(weight)!=len(resp) or not np.isfinite(weight).all() or np.any(weight<0) or weight.sum()<=0:raise ValueError('权重个数不匹配或含负数/无效值')
    weight=weight/weight.sum()
    if not 32<=int(n_candidates)<=3000:raise ValueError('候选数应在32～3000之间')
    if len(df)<15 or len(df)>350:raise ValueError('当前高斯过程需要15～350条已完成实验记录')
    if not set(par+resp).issubset(df.columns):raise ValueError('找不到输入参数或测量指标对应的表头')
    X=df[par].apply(pd.to_numeric,errors='raise').to_numpy(float)
    Y=df[resp].apply(pd.to_numeric,errors='raise').to_numpy(float)
    if not np.isfinite(X).all() or not np.isfinite(Y).all():raise ValueError('实验参数与测量结果不能有空值或无穷值')
    n_designs=len(np.unique(X,axis=0))
    if n_designs<max(10,4*len(par)):raise ValueError('不同参数组合太少；同一参数组合重复测量不能代替新设计')
    lo=X.min(axis=0);hi=X.max(axis=0);span=hi-lo
    search_lo,search_hi=restrict_design_bounds(parameter_bounds,par,lo,hi)
    if np.any(span<1e-12):raise ValueError('有输入参数始终不变；请移除或补充实验')
    if np.any(Y.std(axis=0)<1e-10):raise ValueError('测量指标几乎恒定，无法学习变化规律')
    constraints=_constraints(response_constraint,resp)
    explicit=None
    if group_col:
        if group_col not in df:raise ValueError('独立实验 ID 列不存在')
        explicit=df[group_col].to_numpy()
    groups,splits=design_groups(X,explicit)
    group_count=len(np.unique(groups))
    warning=[]
    if not group_col:warning.append('未提供真实独立实验ID；已自动将相同参数组合放在同一验证折，但不能识别同批次/同试样相关性。')
    elif group_count<8:warning.append('可独立验证的实验组偏少；请重点查看交叉验证误差。')
    bundles=[];validation=[];oof_table=df[par+resp].copy().reset_index(drop=True)
    score_ok=True
    for i,name in enumerate(resp):
        pred=np.full(len(X),np.nan);sd_cv=np.full(len(X),np.nan);naive=np.full(len(X),np.nan)
        for a,b in splits:
            fit,_=_fit(X[a],Y[a,i],seed)
            pred[b],sd_cv[b]=_predict(fit,X[b]);naive[b]=np.mean(Y[a,i])
        metric=compare_fold_predictions(Y[:,i],pred,naive)
        metric.update({'response':name,'validation':'grouped_by_design_and_id' if group_col else 'grouped_by_same_design',
                       'folds':len(splits),'independent_validation_groups':group_count,
                       'nominal_95_interval_coverage_cv':float(np.mean(np.abs(Y[:,i]-pred)<=1.96*sd_cv))})
                                                                            
                                                                           
                                        
        per_group=[]
        for g in np.unique(groups):
            ix=groups==g
            per_group.append((float(np.mean(np.abs(Y[ix,i]-pred[ix]))),float(np.mean(np.abs(Y[ix,i]-naive[ix])))))
        metric['group_equal_MAE']=float(np.mean([a for a,b in per_group]))
        metric['group_equal_baseline_MAE']=float(np.mean([b for a,b in per_group]))
                                                                                 
                                                                           
        ratio=metric['cv_abs_error_q90']/max(1.645*np.median(sd_cv),1e-10)
        metric['suggested_uncertainty_inflation']=float(np.clip(ratio,1,10))
        bad=(metric['cv_R2']<.3 or metric['cv_MAE']>=metric['baseline_MAE']*.98 or
             metric['group_equal_MAE']>=metric['group_equal_baseline_MAE']*.98)
        metric['passes_basic_validation']=not bad
        if bad:
            score_ok=False
            warning.append(f'{name} 在留组验证中不可靠（R²={metric["cv_R2"]:.2f}，MAE={metric["cv_MAE"]:.3g}，简单均值基线MAE={metric["baseline_MAE"]:.3g}）；暂不发布正式推荐。')
        bundle,fitwarn=_fit(X,Y[:,i],seed)
        if fitwarn:warning.append(name+' 的核函数超参数可能处在边界；建议更多设计或人工复核拟合。')
        bundles.append(bundle);validation.append(metric)
        oof_table['measured_'+name]=Y[:,i]
        oof_table['cv_predicted_'+name]=pred
        oof_table['cv_residual_'+name]=Y[:,i]-pred
        oof_table['cv_nominal_sd_'+name]=sd_cv
        oof_table['cv_group']=groups
                                                                            
                                                                             
    Xn=(X-lo)/span
    grid=qmc.LatinHypercube(d=len(par),seed=seed).random(int(n_candidates))
    grid=(grid*(search_hi-search_lo)+search_lo-lo)/span
    samples=np.concatenate([grid,Xn])
    candidate_x=samples*span+lo
    means=[];nominal_sd=[];effective_sd=[]
    for i,bundle in enumerate(bundles):
        m,s=_predict(bundle,candidate_x)
        means.append(m);nominal_sd.append(s)
        effective_sd.append(np.maximum(s*validation[i]['suggested_uncertainty_inflation'],validation[i]['cv_abs_error_q90']/1.645))
    mu=np.stack(means,axis=1)
    sigma_raw=np.stack(nominal_sd,axis=1)
    sigma=np.maximum(np.stack(effective_sd,axis=1),1e-9)
    direction=np.array([1 if x=='max' else -1 for x in goals])
    yrange=np.maximum(Y.max(axis=0)-Y.min(axis=0),1e-9)
    util=np.sum((mu-Y.min(axis=0))/yrange*direction*weight,axis=1)
    util_sd=np.sqrt(np.sum((sigma/yrange*weight)**2,axis=1))
    observed_util=np.sum((Y-Y.min(axis=0))/yrange*direction*weight,axis=1)
                                                                               
    observed_feasible=np.ones(len(Y),bool)
    for idx,op,value in constraints:
        if op in ('>','>='):observed_feasible&=Y[:,idx]>=value
        else:observed_feasible&=Y[:,idx]<=value
    if constraints and not observed_feasible.any():
        warning.append('历史实验没有一条同时满足测量响应约束；改进量采用全部已测数据作为参照，推荐更需要验证。')
    observed_best=float(np.max(observed_util[observed_feasible])) if observed_feasible.any() else float(np.max(observed_util))
    improvement=util-observed_best
    zz=improvement/np.maximum(util_sd,1e-12)
    EI=np.maximum(improvement*norm.cdf(zz)+util_sd*norm.pdf(zz),0)
    feasible_prob=np.ones(len(samples));mean_feasible=np.ones(len(samples),bool)
    for idx,op,threshold in constraints:
        zz=(mu[:,idx]-threshold)/sigma[:,idx]
        feasible_prob*=norm.cdf(zz) if op in ('>','>=') else norm.cdf(-zz)
        mean_feasible&=mu[:,idx]>=threshold if op in ('>','>=') else mu[:,idx]<=threshold
    dist=np.min(cdist(samples,Xn),axis=1)
    unmeasured=dist>1e-5
    within_limits=np.all((candidate_x>=search_lo-1e-9)&(candidate_x<=search_hi+1e-9),axis=1)
    score=np.where(unmeasured&within_limits,EI*feasible_prob,-np.inf)
                                                                              
    can_recommend=(unmeasured & within_limits & mean_feasible & (feasible_prob>=.8)) if constraints else (unmeasured & within_limits)
    if not np.any(np.isfinite(score[can_recommend]) & (score[can_recommend]>1e-12)):
        exploration=(util+1.2*util_sd)*feasible_prob
        score=np.where(unmeasured&within_limits,exploration,-np.inf)
        warning.append('预期改进几乎为零：候选排序退化为偏向探索的启发式指标，不等于真实性能提高。')
    eligible=np.where(can_recommend,score,-np.inf)
    best=int(np.argmax(eligible)) if can_recommend.any() else None
    reliable=score_ok and group_count>=5
    status='CANDIDATE_REQUIRES_VALIDATION'
    if not reliable:status='LOW_MODEL_RELIABILITY';best=None
    elif best is None:status='NO_CONFIDENT_FEASIBLE_CANDIDATE'
    elif dist[best]>.45:
        status='NO_NEARBY_SUPPORTED_CANDIDATE'
        warning.append('最高评分候选离历史设计太远，自动建议已撤回；请优先增加邻近实验或缩小搜索范围。')
        best=None
    recommended=dict(zip(par,map(float,candidate_x[best]))) if best is not None else None
    predicted=dict(zip(resp,map(float,mu[best]))) if best is not None else None
    uncertain=dict(zip(resp,map(float,sigma[best]))) if best is not None else None
    out=pd.DataFrame(candidate_x,columns=par)
    for i,name in enumerate(resp):
        out['predicted_'+name]=mu[:,i]
        out['uncertainty_sd_'+name]=sigma[:,i]
        out['gp_nominal_sd_'+name]=sigma_raw[:,i]
        out['ci95_low_'+name]=mu[:,i]-1.96*sigma[:,i]
        out['ci95_high_'+name]=mu[:,i]+1.96*sigma[:,i]
        out['cv_abs_error_q90_'+name]=validation[i]['cv_abs_error_q90']
    out['constraint_feasibility_probability']=feasible_prob
    out['predicted_constraints_met']=mean_feasible
    out['meets_80pct_feasibility_threshold']=feasible_prob>=.8
    out['acquisition_expected_improvement']=EI
    out['acquisition_score']=np.where(np.isfinite(score),score,np.nan)
    out['distance_to_nearest_design_normalized']=dist
    out['was_already_measured']=~unmeasured
    out['within_user_design_limits']=within_limits
    out['estimated_pareto']=False
    valid_idx=np.flatnonzero(mean_feasible & (feasible_prob>=.8) & unmeasured & within_limits)
    if len(valid_idx):out.loc[valid_idx,'estimated_pareto']=_pareto(mu[valid_idx],goals)
    out['recommended_next_experiment']=False
    out['shortlist_rank']=0
    if best is not None:
        out.loc[best,'recommended_next_experiment']=True
                                                                              
                                                                                
        shortlisted=[best]
        order=np.argsort(-np.where(np.isfinite(score),score,-np.inf))
        for cand in order:
            if len(shortlisted)>=5:break
            if cand==best or not can_recommend[cand] or not np.isfinite(score[cand]):continue
            if np.min(np.linalg.norm(samples[np.array(shortlisted)]-samples[cand],axis=1))<.08:continue
            shortlisted.append(int(cand))
        for rank,ix in enumerate(shortlisted,1):out.loc[ix,'shortlist_rank']=rank
    out=out.sort_values('acquisition_score',ascending=False,na_position='last').reset_index(drop=True)
    report={'status':status,'surrogate':'Gaussian process (Matern 5/2 + WhiteKernel), group-safe out-of-fold check',
      'parameter_columns':par,'response_columns':resp,'data_rows':len(df),'unique_designs':n_designs,
      'independent_validation_groups':group_count,
      'independent_grouping':group_col or 'ONLY EXACT SAME PARAMETER DESIGN GROUPED (NOT PHYSICAL ID)',
      'validation_metrics':validation,'recommended_parameters':recommended,'predicted_responses':predicted,
      'predicted_standard_deviation':uncertain,
      'constraint_feasibility_probability':float(feasible_prob[best]) if best is not None else None,
      'constraint_expression':response_constraint,'nearest_experiment_normalized_distance':float(dist[best]) if best is not None else None,
      'parameter_bounds_observed':{name:[float(l),float(h)] for name,l,h in zip(par,lo,hi)},
      'parameter_bounds_user_allowed':{name:[float(l),float(h)] for name,l,h in zip(par,search_lo,search_hi)},
      'n_candidate_designs':int(len(out)),'n_independent_training_groups':group_count,
      'shortlist_count':int((out.shortlist_rank>0).sum()),
      'seed':int(seed),'warnings':warning,
      'note':'只在已有参数坐标范围内搜索；不等于多维设计的安全可行域。留组验证、防相同设计泄漏及相对均值基线是最低门槛。区间/可行概率是基于GP并用留组误差做保守膨胀的启发式估计，不是有保证的频率覆盖或真实试验成功概率。低可信度时拒绝推荐；任何候选必须新实验核验。'}
    return report,out


def gp_out_of_fold_table(df,parameter_cols,response_cols,group_col=None,seed=42):
    """Audit table used by desktop exports: exact same fold-local preprocessing as engine."""
    par=list(parameter_cols);resp=list(response_cols)
    X=df[par].to_numpy(float);Y=df[resp].to_numpy(float)
    explicit=df[group_col].to_numpy() if group_col else None
    groups,splits=design_groups(X,explicit)
    out=df[par+resp].copy().reset_index(drop=True);out['validation_group']=groups
    for j,name in enumerate(resp):
        p=np.full(len(X),np.nan)
        for a,b in splits:p[b]=_predict(_fit(X[a],Y[a,j],seed)[0],X[b])[0]
        out['cv_predicted_'+name]=p
        out['cv_residual_'+name]=Y[:,j]-p
    return out
