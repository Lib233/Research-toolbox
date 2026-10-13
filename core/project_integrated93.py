""" multi-source research project orchestration.

An explicit manifest is the source of truth: no guessed specimen identity, clock sync,
units, experimental design, or physical motion mode. Existing module engines are reused.
Failure is recorded per modality; the origin and intermediate tables are retained.
"""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .common import read_table, save_csv, save_json

SOURCES=('video_file','seed_file','trajectory_file','stereo_points_file','force_file','image_file','signal_file','measurement_file')
REQUIRED=('experiment_id','condition','sample_id')


def _s(value):
    return '' if pd.isna(value) else str(value).strip()


def _path(root, name):
    if not name:return None
    p=Path(name).expanduser()
    return p if p.is_absolute() else root/p


def _num(v):
    try:
        n=float(v)
        return n if np.isfinite(n) else None
    except (ValueError,TypeError):return None


def _first_numeric(row, field):
    return _num(row[field]) if field in row else None


def _one_record(tab, label, expected, allow_repeats=False):
    if tab.empty:raise ValueError(label+' 的结果表为空')
    if len(tab)!=1 and not allow_repeats:raise ValueError(label+' 的结果含多条独立对象：请在源表明确分组后分析，不能擅自取第一条')
    return tab.iloc[0]


def project_figure(table, output, save_plot, response=''):
    """Descriptive only, retains every row, never invents inferential intervals."""
    numeric=[c for c in table.columns if c not in ('experiment_id','condition','sample_id','source_row','status','source_paths')
             and pd.api.types.is_numeric_dtype(table[c]) and table[c].notna().any()]
    metric=response if response in numeric else (numeric[0] if numeric else '')
    if not metric:return None
    cols=['experiment_id','condition',metric]
    if 'sample_id' in table:cols.append('sample_id')
    df=table[cols].dropna(subset=[metric]).copy()
                                                                                
                                                                                    
    per_specimen=False
    if 'sample_id' in df and df.sample_id.notna().all() and df.sample_id.astype(str).str.strip().ne('').all():
        cross=df.groupby('sample_id').condition.nunique()
        if (cross<=1).all():
            df=df.groupby(['condition','sample_id'],as_index=False,sort=False)[metric].mean()
            per_specimen=True
                                                                             
                                                                               
    if df.empty:return None
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(183/25.4,93/25.4),layout='constrained')
    groups=list(dict.fromkeys(df.condition.astype(str)))
    for i,g in enumerate(groups):
        vals=df.loc[df.condition.astype(str)==g,metric].to_numpy(float)
        axs[0].scatter(np.full(len(vals),i),vals,s=25,zorder=3,alpha=.85,label=g)
        axs[0].plot([i-.18,i+.18],[np.mean(vals)]*2,lw=2.1,color='#293E4B')
    axs[0].set_xticks(range(len(groups)),groups,rotation=10)
    axs[0].set_ylabel(metric)
    axs[0].set_title('a  独立试样均值' if per_specimen else 'a  已记录实验（不代表独立样本数）',loc='left',fontsize=9,fontweight='bold')
    for i,g in enumerate(groups):
        vals=df.loc[df.condition.astype(str)==g,metric].to_numpy(float)
        axs[1].bar(i,float(np.mean(vals)),color=('#397F9D' if i%2==0 else '#C47D5B'),alpha=.85)
    axs[1].set_xticks(range(len(groups)),groups,rotation=10)
    axs[1].set_ylabel('Descriptive mean: '+metric)
    axs[1].set_title('b  条件组描述性汇总（非显著性结论）',loc='left',fontsize=9,fontweight='bold')
    for ax in axs:
        ax.spines[['top','right']].set_visible(False)
        ax.tick_params(labelsize=7)
    fig.text(.04,.02,'Source: '+('one mean per specimen (ID must be verified)' if per_specimen else 'per-experiment records; do not infer independent n')+'; missing excluded. Verify calibration.',fontsize=6)
    save_plot(fig,output/'FIGURE_project_main')
    return metric


from ui_outputs102 import find_output_file

