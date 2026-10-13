""": geometrically interpretable relationships from VALID calibrated 3-D points.

No monocular depth inference. Does not interpolate dropped points, or regard
reprojection residual as true 3-D measurement uncertainty. Pair distance and
three-point included angle are invariant to camera rigid rotation/translation.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

REQUIRED={'frame','time_s','point_id','valid_3d','x_mm','y_mm','z_mm'}

def analyze_spatial_relations(data:pd.DataFrame, reference:str='',pairs:list[tuple[str,str]]|None=None,triplets:list[tuple[str,str,str]]|None=None, max_pairs:int=30):
    missing=REQUIRED-set(data.columns)
    if missing:raise ValueError('三维轨迹缺少列：'+', '.join(sorted(missing)))
    if data.empty:raise ValueError('三维轨迹表为空。')
    d=data.copy();d['point_id']=d.point_id.astype(str)
    if d.duplicated(['frame','point_id']).any():raise ValueError('同一帧同名特征点重复，无法可靠计算三维点间关系。')
    for c in ('time_s','x_mm','y_mm','z_mm'):
        d[c]=pd.to_numeric(d[c],errors='coerce')
    d['valid_3d']=d['valid_3d'].map(lambda v: str(v).lower() in ('true','1','yes'))
    names=sorted(d.point_id.unique());name_set=set(names)
    if reference and reference not in name_set:raise ValueError('三维参考点不存在：'+reference)
    if len(names)>40:raise ValueError('一次最多分析40个命名三维点，避免输出组合爆炸；请先选择有科学意义的点。')
    valid=d.valid_3d & np.isfinite(d[['x_mm','y_mm','z_mm']]).all(axis=1)
    d.loc[~valid,['x_mm','y_mm','z_mm']]=np.nan
    d['valid_3d']=valid
    d=d.sort_values(['frame','point_id'])
    positions={(int(r.frame),r.point_id):np.array([r.x_mm,r.y_mm,r.z_mm],float)
              for r in d.itertuples(index=False) if r.valid_3d}
    frames=sorted(d.frame.astype(int).unique())
    time_by_frame={int(k):float(v) for k,v in d[['frame','time_s']].drop_duplicates().itertuples(index=False)}
    if not all(np.isfinite(list(time_by_frame.values()))):raise ValueError('三维时间戳必须是有限数字。')
    if d.groupby('frame').time_s.nunique().gt(1).any():raise ValueError('同一帧内各特征点时间不一致，不能当成同步三维记录。')
    frame_times=np.array([time_by_frame[k] for k in frames],float)
    if len(frame_times)>1 and np.any(np.diff(frame_times)<=0):raise ValueError('三维坐标的帧时间必须严格递增。')
    if not pairs:
        pairs=[(names[i],names[j]) for i in range(len(names)) for j in range(i+1,len(names))][:max_pairs]
    if len(pairs)>max_pairs:raise ValueError(f'指定点对多于{max_pairs}，请只保留研究所需的点对。')
    if triplets is None:triplets=[]
    if len(triplets)>30:raise ValueError('三点夹角最多分析30组。')
    for group in [*pairs,*triplets]:
        if any(n not in name_set for n in group) or len(set(group))!=len(group):
            raise ValueError('点对或三点夹角中存在未追踪的点、或同一个点被重复使用：'+str(group))
    per_point=[]
    for r in d.itertuples(index=False):
        if reference:
            ref=positions.get((int(r.frame),reference))
            vec=positions.get((int(r.frame),r.point_id))
            valid_relative=vec is not None and ref is not None
            rel=(vec-ref) if valid_relative else [np.nan]*3
        else:valid_relative=False;rel=[np.nan]*3
        per_point.append({'frame':int(r.frame),'time_s':float(r.time_s),'point_id':r.point_id,
                          'valid_3d':bool(r.valid_3d), 'reference':reference,
                          'relative_valid':valid_relative,'relative_x_mm':rel[0],
                          'relative_y_mm':rel[1],'relative_z_mm':rel[2],
                          'relative_distance_mm':float(np.linalg.norm(rel)) if valid_relative else np.nan})
    per_pair=[]
    for a,b in pairs:
        for f in frames:
            va=positions.get((f,a));vb=positions.get((f,b))
            ok=va is not None and vb is not None
            diff=vb-va if ok else [np.nan]*3
            per_pair.append({'frame':f,'time_s':time_by_frame[f],'point_a':a,'point_b':b,'valid_pair':ok,
                'dx_mm':diff[0],'dy_mm':diff[1],'dz_mm':diff[2],
                'distance_3d_mm':float(np.linalg.norm(diff)) if ok else np.nan})
    per_angle=[]
    for a,vertex,c in triplets:
        for f in frames:
            v1=positions.get((f,a));v=positions.get((f,vertex));v2=positions.get((f,c))
            valid=v1 is not None and v is not None and v2 is not None
            angle=np.nan
            if valid:
                u=v1-v;w=v2-v;den=np.linalg.norm(u)*np.linalg.norm(w)
                if den>1e-10:angle=float(np.degrees(np.arccos(np.clip(np.dot(u,w)/den,-1,1))))
                else:valid=False
            per_angle.append({'frame':f,'time_s':time_by_frame[f], 'point_a':a,'vertex_point':vertex,'point_c':c,
                              'angle_valid':valid,'included_angle_deg':angle})
    point_df=pd.DataFrame(per_point)
    pair_df=pd.DataFrame(per_pair,columns=['frame','time_s','point_a','point_b','valid_pair','dx_mm','dy_mm','dz_mm','distance_3d_mm'])
    angle_df=pd.DataFrame(per_angle,columns=['frame','time_s','point_a','vertex_point','point_c','angle_valid','included_angle_deg'])
    summary=[]
    for (a,b),group in pair_df.groupby(['point_a','point_b'],sort=False):
        v=group.loc[group.valid_pair,'distance_3d_mm']
        summary.append({'metric':'pair_distance','point_names':f'{a},{b}','total_frames':len(group),
            'valid_frames':len(v),'valid_ratio':len(v)/len(group),
            'mean_value':float(v.mean()) if len(v) else np.nan,
            'range_value':float(v.max()-v.min()) if len(v) else np.nan,'unit':'mm',
            'interpretation':'空间点间距离，仅当两点各自的三维位置通过测量质量筛选；不能视为材料应变。'})
    for (a,b,c),group in angle_df.groupby(['point_a','vertex_point','point_c'],sort=False):
        v=group.loc[group.angle_valid,'included_angle_deg']
        summary.append({'metric':'three_point_angle','point_names':f'{a},{b},{c}', 'total_frames':len(group),
           'valid_frames':len(v),'valid_ratio':len(v)/len(group),'mean_value':float(v.mean()) if len(v) else np.nan,
           'range_value':float(v.max()-v.min()) if len(v) else np.nan,'unit':'deg',
           'interpretation':'三点在空间中的夹角（顶点为中间点）；不等于完整刚体姿态或真实关节全部自由度。'})
    return point_df,pair_df,angle_df,pd.DataFrame(summary,columns=['metric','point_names','total_frames','valid_frames','valid_ratio','mean_value','range_value','unit','interpretation'])

def parse_point_combinations(pair_text='',angle_text=''):
    def parse(text,n,label):
        out=[]
        for part in str(text).replace('；',';').split(';'):
            if not part.strip():continue
            tokens=[x.strip() for x in part.replace('，',',').split(',')]
            if len(tokens)!=n or any(not x for x in tokens):raise ValueError(f'{label} 请用英文逗号分隔 {n} 个点，多个组合用分号分隔。')
            out.append(tuple(tokens))
        return out
    return parse(pair_text,2,'三维点对'),parse(angle_text,3,'三点夹角')
