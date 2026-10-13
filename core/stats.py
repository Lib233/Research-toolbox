"""Independent specimen-aware statistics. No frame-level pseudo-replication."""
import numpy as np
import pandas as pd
from scipy import stats

def aggregate_specimens(df: pd.DataFrame) -> pd.DataFrame:
    if not {'condition','sample_id','value'} <= set(df.columns):
        raise ValueError('Need columns condition, sample_id, value.')
    x = df[['condition','sample_id','value']].copy()
    x['value'] = pd.to_numeric(x.value, errors='raise')
    if x.isna().any().any() or not np.isfinite(x.value.to_numpy()).all():
        raise ValueError('Missing / nonfinite entries.')
    return x.groupby(['condition','sample_id'], as_index=False)['value'].mean()

def describe_groups(specimens: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for condition, g in specimens.groupby('condition'):
        x = g.value.to_numpy(float); n=len(x); mean=float(x.mean())
        sd=float(x.std(ddof=1)) if n>1 else np.nan
        sem=sd/np.sqrt(n) if n>1 else np.nan
        margin=float(stats.t.ppf(0.975, n-1)*sem) if n>1 else np.nan
        rows.append(dict(condition=condition, n_independent=n, mean=mean, sd=sd,
                         sem=sem, ci95_low=mean-margin, ci95_high=mean+margin))
    return pd.DataFrame(rows)

def welch_comparison(specimens: pd.DataFrame) -> dict:
    groups=list(specimens.condition.unique())
    if len(groups)!=2:
        raise ValueError('Welch test requires exactly two conditions.')
    a=specimens[specimens.condition==groups[0]]; b=specimens[specimens.condition==groups[1]]
    if set(a.sample_id) & set(b.sample_id):
        raise ValueError('Shared sample IDs across conditions: possibly paired/repeated measures; Welch test is invalid here.')
    if min(len(a),len(b))<2:
        raise ValueError('Each group needs >=2 independent specimens.')
    x=a.value.to_numpy(float); y=b.value.to_numpy(float)
    t,p=stats.ttest_ind(x,y,equal_var=False)
    if not np.isfinite(p):
        raise ValueError('Insufficient variance to perform Welch test.')
    var_x=np.var(x,ddof=1); var_y=np.var(y,ddof=1)
    nx=len(x); ny=len(y); se2=var_x/nx+var_y/ny
    df=(se2**2)/((var_x/nx)**2/(nx-1)+(var_y/ny)**2/(ny-1))
    delta=float(x.mean()-y.mean()); ci=float(stats.t.ppf(.975,df)*np.sqrt(se2))
    return dict(group_a=groups[0],group_b=groups[1],
                delta_mean_a_minus_b=delta,t_stat=float(t),p_value=float(p),
                welch_df=float(df),ci95_delta_low=delta-ci,ci95_delta_high=delta+ci,
                n_a=nx,n_b=ny)


def statistical_diagnostics(specimens: pd.DataFrame, seed=42, n_boot=3000):
    """Descriptive diagnostics at independent specimen level, reproducible cluster-safe bootstrap.

    These are diagnostics, *not* an automatic promise that parametric tests are valid.
    """
    x=specimens.copy();rng=np.random.default_rng(int(seed));report=[]
    for condition,g in x.groupby('condition',sort=False):
        vals=g.value.to_numpy(float);n=len(vals)
        if n>=3 and n<=5000 and np.ptp(vals)>0:
            W,p=stats.shapiro(vals)
        else:W,p=np.nan,np.nan
        if n>=2:
            bootstrap=rng.choice(vals,size=(n_boot,n),replace=True).mean(axis=1)
            lo,hi=np.percentile(bootstrap,[2.5,97.5])
        else:lo,hi=np.nan,np.nan
        report.append({'condition':condition,'n_independent':n,'shapiro_W':W,
          'shapiro_p_value':p,'bootstrap_mean_ci95_low':lo,'bootstrap_mean_ci95_high':hi,
          'bootstrap_resamples':n_boot,'bootstrap_seed':seed})
    return pd.DataFrame(report)


def welch_effect_sizes(specimens: pd.DataFrame):
    """Return standardized effects with explicit group orientation, without changing Welch test choice."""
    groups=list(specimens.condition.unique())
    if len(groups)!=2:raise ValueError('需要恰好两组来计算组间效应量。')
    a=specimens[specimens.condition==groups[0]];b=specimens[specimens.condition==groups[1]]
    if set(a.sample_id)&set(b.sample_id):raise ValueError('检测到交叉组共享试样 ID，请先建立配对模型而非独立组模型。')
    n1,n2=len(a),len(b)
    if min(n1,n2)<2:raise ValueError('每组至少需要2个独立试样。')
    x=a.value.to_numpy(float);y=b.value.to_numpy(float)
    pooled=((n1-1)*np.var(x,ddof=1)+(n2-1)*np.var(y,ddof=1))/(n1+n2-2)
    d=(np.mean(x)-np.mean(y))/np.sqrt(pooled) if pooled>0 else float('nan')
    correction=(1-3/(4*(n1+n2)-9)) if n1+n2>3 else np.nan
    return {'direction':'group_a_minus_group_b', 'group_a':groups[0], 'group_b':groups[1],
      'cohens_d':float(d),'hedges_g':float(d*correction),'note':'标准化效应量为A组减B组；为描述性估计，不用于替代置信区间。'}


def variance_diagnostic(specimens):
    groups=[g.value.to_numpy(float) for _,g in specimens.groupby('condition',sort=False)]
    if len(groups)<2 or min(map(len,groups))<2:return {'levene_p_value':None}
    z=stats.levene(*groups,center='median')
    return {'levene_p_value':float(z.pvalue),'note':'方差检验不作为自动选择检验的唯一依据；小样本功效可能不足。'}