def run_integrated(config,folder,run_module,save_plot):
    out=Path(folder)
    manifest_path=Path(config.get('file',''))
    if not manifest_path.is_file():raise ValueError('多源项目需要一份项目实验清单 CSV/Excel（每一行对应一次实验）。')
    m=read_table(manifest_path,sheet='auto' if manifest_path.suffix.lower() in ('.xlsx','.xlsm') else 0)
    absent=set(REQUIRED)-set(m.columns)
    if absent:raise ValueError('项目清单缺少必需列 '+str(sorted(absent))+'；请使用示例清单或修改原始表头。')
    if m.empty:raise ValueError('项目清单没有实验记录。')
    if len(m)>120:raise ValueError('为避免一次误批处理大量视频，本工作流每次最多120条实验；请按项目分批运行。')
                                                                                           
    for col in REQUIRED:
        m[col]=m[col].map(_s)
        if not m[col].all():raise ValueError('项目清单 '+col+' 存在空白；请填写真实信息。')
    if m.experiment_id.duplicated().any():raise ValueError('experiment_id 必须唯一；多次测量请使用不同实验编号并复用真实 sample_id。')
    if m.groupby('sample_id').condition.nunique().gt(1).any():
                                                                                                 
        cross_condition=True
    else:cross_condition=False
    base=manifest_path.resolve().parent
                                                                        
    indexed=[]
    for i,row in m.iterrows():
        d={'source_row':int(i)+2}
        for col in SOURCES:
            p=_path(base,_s(row.get(col,'')))
            if p is not None and not p.is_file():raise ValueError(f'清单第{i+2}行 {col} 找不到文件：{p}')
            d[col]=p
        if d['seed_file'] is not None and d['video_file'] is None:
            raise ValueError(f'清单第{i+2}行提供 seed_file 却没有 video_file；请配对设置。')
        if not any(d.get(k) is not None for k in ('video_file','trajectory_file','stereo_points_file','force_file','image_file','signal_file','measurement_file')):
            raise ValueError(f'清单第{i+2}行没有任何可分析的数据源。')
        indexed.append(d)
    stage=[];samples=[];warnings=[];index=[]
    confirm_force=config.get('pipeline_protocol_confirm','no')=='yes'
    confirmed_scale=config.get('motion_scale_confirmed','no')=='yes'
    include_stats=config.get('pipeline_integrated_stats','no')=='yes'
    include_opt=config.get('pipeline_integrated_opt','no')=='yes'
    def log(experiment,mod,status,folder_path,note):
        stage.append({'experiment_id':experiment,'stage':mod,'status':status,'folder':str(folder_path or ''),'note':str(note)})
        with (out/'project_progress.log').open('a',encoding='utf-8') as f:
            f.write(f'{experiment} | {mod} | {status} | {note}\n')
    for ix,(i,row) in enumerate(m.iterrows()):
        rid=row.experiment_id
        sources=indexed[ix]
        eout=out/('experiment_'+str(ix+1).zfill(3));eout.mkdir(exist_ok=True)
        vals={'experiment_id':rid,'condition':row.condition,'sample_id':row.sample_id,'source_row':sources['source_row']}
        provenance={'experiment_id':rid,'condition':row.condition,'sample_id':row.sample_id,
                    'sources':{k:str(v) if v else '' for k,v in sources.items() if k in SOURCES}}
        digests={}
        for kind,path in sources.items():
            if kind not in SOURCES or not path:continue
            h=hashlib.sha256()
            with path.open('rb') as file:
                for chunk in iter(lambda:file.read(1024*1024),b''):h.update(chunk)
            digests[kind]=h.hexdigest()
        provenance['source_sha256']=digests
                                                                                                   
        for k in m.columns:
            if str(k).startswith('param_') and _num(row[k]) is not None:vals[k]=_num(row[k])
        def invoke(module,cfg,phase):
            d,r=run_module(module,cfg,eout)
            log(rid,phase,'complete',d,'调用现有模块，原始文件只读；所有中间表、图片及参数均保留')
            for msg in r.get('quality_warnings',[]):warnings.append(f'{rid}/{phase}: {msg}')
            return d,r
                                                                                  
        p=sources['measurement_file']
        if p:
            df=read_table(p)
            if len(df)!=1:
                raise ValueError(f'{rid} 的 measurement_file 应为单次实验一行的数值指标表；当前{len(df)}行。不能直接取第一条。')
            for c in df.columns:
                if c not in (*REQUIRED,'experiment_id','source_row') and _num(df.iloc[0][c]) is not None:
                    vals['measured_'+str(c)]=_num(df.iloc[0][c])
            invoke('数据质检',{'file':str(p)},'测量表质检')
                                                                                        
        p=sources['force_file']
        if p:
            if not confirm_force:
                log(rid,'力学专项','blocked','', '需核实实验实际加载方式、拉伸力读数正负号、力传感器空载零点和拉离分析时间窗；本次不计算正向力—位移积分')
                warnings.append(f'{rid}: 存在力学记录，但没有确认拉离协议，已阻止自动力学专项分析。')
            else:
                fc={'file':str(p),'col_condition':'condition','col_sample_id':'sample_id',
                    'col_time_s':config.get('time_col','time_s'),
                    'col_displacement_mm':config.get('displacement_col','displacement_mm'),
                    'col_force_N':config.get('force_col','force_N'),
                    'tension_sign':config.get('tension_sign','positive'),'force_unit':config.get('force_unit','N'),
                    'time_unit':config.get('time_unit','s'),'displacement_unit':config.get('displacement_unit','mm'),
                    'force_baseline':config.get('force_baseline','first_fraction'),
                    'baseline_fraction':config.get('baseline_fraction','0.05'),
                    'baseline_start_s':config.get('baseline_start_s',''), 'baseline_end_s':config.get('baseline_end_s',''),
                    'baseline_manual_N':config.get('baseline_manual_N',''),
                    'pull_start_s':config.get('pull_start_s',''),'pull_end_s':config.get('pull_end_s',''),
                    'area_mm2':'0','cycle_column':'','plot_size':'双栏 183 mm'}
                try:
                    d,_=invoke('力学分析',fc,'力学专项')
                    per=read_table(find_output_file(d,'independent_specimens.csv'))
                    if len(per)!=1:raise ValueError('力学文件包含多块试样或多个组，请分别拆分并保留真实身份')
                                                                                                    
                    original_force=read_table(p)
                    if not {'condition','sample_id'}.issubset(original_force.columns):
                        raise ValueError('力学源文件缺少 condition/sample_id，无法核实物理试样身份；请补充真实记录')
                    if (original_force['condition'].astype(str).nunique()!=1 or
                        original_force['sample_id'].astype(str).nunique()!=1 or
                        str(per.iloc[0]['condition'])!=row.condition or
                        str(per.iloc[0]['sample_id'])!=row.sample_id):
                        raise ValueError('力学文件内的 condition 或 sample_id 与项目清单不一致；不能静默归并')
                    for metric in ('peak_force_N','separation_work_mJ'):
                        vals[metric]=_first_numeric(per.iloc[0],metric)
                    provenance['force_metrics_csv']=str(find_output_file(d,'independent_specimens.csv'))
                except Exception as e:
                    log(rid,'力学专项','failed','',str(e));warnings.append(f'{rid}/力学：{e}')
                                                                                      
        track=sources['trajectory_file']
        if sources['video_file']:
            if sources['seed_file'] is None:
                log(rid,'视频追踪','blocked','', '需要对原视频确认人工锚点；未自动选择背景轮廓')
                warnings.append(f'{rid}: 视频未配置人工 seed_file，未追踪；其他数据仍正常处理。')
            else:
                try:
                    vc={'file':str(sources['video_file']),'seed_file':str(sources['seed_file']),
                        'tracking_mode':'point_lk','mm_per_pixel':config.get('mm_per_pixel','0.05'),
                        'motion_scale_confirmed':config.get('motion_scale_confirmed','no'),
                        'enable_3d':'no','reconstruction_3d':'none','step':'1',
                        'max_processed_frames':str(config.get('pipeline_integrated_max_frames','1200')),
                        'lk_window_px':'25','lk_pyramid':'3','lk_fb_limit_px':'1.5',
                        'stationary_threshold_mm_s':'.15','roi':'','climb_axis':'right',
                        'motion_smooth_window':'11','motion_max_speed_mm_s':'0',
                        'motion_reference_point':'','motion_pairs':'','pair_point_a':'','pair_point_b':'',
                        'motion_max_frequency_hz':'5','motion_focus_start_s':'','motion_focus_end_s':'',
                        'motion_primary_point':'', 'motion_baseline_end_s':'1',
                        'motion_min_movement_px':'3','motion_sustain_frames':'5',
                        'motion_fb_warning_px':'1', 'motion_manual_event_time_s':'',
                        'motion_manual_event_name':'','motion_review_max_frames':'0',
                        'behavior_enable':'no'}
                    d,_=invoke('视频追踪',vc,'视频标点追踪')
                    if track is None:track=find_output_file(d,'frame_trajectory.csv')
                    else:warnings.append(f'{rid}: 同时提供视频和现有轨迹；已分别保存视频结果，关系分析优先使用清单给定的现有轨迹。')
                except Exception as e:
                    log(rid,'视频追踪','failed','',str(e));warnings.append(f'{rid}/视频：{e}')
        if track:
            try:
                mc={'file':str(track), 'behavior_track_format':config.get('behavior_track_format','auto'),
                    'behavior_time_col':'time_s','behavior_point_col':'point_id','behavior_x_col':'x_px',
                    'behavior_y_col':'y_px','behavior_source_unit':'px','behavior_mode':'generic',
                    'behavior_body':config.get('pipeline_integrated_reference',''),
                    'behavior_feet':config.get('pipeline_integrated_targets',''),
                    'behavior_substrate':'','climb_axis':'right',
                    'behavior_speed_threshold_px_s':config.get('behavior_speed_threshold_px_s','12'),
                    'behavior_min_dwell_s':config.get('behavior_min_dwell_s','0.25'),
                    'mm_per_pixel':config.get('mm_per_pixel','0.05'),
                    'motion_scale_confirmed':config.get('motion_scale_confirmed','no')}
                if sources['signal_file'] and config.get('pipeline_integrated_sync','no')=='yes':
                    mc.update(behavior_force_file=str(sources['signal_file']),
                        behavior_force_time_col=config.get('pipeline_integrated_signal_time','time_s'),
                        behavior_force_value_col=config.get('pipeline_integrated_signal_value','value'),
                        behavior_force_shift_s=config.get('pipeline_integrated_signal_shift','0'),
                        behavior_force_max_gap_s='0.2')
                d,_=invoke('运动关系分析',mc,'多点运动关系')
                ms=read_table(find_output_file(d,'motion_relation_summary.csv'))
                for _,rr in ms.iterrows():
                    point=str(rr.get('target_point','')).strip()
                    if not point:continue
                    safe=''.join(ch if ch.isalnum() or ch=='_' else '_' for ch in point)[:24]
                    for name in ('valid_rate','mean_speed_px_s','median_speed_px_s','candidate_count'):
                        if name in rr and _num(rr[name]) is not None:vals['motion_'+safe+'_'+name]=_num(rr[name])
                vals['motion_target_count']=len(ms)
                provenance['motion_summary_csv']=str(find_output_file(d,'motion_relation_summary.csv'))
            except Exception as e:
                log(rid,'运动关系分析','failed','',str(e));warnings.append(f'{rid}/运动：{e}')
                                                                                             
        p=sources['stereo_points_file']
        if p:
            try:
                points=read_table(p)
                needed={'point_id','valid_3d','X_mm','Y_mm','Z_mm'}
                if not needed.issubset(points.columns):raise ValueError('三维表缺少已校准X/Y/Z或 valid_3d 标记')
                valid=points[points.valid_3d.astype(str).str.lower().isin(('true','1'))].copy()
                if valid.empty:raise ValueError('没有通过三维质量检查的点')
                point=config.get('pipeline_integrated_reference','').strip()
                if not point:point=str(valid.point_id.iloc[0]);warnings.append(f'{rid}: 三维参考点未指定，已临时使用 {point}；请核实其物理意义。')
                valid=valid[valid.point_id.astype(str)==point]
                if valid.empty:raise ValueError('指定三维特征点不存在于有效三维记录')
                xyz=valid[['X_mm','Y_mm','Z_mm']].apply(pd.to_numeric,errors='raise').to_numpy(float)
                if not np.isfinite(xyz).all():raise ValueError('三维数值包含非有限值')
                vals['stereo_valid_3d_points']=len(valid)
                vals['stereo_3d_z_median_mm']=float(np.median(xyz[:,2]))
                vals['stereo_3d_net_displacement_mm']=float(np.linalg.norm(xyz[-1]-xyz[0]))
                log(rid,'已标定三维结果','complete',eout,'复用经过几何检查的X/Y/Z数据；不从单目数据推测深度')
                provenance['stereo_points_csv']=str(p)
            except Exception as e:
                log(rid,'已标定三维结果','failed','',str(e));warnings.append(f'{rid}/三维：{e}')
        p=sources['image_file']
        if p:
            if config.get('pipeline_integrated_image_confirm','no')!='yes':
                log(rid,'图像定量','blocked','','未确认图像标尺与目标亮暗分割含义；不输出面积')
            else:
                try:
                    d,_=invoke('显微图像',{'file':str(p),'um_per_pixel':config.get('pipeline_integrated_um_per_pixel','1'),
                        'mode':config.get('pipeline_integrated_image_mode','bright'),
                        'threshold':config.get('pipeline_integrated_image_threshold',''),'roi':''},'图像定量')
                    im=read_table(find_output_file(d,'image_metrics.csv')).iloc[0]
                    for met in ('area_mm2','area_fraction','foreground_pixels'):
                        if met in im:vals['image_'+met]=_num(im[met])
                    provenance['image_metrics_csv']=str(find_output_file(d,'image_metrics.csv'))
                except Exception as e:
                    log(rid,'图像定量','failed','',str(e));warnings.append(f'{rid}/图像：{e}')
        p=sources['signal_file']
        if p:
            try:
                d,_=invoke('信号处理',{'file':str(p),'time_col':config.get('pipeline_integrated_signal_time','time_s'),
                    'value_col':config.get('pipeline_integrated_signal_value','value'),
                    'filter':'none','window':'7','cutoff_hz':'3','prominence':'.1'},'传感器信号')
                sd=read_table(find_output_file(d,'filtered_signal.csv'))
                if 'raw_value' in sd:
                    vals['signal_mean_raw']=float(pd.to_numeric(sd.raw_value).mean())
                    vals['signal_max_raw']=float(pd.to_numeric(sd.raw_value).max())
                provenance['signal_filtered_csv']=str(find_output_file(d,'filtered_signal.csv'))
            except Exception as e:
                log(rid,'传感器信号','failed','',str(e));warnings.append(f'{rid}/传感器：{e}')
        save_json(provenance,eout/'input_provenance.json')
        samples.append(vals);index.append(provenance)
    combined=pd.DataFrame(samples)
    save_csv(combined,out/'project_metrics_by_experiment.csv')
    def meaning(col):
        if col in ('experiment_id','condition','sample_id','source_row'):
            return {'experiment_id':'一次实验的唯一编号，不是采样帧数',
                    'condition':'实验真实条件或分组，须与实验记录一致',
                    'sample_id':'真实物理试样编号；多次技术重复沿用同一编号',
                    'source_row':'该记录在原始项目清单中的 Excel 行号'}[col]
        if col.startswith('param_'):return '实验前主动设置的可控参数；数值单位需由该列名称和原始实验记录确认'
        if col.startswith('measured_'):return '从该次实验其他测量表直接提取的数值；未经物理模型二次解释'
        if col=='peak_force_N':return '在用户选定时间窗内，扣除零点并统一符号后得到的最大非负力，单位 N；未校验法向加载时不能称为法向黏附力'
        if col=='separation_work_mJ':return '校正后非负力沿所选位移轴的积分，单位 mJ；可能包含装置及形变耗能，不能直接当作界面黏附能'
        if col.startswith('motion_'):return '轨迹特征点的二维投影运动指标；依赖点位跟踪和坐标系核对，参见单阶段明细'
        if col.startswith('image_'):return '基于阈值分割的图像定量指标；面积需真实微米/像素标定'
        if col.startswith('signal_'):return '传感器原始数值概况；单位继承原数据，不表示已物理同步'
        if col.startswith('stereo_'):return '来自外部已经标定且通过几何质量检查的三维坐标；非单目推断'
        return '本次输出数值，须结合对应阶段的结果字典和原始单位核实'
    save_csv(pd.DataFrame({'column':list(combined.columns),
                           '中文定义与风险提醒':[meaning(c) for c in combined.columns]}),
             out/'project_metric_dictionary.csv')
                                                                                          
    if include_stats:
        selected=config.get('pipeline_integrated_response','').strip()
        if not selected or selected not in combined:
            log('PROJECT','独立样本统计','blocked','',f'选定响应指标 {selected!r} 不在统一指标表中，请先查看实际生成的列名')
            warnings.append('统计未执行：响应列不存在。')
        elif config.get('pipeline_confirm_id')!='yes' or cross_condition:
            log('PROJECT','独立样本统计','blocked','','没有核实独立试样身份或试样跨条件；配对设计请使用高级统计')
            warnings.append('统计未执行：独立试样身份尚未确认，或同一试样跨组。')
        else:
            have=combined[['condition','sample_id',selected]].copy().dropna()
            if have.condition.nunique()<2 or have.groupby('condition').sample_id.nunique().min()<3:
                log('PROJECT','独立样本统计','blocked','','自动推断统计至少需要两组且每组至少三件独立试样；更小数据仍可做描述性分析')
                warnings.append('统计未执行：有效独立试样不足。')
            else:
                ready=have.rename(columns={selected:'value'})
                save_csv(ready,out/'project_stats_ready.csv')
                d,r=run_module('独立样本统计',{'file':str(out/'project_stats_ready.csv'),
                    'col_condition':'condition','col_sample_id':'sample_id','col_value':'value',
                    'bootstrap_seed':'42','bootstrap_rounds':'3000'},out)
                log('PROJECT','独立样本统计','complete',d,'以独立试样为单位汇总，可查看统计假设、诊断和样本量')
                warnings.extend(r.get('quality_warnings',[]))
    if include_opt:
        response=config.get('pipeline_integrated_response','').strip()
        pars=[q.strip() for q in config.get('pipeline_integrated_design','').split(',') if q.strip()]
        optable=combined.dropna(subset=[*pars,response]) if response in combined and all(p in combined for p in pars) and pars else pd.DataFrame()
        if config.get('pipeline_integrated_opt_confirm')!='yes' or len(optable)<15:
            log('PROJECT','实验数据优化','blocked','','必须明确确认设计变量与响应、至少15条完整记录，并在外推前验证预测误差')
            warnings.append('未启动实验参数推荐：确认条件或完整记录数不足。')
        else:
            design=optable[[*pars,response,'sample_id']].copy()
            save_csv(design,out/'project_optimization_ready.csv')
            oc={'file':str(out/'project_optimization_ready.csv'),'parameters':','.join(pars),'responses':response,
                'goals':config.get('pipeline_integrated_goal','max'),'weights':'1','surrogate':'GaussianProcess',
                'group_col':'sample_id','seed':'42','constraints':'', 'parameter_bounds':'',
                'candidate_count':'384'}
            try:
                d,r=run_module('实验数据优化',oc,out)
                log('PROJECT','实验数据优化','complete',d,'跨实验候选推荐为预测值，必须进一步实验验证')
                warnings.extend(r.get('quality_warnings',[]))
            except Exception as e:
                log('PROJECT','实验数据优化','failed','',str(e));warnings.append('实验数据优化失败：'+str(e))
    metric=project_figure(combined,out,save_plot,config.get('pipeline_integrated_response','').strip())
    log('PROJECT','联合指标图版','complete' if metric else 'blocked',out if metric else None,
        '仅描述所有有效数值，不把测量误差、试样重复和模型推荐混为一谈' if metric else '没有可以绘制的数值指标')
    save_csv(pd.DataFrame(stage),out/'project_stage_audit.csv')
    save_csv(pd.DataFrame(index),out/'project_source_index.csv')
                                                              
    save_json({'project_experiments':len(combined),'stage_count':len(stage),'warning_count':len(warnings),
               'metrics':list(combined.columns),'sources':list(SOURCES),'source_manifest':str(manifest_path.resolve()),
               'conditions':sorted(combined.condition.unique().tolist()),'warnings':warnings},out/'project_summary.json')
    return {'pipeline_type':'multi_source_project','project_experiments':len(combined),
            'metrics_count':len(combined.columns)-4,'project_main_metric':metric,
            'completed_steps':sum(s['status']=='complete' for s in stage),
            'blocked_steps':sum(s['status']=='blocked' for s in stage),
            'failed_steps':sum(s['status']=='failed' for s in stage),
            'quality_warnings':warnings},stage
