"""Module dispatcher. All outputs live in a new, immutable run folder; original inputs never overwritten."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .common import read_table,columns,identify_column,save_csv,save_json,save_plot,create_run,clean_report,export_result_workbook
from .force import analyze_force
from .adhesion_protocol import AdhesionProtocol,analyze_adhesion_protocol
from .storyboard import force_storyboard,single_force_storyboard,track_storyboard,statistical_storyboard
from .track_validation import make_review_sheet,evaluate_reference
from .video import TrackConfig,track_video,motion_summary
from .image_native import analyze_native_image
from .stats import aggregate_specimens,describe_groups,welch_comparison,statistical_diagnostics,welch_effect_sizes,variance_diagnostic
from .signals import analyze_signal
from .synchronization import synchronize_signals
from .fitting import fit_curve,MODELS
from .optimization import optimize_equation,optimize_experiments,quadratic_out_of_fold_table
from .bayesian_design import optimize_bayesian,gp_out_of_fold_table
from .batch_force import load_force_folder,specimen_force_summary
from .advanced_stats import prepare_independent,paired_comparison,multiple_group_comparison,mixed_effects,measurement_uncertainty
from .trajectory_edit import apply_track_corrections
from .point_tracking import PointTrackConfig,track_marked_points,point_summary,pair_geometry,apply_point_corrections,evaluate_point_reference
from .motion_analysis82 import annotate_motion,relative_motion,multiple_pairs,screen_cycles
from .motion_figures82 import plot_temporal_tracks,plot_motion_quality,plot_relative_motion,plot_cycle_screen
from .motion_overlay82 import export_overlay_video
from .motion_story83 import select_primary,movement_evidence,plot_experiment_story,write_guide
from .reconstruction3d84 import stereo_triangulate,pnp_rigid_pose,plot_3d_result,stereo_pair_distances,summarize_3d
from .video_mode85 import effective_3d_mode,normalized_video_config
from .functional_gait86 import BehaviorSettings,normalized_landmarks,support_kinematics,align_force_to_frames,behavior_figures,behavior_report
from .universal_motion87 import MotionRelationSettings, analyze_relations,plot_relations87,report_relations87
from .fit_diagnostics import compare_models,parameter_ci
from .auto_sync import suggest_clock_offset
from .plots import force_figure,track_figure,groups_figure
from .figure_engine import make_chart,FigureOptions,export_figure
from .writing import generate_draft,export_docx
from ui_guidance import files_guide, QC_COLUMNS


def _names(v):return [x.strip() for x in v.replace(';',',').split(',') if x.strip()]
def _num(v):return float(str(v).strip())
def _table(cfg):return read_table(cfg['file'],sheet='auto' if str(cfg['file']).lower().endswith(('.xlsx','.xlsm')) else 0)
def _mapped(d,cfg,fields):
    mapping={}
    for name in fields:
        chosen=cfg.get('col_'+name,name)
        if chosen not in d and chosen==name:
            chosen=identify_column(d.columns,name) or chosen
        mapping[name]=chosen
    return columns(d,mapping)
def _chart_xy(x,y,xlabel,ylabel,title):
    f,ax=plt.subplots(figsize=(7,4.5),layout='constrained')
    ax.plot(x,y,lw=1.8);ax.set(xlabel=xlabel,ylabel=ylabel,title=title);ax.grid(alpha=.2)
    return f

                                                                                   
                                                                                    
import threading as _threading
_RUN_CONTEXT=_threading.local()
def _runtime_check(stage='运行检查点'):
    event=getattr(_RUN_CONTEXT,'cancel_event',None)
    if event is not None and event.is_set():
        raise RuntimeError('用户请求停止：任务在 '+stage+' 的安全检查点退出；本次未完成结果不可用于科研结论。')
    callback=getattr(_RUN_CONTEXT,'progress_callback',None)
    if callback is not None:
        try:callback(stage)
        except (OSError,ValueError,RuntimeError):pass

def run_module(module,cfg,output_parent,cancel_event=None,progress_callback=None):
    """Task wrapper: restore thread-local state even when validation/cancel fails.

    Nested project stages inherit the parent's cooperative cancellation request;
    later independent tasks must never inherit a previous cancelled run.
    """
    prev_cancel=getattr(_RUN_CONTEXT,'cancel_event',None)
    prev_progress=getattr(_RUN_CONTEXT,'progress_callback',None)
    if cancel_event is not None:_RUN_CONTEXT.cancel_event=cancel_event
    if progress_callback is not None:_RUN_CONTEXT.progress_callback=progress_callback
    try:
        return _run_module_impl(module,cfg,output_parent)
    finally:
        if prev_cancel is None:
            if hasattr(_RUN_CONTEXT,'cancel_event'):delattr(_RUN_CONTEXT,'cancel_event')
        else:_RUN_CONTEXT.cancel_event=prev_cancel
        if prev_progress is None:
            if hasattr(_RUN_CONTEXT,'progress_callback'):delattr(_RUN_CONTEXT,'progress_callback')
        else:_RUN_CONTEXT.progress_callback=prev_progress

def _run_module_impl(module,cfg,output_parent):
    _runtime_check('开始 '+str(module))
    if module in ('视频追踪','轨迹人工修正'):
        cfg=normalized_video_config(cfg)
    primary=cfg.get('file','')
    sources=[primary]
    if module in ('写作辅助','分析结果整理'):sources=[cfg.get('file','')]
    if module=='多源同步':sources=[cfg.get('file',''),cfg.get('file_b','')]
    if module=='视频追踪':sources=[primary]+[cfg[k] for k in ('seed_file','reference_file','stereo_right_track_file','stereo_calibration_file','rigid_geometry_file') if cfg.get(k)]
    if (module in ('运动机制分析','运动关系分析') or (module in ('视频追踪','轨迹人工修正') and cfg.get('behavior_enable','no')=='yes')) and cfg.get('behavior_force_file'):
        sources.append(cfg['behavior_force_file'])
    if module=='轨迹人工修正':sources=[primary]+[cfg[k] for k in ('corrections_file','video_file','stereo_right_track_file','stereo_calibration_file','rigid_geometry_file') if cfg.get(k)]
    _runtime_check('读取输入、建立新结果目录')
    out=create_run(output_parent,module,sources,cfg)
    results={};warnings=[]
    def publish_plot(fig,prefix):
        return save_plot(fig,prefix,cfg)
    def run_behavior(track):
        """: task-neutral default;  specialised support analysis remains opt-in.

        A failed OPTIONAL add-on never discards successful 2-D tracking results.
        """
        source=track.copy()
                                                                                              
        if 'point_id' not in source.columns and {'frame','time_s','x_px','y_px'}.issubset(source):
            source['point_id']='tracked_center'
        mode=str(cfg.get('behavior_mode', 'support' if module=='运动机制分析' else 'generic')).strip()
        if mode not in ('support','generic'):raise ValueError('运动关系分析方法只能为 generic 或 support。')
        scale=float(cfg.get('mm_per_pixel','0.05')) if (cfg.get('motion_scale_confirmed')=='yes' or cfg.get('behavior_source_unit')=='mm') else None
        normalized=normalized_landmarks(source,fmt='long',point_col='point_id',x_col='x_px',y_col='y_px')
        if mode=='generic':
            setup=MotionRelationSettings(
                targets=_names(str(cfg.get('behavior_feet',''))),
                reference=str(cfg.get('behavior_body','')).strip(),
                fixed_marker=str(cfg.get('behavior_substrate','')).strip(),
                positive_axis=cfg.get('climb_axis','right'),
                slow_threshold_px_s=float(cfg.get('behavior_speed_threshold_px_s','12')),
                min_duration_s=float(cfg.get('behavior_min_dwell_s','0.25')),
                mm_per_pixel=scale)
            frames,bouts,summary,pairs=analyze_relations(normalized,setup)
            save_csv(frames,out/'motion_relation_frames.csv')
            save_csv(bouts,out/'motion_relation_bouts.csv')
            save_csv(summary,out/'motion_relation_summary.csv')
            save_csv(pairs,out/'motion_relation_pairs.csv')
            signal=None
            force_path=cfg.get('behavior_force_file','').strip()
            if force_path:
                reference_times=frames[['frame','time_s']].drop_duplicates().sort_values('frame')
                signal=align_force_to_frames(reference_times,read_table(force_path),
                   time_col=cfg.get('behavior_force_time_col','time_s'),
                   value_col=cfg.get('behavior_force_value_col','force_N'),
                   shift_s=float(cfg.get('behavior_force_shift_s','0')),
                   max_gap_s=float(cfg.get('behavior_force_max_gap_s','0.1')))
                save_csv(signal,out/'motion_external_signal_aligned.csv')
            publish_plot(plot_relations87(frames,bouts,summary,pairs,signal),out/'FIGURE_motion_relation_overview')
                                                                                                       
            from .editorial_figures88 import motion_figure
            publish_plot(motion_figure(frames,bouts,pairs),out/'FIGURE_motion_editorial_88')
            (out/'运动关系分析_阅读报告.md').write_text(report_relations87(setup,frames,bouts,summary,pairs),encoding='utf-8-sig')
            warning=['本次计算描述特征点的二维投影运动，不自动识别吸附、飞行状态、完整步态或三维机构运动。',
                     '低速候选来自用户选定的阈值和实际可追踪帧，应结合采样频率与跟踪误差复核。']
            if not setup.fixed_marker:warning.append('没有固定参考点：假设摄像机固定。若镜头移动，位移/低速候选可能包含镜头运动。')
            return {'motion_relation_status':'PROJECTED_KINEMATICS_ONLY',
                    'motion_relation_targets':list(summary.target_point),
                    'motion_relation_target_count':len(summary),
                    'motion_relation_candidate_count':len(bouts),
                    'motion_relation_pair_count':len(set(zip(pairs.point_a,pairs.point_b))) if len(pairs) else 0},warning
                                                                                 
        setting=BehaviorSettings(
            body=str(cfg.get('behavior_body','')).strip(),
            feet=_names(str(cfg.get('behavior_feet',''))),
            substrate=str(cfg.get('behavior_substrate','')).strip(),
            positive_axis=cfg.get('climb_axis','right'),
            stationary_threshold_px_s=float(cfg.get('behavior_speed_threshold_px_s','12')),
            min_dwell_s=float(cfg.get('behavior_min_dwell_s','0.25')),scale_mm_per_px=scale)
        if not setting.body:raise ValueError('足端专项分析需要明确设置身体/机身点。')
        frames,bouts,summary,overlap=support_kinematics(normalized,setting)
        save_csv(frames,out/'behavior_frame_states.csv')
        save_csv(bouts,out/'behavior_candidate_bouts.csv')
        save_csv(summary,out/'behavior_foot_summary.csv')
        save_csv(overlap,out/'behavior_phase_overlap.csv')
        force_path=cfg.get('behavior_force_file','').strip()
        force_aligned=None
        if force_path:
            force_aligned=align_force_to_frames(frames,read_table(force_path),
                time_col=cfg.get('behavior_force_time_col','time_s'),
                value_col=cfg.get('behavior_force_value_col','force_N'),
                shift_s=float(cfg.get('behavior_force_shift_s','0')),
                max_gap_s=float(cfg.get('behavior_force_max_gap_s','0.1')))
            save_csv(force_aligned,out/'behavior_external_force_aligned.csv')
        publish_plot(behavior_figures(frames,bouts,summary,force_aligned),out/'FIGURE_mechanism_phase_and_motion')
        (out/'运动机制分析_阅读报告.md').write_text(
            behavior_report(setting,summary,bouts,overlap,force_present=force_aligned is not None),encoding='utf-8-sig')
        note=['低速段只是足端二维投影的运动学候选，不能当成真实吸附或接触状态。',
              '足端专项分析要求对应点在视频中已经实际标注和核对。']
        if not setting.substrate:note.append('没有固定表面参考点：默认相机静止。')
        return {'behavior_analysis_status':'IMAGE_KINEMATICS_CANDIDATE_ONLY',
                'behavior_body_point':setting.body,'behavior_foot_points':setting.feet,
                'behavior_substrate_point':setting.substrate or '未提供',
                'behavior_candidate_bouts':len(bouts),'behavior_output_prefix':'behavior_',
                'behavior_scale_confirmed':setting.scale_mm_per_px is not None},note
    def add_optional_behavior(track):
        """Never let an unrequested or failed add-on invalidate core video results."""
        if str(cfg.get('behavior_enable','no')).lower()!='yes':return {},[]
        try:return run_behavior(track)
        except (ValueError,KeyError,TypeError) as exc:
                                                                                                
            return {'motion_relation_status':'OPTIONAL_SKIPPED'},[
                '基础二维追踪已经完成；可选运动关系分析未执行：'+str(exc)+
                '。请检查本次轨迹的 point_id，或清空目标点名以自动分析真实存在的点。']
    def reconstruct_3d_optional(point_track):
                                                                                      
        mode=effective_3d_mode(cfg)
        if mode=='none':
                                                                                                             
            return {},[]
        calib=cfg.get('stereo_calibration_file','').strip()
        if not calib:raise ValueError('已开启三维分析，但没有相机标定 JSON。请使用标定向导，不能猜测相机参数。')
        if mode=='stereo':
            right=cfg.get('stereo_right_track_file','').strip()
            if not right:raise ValueError('双目重建需要从右相机视频独立追踪得到的 CSV。请先分析第二个视频，使用相同点名。')
            points=stereo_triangulate(point_track,read_table(right),calib,
                 offset_right_s=float(cfg.get('stereo_time_offset_s','0')),
                 tolerance_s=float(cfg.get('stereo_match_tolerance_s','0.012')),
                 max_reprojection_px=float(cfg.get('stereo_max_reprojection_px','2')),
                 min_ray_angle_deg=float(cfg.get('stereo_min_ray_angle_deg','0.5')))
            save_csv(points,out/'stereo_3d_points.csv')
            save_csv(summarize_3d(points),out/'three_d_point_summary.csv')
            pairs=stereo_pair_distances(points)
            if not pairs.empty:save_csv(pairs,out/'three_d_point_pairs.csv')
            publish_plot(plot_3d_result(points),out/'FIGURE_calibrated_3d_trajectory')
            valid=points[points.valid_3d]
            stats={'three_d_status':'CALIBRATED_STEREO_RECONSTRUCTION','three_d_valid_points':len(valid),
                'three_d_attempted_points':len(points),'three_d_valid_rate':round(len(valid)/max(len(points),1),4),
                'three_d_frame':'left_camera_X_right_Y_down_Z_forward_mm',
                'three_d_reprojection_error_median_px':float(np.median(np.maximum(valid.reprojection_error_left_px,valid.reprojection_error_right_px))) if len(valid) else None,
                'three_d_note':'只有同步、标定与三角质量通过的点才有真实尺度的XYZ；原视频双目标注错误仍会影响深度。'}
            warning=[]
            if len(valid)<.6*len(points):warning.append('三维有效点不足60%，请优先检查双相机时间同步/光学标定/对应特征点身份。')
            return stats,warning
        if mode=='rigid_pnp':
            geom=cfg.get('rigid_geometry_file','').strip()
            if not geom:raise ValueError('PnP需要已知CAD或实测的刚体三维特征点 CSV，不能用于任意柔性昆虫翅膀。')
            posed=pnp_rigid_pose(point_track,read_table(geom),calib,
                    max_reprojection_px=float(cfg.get('stereo_max_reprojection_px','2')))
            save_csv(posed,out/'rigid_body_pose_3d.csv')
            publish_plot(plot_3d_result(posed,'已知刚体的三维位姿（PnP）'),out/'FIGURE_rigid_3d_pose')
            good=int(posed.valid_pose.sum())
            return {'three_d_status':'CALIBRATED_RIGID_OBJECT_PNP','three_d_pose_valid_frames':good,
                'three_d_pose_total_frames':len(posed),'three_d_frame':'camera_X_right_Y_down_Z_forward_mm',
                'three_d_note':'结果是已知刚体模型坐标原点的相机系位姿；不能拿变形翅尖套刚体模型。'},([] if good else ['所有帧的刚体PnP位姿均未通过检查，不能解释为三维轨迹。'])
        raise ValueError('未知的三维分析模式：'+str(mode))
    try:
        if module=='项目工作流':
            from .project_workflow88 import execute_workflow
            results=execute_workflow(cfg,out,run_module,publish_plot)
            warnings.extend(results.get('quality_warnings',[]))
        elif module=='数据质检':
            df=_table(cfg);report=clean_report(df)
            report['status']='flag_only_no_data_deleted';save_csv(report,out/'column_quality.csv')
            from .common import locate_quality_issues
            save_csv(locate_quality_issues(df),out/'quality_issues.csv')
            save_csv(df.head(50),out/'data_preview_first50.csv')
            duplicates=int(df.duplicated().sum())
            results={'rows':len(df),'columns':len(df.columns),'exact_duplicate_rows':duplicates,
                     'total_missing_cells':int(df.isna().sum().sum()),'located_quality_issues':len(locate_quality_issues(df)),'outlier_action':'flag_only'}
            warnings=['IQR异常点仅标记，不自动删除。样本排除需要实验依据。']
        elif module in ('运动机制分析','运动关系分析'):
            track_source=read_table(primary)
            coords=normalized_landmarks(track_source,
                fmt=cfg.get('behavior_track_format','auto'),
                time_col=cfg.get('behavior_time_col','time_s'),
                point_col=cfg.get('behavior_point_col','point_id'),
                x_col=cfg.get('behavior_x_col','x_px'),
                y_col=cfg.get('behavior_y_col','y_px'),
                coord_unit=cfg.get('behavior_source_unit','px'),
                mm_per_pixel=float(cfg.get('mm_per_pixel','0.05')))
            save_csv(coords,out/'normalized_landmark_tracks.csv')
            results,extra=run_behavior(coords);warnings.extend(extra)
                                                                                   
            spatial_source=str(cfg.get('spatial_3d_track_file','')).strip()
            if spatial_source:
                from .spatial_relations102 import analyze_spatial_relations,parse_point_combinations
                pairs3,angles3=parse_point_combinations(cfg.get('spatial_3d_pairs',''),cfg.get('spatial_3d_triplets',''))
                pts3,pair3,ang3,summary3=analyze_spatial_relations(read_table(spatial_source),
                    reference=cfg.get('spatial_3d_reference','').strip(),pairs=pairs3 or None,triplets=angles3)
                save_csv(pts3,out/'spatial_3d_relative_points.csv')
                save_csv(pair3,out/'spatial_3d_pairs.csv')
                save_csv(ang3,out/'spatial_3d_angles.csv')
                save_csv(summary3,out/'spatial_3d_summary.csv')
                                                                                  
                fig,axes=plt.subplots(2,1,figsize=(8.4,6.1),sharex=True,layout='constrained')
                for (a,b),g in pair3.groupby(['point_a','point_b'],sort=False):
                    axes[0].plot(g.time_s,g.distance_3d_mm,label=f'{a}–{b}',lw=1.45)
                for (a,b,c),g in ang3.groupby(['point_a','vertex_point','point_c'],sort=False):
                    axes[1].plot(g.time_s,g.included_angle_deg,label=f'{a}–{b}–{c}',lw=1.45)
                axes[0].set(ylabel='空间点对距离（毫米）',title='有效标定三维点对（保留缺测）')
                axes[1].set(xlabel='时间（秒）',ylabel='三点空间夹角（度）')
                for ax in axes:
                    ax.grid(alpha=.15)
                    if ax.lines:ax.legend(loc='best',fontsize=7,ncol=2)
                publish_plot(fig,out/'FIGURE_spatial_3d_relations')
                results.update({'spatial_3d_relation_count':len(summary3),
                    'spatial_3d_valid_pairs':int(pair3.valid_pair.sum()) if len(pair3) else 0})
                warnings.append('三维关系使用具有 valid_3d 标记的标定空间点，不凭二维影像猜深度；空间夹角不是完整刚体姿态。')

            results['tracks_imported']=len(coords)
            results['external_camera_compatible']='long or wide tracking table, no camera brand required'
        elif module=='批量力学':
            batch,manifest,issues=load_force_folder(primary,
              cfg.get('condition_col','condition'),cfg.get('sample_col','sample_id'),
              time_col=cfg.get('time_col','time_s'),displacement_col=cfg.get('displacement_col','displacement_mm'),
              force_col=cfg.get('force_col','force_N'),normalize_units=True,
              time_unit=cfg.get('time_unit','s'),displacement_unit=cfg.get('displacement_unit','mm'),
              force_unit=cfg.get('force_unit','N'))
            save_csv(manifest,out/'import_manifest.csv')
            if issues:warnings+=issues
            if 'sample_origin' in manifest and (manifest.sample_origin=='filename_fallback').any():
                warnings.append('部分文件没有真实独立试样编号，暂用文件名：同一试样多文件可能被误计为多块试样；先核对 import_manifest.csv。')
            if 'condition_origin' in manifest and (manifest.condition_origin=='folder_name_fallback').any():
                warnings.append('部分文件没有条件分组列，暂用文件夹名；不同实验条件可能被混在同组，请人工核对。')
            sign={'positive':1,'negative':-1}[cfg.get('tension_sign','positive')]
            batch['force_N']=pd.to_numeric(batch.force_N,errors='raise')*sign
                                                                                               
            cycle=cfg.get('cycle_column','').strip() or 'source_filename'
            if cycle not in batch:raise ValueError('循环列不存在：'+cycle)
            def optional(name):
                v=str(cfg.get(name,'')).strip();return float(v) if v else None
            protocol=AdhesionProtocol(baseline_mode=cfg.get('force_baseline','first_fraction'),
              baseline_fraction=float(cfg.get('baseline_fraction',.05)),
              baseline_start_s=optional('baseline_start_s'),baseline_end_s=optional('baseline_end_s'),
              manual_baseline_N=optional('baseline_manual_N') or 0,
              pull_start_s=optional('pull_start_s'),pull_end_s=optional('pull_end_s'),
              cycle_column=cycle,area_mm2=optional('area_mm2'))
            metrics,traces,alerts=analyze_adhesion_protocol(batch,protocol)
            specimen,summary=specimen_force_summary(metrics)
            save_csv(metrics,out/'cycle_metrics.csv');save_csv(traces,out/'corrected_curves.csv')
            save_csv(specimen,out/'independent_specimens.csv');save_csv(summary,out/'group_summary.csv')
            publish_plot(force_storyboard(metrics,traces,FigureOptions.from_config(cfg)),out/'FIGURE_batch_mechanics')
            results={'imported_files':len(manifest[manifest.status=='OK']),
              'independent_specimens':len(specimen),'tested_cycles':len(metrics),
              'mean_peak_force_per_specimen_N':float(specimen.peak_force_N.mean()),
              'mean_work_per_specimen_mJ':float(specimen.separation_work_mJ.mean()),
              'note':'汇总先求每一独立试样的循环均值，再进行跨试样统计；源数据不改动。'}
            warnings+=alerts
        elif module=='力学分析':
            from .common import identify_column
            source_df=_table(cfg)
            inferred_group=not (cfg.get('col_condition','condition') in source_df or identify_column(source_df.columns,'condition'))
            inferred_sample=not (cfg.get('col_sample_id','sample_id') in source_df or identify_column(source_df.columns,'sample_id'))
            if inferred_group:source_df['condition']='未分组'
            if inferred_sample:source_df['sample_id']=Path(cfg['file']).stem
            df=_mapped(source_df,cfg,('condition','sample_id','time_s','displacement_mm','force_N'))
            fac={'N':1.,'mN':.001,'gf':.00980665,'kgf':9.80665,'uN':1e-6}
            if cfg['force_unit'] not in fac:raise ValueError('力单位不支持')
            from .common import infer_source_unit,UNIT_SCALE
                                                                                                  
            def column_source(key,canonical):
                selected=cfg.get(key,canonical)
                if selected in source_df.columns:return selected
                return identify_column(source_df.columns,canonical) or selected
            raw_header=column_source('col_force_N','force_N')
            df['force_N']=pd.to_numeric(df['force_N'],errors='raise')*UNIT_SCALE['force'][
                infer_source_unit(raw_header,'force',cfg['force_unit'])]
            df['time_s']=pd.to_numeric(df['time_s'],errors='raise')*UNIT_SCALE['time'][
                infer_source_unit(column_source('col_time_s','time_s'),'time',cfg.get('time_unit','s'))]
            df['displacement_mm']=pd.to_numeric(df['displacement_mm'],errors='raise')*UNIT_SCALE['displacement'][
                infer_source_unit(column_source('col_displacement_mm','displacement_mm'),'displacement',cfg.get('displacement_unit','mm'))]
            sign={'positive':1,'negative':-1}[cfg['tension_sign']]
            df['force_N']*=sign
            area=_num(cfg['area_mm2']);area=area if area>0 else None
            cfg_baseline=cfg.get('force_baseline','first_fraction')
            cycle_name=cfg.get('cycle_column','').strip()
            if cycle_name:
                raw=read_table(cfg['file'])
                if cycle_name not in raw:raise ValueError('循环编号列不存在：'+cycle_name)
                df['cycle_id']=raw[cycle_name].to_numpy()
            def nullable(key):
                v=str(cfg.get(key,'')).strip()
                return float(v) if v else None
            protocol=AdhesionProtocol(
                baseline_mode=cfg_baseline,
                baseline_fraction=float(cfg.get('baseline_fraction','0.05')),
                baseline_start_s=nullable('baseline_start_s'),baseline_end_s=nullable('baseline_end_s'),
                manual_baseline_N=nullable('baseline_manual_N') or 0.,
                pull_start_s=nullable('pull_start_s'),pull_end_s=nullable('pull_end_s'),
                cycle_column='cycle_id' if cycle_name else None,area_mm2=area)
            report,traces,alerts=analyze_adhesion_protocol(df,protocol)
            save_csv(report,out/'adhesion_metrics.csv')
            save_csv(traces,out/'force_trace_corrected.csv')
            publish_plot(force_figure(df),out/'force_curves')
                                                                                        
            publish_plot(single_force_storyboard(report,traces,FigureOptions.from_config(cfg)),out/'FIGURE_adhesion_multipanel')
            specimen,group_summary=specimen_force_summary(report)
            save_csv(specimen,out/'independent_specimens.csv');save_csv(group_summary,out/'group_summary.csv')
            results={'independent_specimens':len(specimen),'tested_cycles':len(report),
                     'mean_peak_force_N':float(specimen.peak_force_N.mean()),
                     'mean_separation_work_mJ':float(specimen.separation_work_mJ.mean()),
                     'summary_method':'先在试样内平均循环，再将每一独立试样等权汇总',
                     'baseline_policy':cfg_baseline}
            warnings=list(alerts)
            if inferred_sample:warnings.append('输入表没有样品编号，已暂用文件名作为一块独立样品；若文件包含多块样品，请重新标注样品编号。')
            if inferred_group:warnings.append('输入表没有实验组列，本次按未分组处理；不同条件的数据请补充真实分组信息。')
            warnings.append('工作积分仅统计明确拉离过程分析时间窗正向净拉力；力方向、零力时间窗与位移方向需现场核实。')
            if cycle_name:warnings.append('多次循环不等于独立生物样本；统计推断应先按独立试样汇总。')
        elif module=='视频追踪' and cfg.get('tracking_mode','contour')=='point_lk':
            if not cfg.get('seed_file'):raise ValueError('特征点模式需要人工标点 CSV。点击界面的「打开视频·精细标点」按钮，在原视频画面中直接标点。')
            prm=PointTrackConfig(mm_per_pixel=float(cfg['mm_per_pixel']),climb_axis=cfg.get('climb_axis','up'),
                step=int(cfg.get('step',1)),max_frames=int(cfg.get('max_processed_frames',3000)),
                window_px=int(cfg.get('lk_window_px',25)),pyramid_levels=int(cfg.get('lk_pyramid',3)),
                fb_limit_px=float(cfg.get('lk_fb_limit_px',1.5)),
                stationary_threshold_mm_s=float(cfg.get('stationary_threshold_mm_s',.15)),
                cancel_event=getattr(_RUN_CONTEXT,'cancel_event',None))
            roi=cfg.get('roi','').strip()
            if roi:prm.roi=tuple(int(x) for x in _names(roi))
            from .point_tracking import prepare_anchors
            seeds=read_table(cfg['seed_file'])
                                                                                          
            save_csv(seeds,out/'manual_point_anchors.csv')
            df,preview,meta=track_marked_points(primary,seeds,prm)
            save_csv(df,out/'frame_trajectory.csv')
            enhanced,review=annotate_motion(df,int(cfg.get('motion_smooth_window','11')),
                max_speed_mm_s=float(cfg.get('motion_max_speed_mm_s','0')),
                fb_warning_px=float(cfg.get('motion_fb_warning_px','1.0')))
            save_csv(enhanced,out/'point_motion_analysis.csv')
            save_csv(review,out/'motion_review_queue.csv')
            reference=cfg.get('motion_reference_point','').strip()
            relative=relative_motion(enhanced,reference) if reference else pd.DataFrame()
            if not relative.empty:save_csv(relative,out/'relative_motion.csv')
            pairs=multiple_pairs(enhanced,cfg.get('motion_pairs',''),cfg.get('pair_point_a',''),cfg.get('pair_point_b',''))
            if not pairs.empty:save_csv(pairs,out/'multiple_point_pairs.csv')
            cycle=screen_cycles(pairs,float(cfg.get('motion_max_frequency_hz','5')))
            if not cycle.empty:save_csv(cycle,out/'exploratory_periodicity.csv')
            tstart=cfg.get('motion_focus_start_s','').strip();tend=cfg.get('motion_focus_end_s','').strip()
            lo=float(tstart) if tstart else None;hi=float(tend) if tend else None
            if lo is not None and hi is not None and lo>=hi:raise ValueError('运动图聚焦终点必须大于起点。')
            publish_plot(plot_temporal_tracks(enhanced,preview,meta,prm.mm_per_pixel,lo,hi),out/'FIGURE_time_coded_multi_point')
            publish_plot(plot_motion_quality(enhanced,review,lo,hi),out/'FIGURE_speed_and_tracking_quality')
            publish_plot(plot_relative_motion(relative,pairs,cycle,lo,hi),out/'FIGURE_relative_motion')
            publish_plot(plot_cycle_screen(pairs,cycle,lo,hi),out/'FIGURE_periodicity_screen')
            try:
                if cfg.get('motion_export_overlay','yes')=='yes':
                    video_info=export_overlay_video(primary,enhanced,out/'review_overlay.mp4',int(cfg.get('motion_overlay_max_frames','0')))
                else:video_info={'review_video_status':'disabled'}
            except (ValueError,cv2.error) as ex:video_info={'review_video_status':f'视频预览导出失败：{ex}'}
            summary=point_summary(df);save_csv(summary,out/'point_summary.csv')
            geometry=pair_geometry(df,cfg.get('pair_point_a') or None,cfg.get('pair_point_b') or None)
            if not geometry.empty:save_csv(geometry,out/'point_pair_geometry.csv')
            from .point_figures import plot_points,plot_kinematics
            publish_plot(plot_points(df,preview,meta,prm.mm_per_pixel),out/'point_trajectories')
            publish_plot(plot_kinematics(df,geometry),out/'point_kinematics')
            if preview is not None:cv2.imwrite(str(out/'tracking_preview.png'),preview)
                                                                         
            main_point,inferred=select_primary(df,cfg.get('motion_primary_point','').strip())
            evidence,event_report=movement_evidence(
                enhanced,main_point,
                baseline_end_s=float(cfg.get('motion_baseline_end_s','5')),
                min_motion_px=float(cfg.get('motion_min_movement_px','3')),
                sustain_frames=int(cfg.get('motion_sustain_frames','5')))
            save_csv(evidence,out/'motion_primary_path.csv')
            manual_text=str(cfg.get('motion_manual_event_time_s','')).strip()
            manual_t=float(manual_text) if manual_text else None
            manual_label=str(cfg.get('motion_manual_event_name','')).strip()
            if manual_t is not None:
                if not np.isfinite(manual_t) or not 0<=manual_t<=float(df.time_s.max()):
                    raise ValueError('人工确认的事件时刻应在本次读取的视频时间范围内。')
                if not manual_label:raise ValueError('填写人工事件时间时，还需要填写事件名称，例如“肉眼确认离开平台”。')
            event_report['manual_event_time_s']=manual_t
            event_report['manual_event_name']=manual_label or '未标记'
            save_csv(pd.DataFrame([event_report]),out/'motion_event_summary.csv')
            calibrated=cfg.get('motion_scale_confirmed','no')=='yes'
                                                                            
                                                                     
            publish_plot(plot_experiment_story(enhanced,preview,evidence,event_report,
                 scale_verified=calibrated,scale=prm.mm_per_pixel,focus_start=lo,focus_end=hi,
                 manual_event_s=manual_t,manual_event_name=manual_label),
                 out/'FIGURE_motion_multipanel')
            (out/'先看这里_视频分析结果.txt').write_text(
                 write_guide(event_report,calibrated),encoding='utf-8-sig')
            results=dict(tracking_mode='人工特征点 + LK双向光流',**meta,
                point_detection_rates={r.point_id:round(float(r.detection_rate),4) for r in summary.itertuples(index=False)},
                mean_detection_rate=float(summary.detection_rate.mean()),
                physical_measurement='二维图像中用户标记特征点的投影运动',
                manual_markers_used=len(seeds),
                point_summary_rows=len(summary),motion_review_marks=len(review),
                named_point_pairs=len(pairs.pair_name.unique()) if not pairs.empty else 0,
                relative_reference=reference or '未指定',main_motion_point=main_point,
                projected_movement_candidate_s=event_report.get('movement_candidate_time_s'),
                projected_movement_status=event_report['status'],
                last_tracked_time_s=event_report.get('last_tracked_time_s'),
                untracked_tail_s=event_report.get('untracked_tail_s'),
                manual_event_time_s=manual_t,manual_event_name=manual_label or '未标记',
                real_scale_confirmed=calibrated,**video_info,
                note='每个点按原视频帧追踪；LK前后向检查失败即标记丢失，不补线、不把检测评分当准确率。')
            warnings=['光流追踪的是手工指定的可见图像特征；亚像素数值不等于已证实的亚像素物理精度。',
                '移动摄像机、画面失焦、遮挡、反光、变形以及透视变化会影响轨迹；应检查标点与原视频。',
                '速度取相邻有效采样帧的有限差分；两点角度是二维投影连线方向，不等于三维翅膀姿态。',
                '时间由视频报告的FPS推算；变帧率视频请用外部可靠时间戳复核。']
            if cfg.get('reference_file','').strip():
                reviewed,comparison=evaluate_point_reference(df,read_table(cfg['reference_file']),
                                                              seeds,prm.mm_per_pixel)
                if not comparison.empty:save_csv(comparison,out/'independent_point_validation.csv')
                results['independent_point_validation']=reviewed
                if reviewed.get('status')!='LABELED_SAMPLE_ONLY':
                    warnings.append('尚无独立于追踪锚点的人工精度核对帧；不能声称误差已验证。')
            if event_report.get('untracked_tail_s') is not None and event_report['untracked_tail_s']>1.0:
                warnings.append(f"主要点最后可靠位置在 {event_report['last_tracked_time_s']:.2f}s，末端约 {event_report['untracked_tail_s']:.2f}s 无有效追踪；这段的运动不能从当前轨迹推断，请补锚点或复核视频。")
            if not calibrated:warnings.append('毫米／毫米每秒未确认比例尺：请按像素结果判断，先使用标尺工具校准真实尺度。')
            if inferred:warnings.append('主要运动点是程序按名称自动选择的；请确认它是身体而不是翅尖，否则整体运动结论可能错误。')
            warnings.append('二维持续位移候选不是起飞时间；真实离台必须对照原视频或另作接触事件标注。')
            if not review.empty:warnings.append(f'已有 {len(review)} 条逐点记录建议人工核查；请查看 motion_review_queue.csv，不要只看平滑图。')
            if (summary.detection_rate<.85).any():warnings.append('有特征点检出率低于85%，请人工核对失跟踪段；不宜直接报告为完整路径。')
            if cfg.get('behavior_enable','no')=='yes':
                bstats,bwarn=add_optional_behavior(df);results.update(bstats);warnings.extend(bwarn)
            spatial,notes=reconstruct_3d_optional(df);results.update(spatial);warnings.extend(notes)
        elif module=='视频追踪':
            c=TrackConfig(mm_per_pixel=_num(cfg['mm_per_pixel']),mode=cfg['mode'],threshold=int(cfg['threshold']),
                 min_area_px=_num(cfg['min_area_px']),climb_axis=cfg['climb_axis'],step=int(cfg['step']),
                 segmentation=cfg.get('segmentation','fixed'),clahe=cfg.get('clahe','no')=='yes',
                 max_jump_px=_num(cfg.get('max_jump_px','0')),
                 min_confidence=_num(cfg.get('min_confidence','0')))
            roi=cfg.get('roi','').strip()
            if roi:c.roi=tuple(int(x) for x in _names(roi))
            df,preview=track_video(primary,c)
            save_csv(df,out/'frame_trajectory.csv')
            save_csv(make_review_sheet(df),out/'人工复核模板_请填x_y像素.csv')
                                                                                               
            df[['time_s','x_mm','y_up_mm','detected']].fillna('nan').assign(
                detected=lambda d:d.detected.astype(int)).to_csv(
                out/'trajectory_for_C.csv',index=False,encoding='utf-8-sig')
            if preview is not None:cv2.imwrite(str(out/'tracking_preview.png'),preview)
            publish_plot(track_figure(df),out/'trajectory')
            publish_plot(track_storyboard(df,preview,c.mm_per_pixel,FigureOptions.from_config(cfg)),out/'FIGURE_motion_multipanel')
            (out/'先看这里_视频分析结果.txt').write_text(
                '当前运行的是【旧版明暗轮廓中心】追踪，而不是人工多点LK追踪。\n'
                '首帧可能把平台或背景识别为目标。此四联图不宜未经逐帧核验用于科研。\n'
                '如果已经人工标记P1/P2，请回到视频追踪界面把跟踪方式改为【人工点锚定 LK 光流】，\n'
                '并确认人工标点CSV路径，重新运行；新结果保存在新建的运行文件夹。\n',encoding='utf-8-sig')
            results=motion_summary(df,c.climb_axis)
            if cfg.get('reference_file','').strip():
                checked,errors=evaluate_reference(df,read_table(cfg['reference_file']),c.mm_per_pixel)
                save_csv(errors,out/'manual_validation_errors.csv')
                results['manual_validation']=checked
            if cfg.get('reconstruction_3d','none')!='none':
                raise ValueError('旧版轮廓追踪没有可信的同名特征点，不能用于三维测量；请先选择人工LK多点模式。')
            warnings=['【旧版明暗轮廓追踪】可能跟到背景或平台；仅作为兼容模式。已做人工标点时请改用人工LK多点模式。','二维投影运动，非3D位移；遮挡和机器人形变会影响阈值识别。检查检出率和轨迹断裂。']
            if results['detection_rate']<.85:warnings.append('检出率低于85%；结果不宜直接用于发表。')
            if results.get('longest_detection_gap_frames',0)>3:warnings.append('追踪发生连续缺帧；需核查人工标注，对位移/速度解释保持谨慎。')
            if 'manual_validation' not in results or results['manual_validation'].get('status')=='NOT_LABELED':
                warnings.append('尚未通过人工标注真值验证；置信度不是实际准确率。')
        elif module=='轨迹人工修正':
            raw=read_table(cfg['file']);edits=read_table(cfg['corrections_file'])
            if 'point_id' in raw:
                corrected,audit=apply_point_corrections(raw,edits,float(cfg['mm_per_pixel']),cfg.get('climb_axis','up'))
                from .point_figures import plot_points,plot_kinematics
                save_csv(corrected,out/'trajectory_corrected.csv')
                save_csv(audit,out/'manual_changes_audit.csv')
                enhanced,review=annotate_motion(corrected,int(cfg.get('motion_smooth_window','11')),
                    max_speed_mm_s=float(cfg.get('motion_max_speed_mm_s','0')))
                save_csv(enhanced,out/'corrected_motion_analysis.csv');save_csv(review,out/'motion_review_queue.csv')
                main,inferred=select_primary(corrected,str(cfg.get('motion_primary_point','')).strip())
                evidence,motion_report=movement_evidence(enhanced,main,
                    baseline_end_s=float(cfg.get('motion_baseline_end_s','5')),
                    min_motion_px=float(cfg.get('motion_min_movement_px','3')),
                    sustain_frames=int(cfg.get('motion_sustain_frames','5')))
                video=str(cfg.get('video_file','')).strip()
                manual=str(cfg.get('motion_manual_event_time_s','')).strip()
                mt=float(manual) if manual else None
                label=str(cfg.get('motion_manual_event_name','')).strip()
                if mt is not None and (not np.isfinite(mt) or not 0<=mt<=float(corrected.time_s.max()) or not label):
                    raise ValueError('人工事件时刻必须位于有效视频时间内，并同时填写事件名称。')
                motion_report.update(manual_event_time_s=mt,manual_event_name=label or '未标记')
                save_csv(evidence,out/'motion_primary_path.csv')
                save_csv(pd.DataFrame([motion_report]),out/'motion_event_summary.csv')
                preview_frame=None
                if video and Path(video).is_file():
                    cap=cv2.VideoCapture(video)
                    try:
                        ok,frame=cap.read()
                        if ok:preview_frame=frame
                    finally:cap.release()
                calibrated=cfg.get('motion_scale_confirmed','no')=='yes'
                publish_plot(plot_experiment_story(enhanced,preview_frame,evidence,motion_report,
                    scale_verified=calibrated,scale=float(cfg['mm_per_pixel']),
                    manual_event_s=mt,manual_event_name=label),out/'FIGURE_motion_multipanel')
                (out/'先看这里_视频分析结果.txt').write_text(
                    '本次轨迹来自人工修正（只改指定点/指定帧，其余点仍为自动结果）。\n'+
                    write_guide(motion_report,calibrated),encoding='utf-8-sig')
                reference=cfg.get('motion_reference_point','').strip()
                relative=relative_motion(enhanced,reference) if reference else pd.DataFrame()
                if not relative.empty:save_csv(relative,out/'relative_motion.csv')
                pairs=multiple_pairs(enhanced,cfg.get('motion_pairs',''),cfg.get('pair_point_a',''),cfg.get('pair_point_b',''))
                if not pairs.empty:save_csv(pairs,out/'multiple_point_pairs.csv')
                cycle=screen_cycles(pairs,float(cfg.get('motion_max_frequency_hz','5')))
                if not cycle.empty:save_csv(cycle,out/'exploratory_periodicity.csv')
                publish_plot(plot_temporal_tracks(enhanced,None,{'video_width_px':int(raw.frame_width_px.iloc[0]),
                    'video_height_px':int(raw.frame_height_px.iloc[0])},float(cfg['mm_per_pixel'])),out/'FIGURE_time_coded_multi_point')
                publish_plot(plot_motion_quality(enhanced,review),out/'FIGURE_speed_and_tracking_quality')
                publish_plot(plot_relative_motion(relative,pairs,cycle),out/'FIGURE_relative_motion')
                publish_plot(plot_cycle_screen(pairs,cycle),out/'FIGURE_periodicity_screen')
                stats=point_summary(corrected);save_csv(stats,out/'point_summary.csv')
                geometry=pair_geometry(corrected,cfg.get('pair_point_a') or None,cfg.get('pair_point_b') or None)
                if not geometry.empty:save_csv(geometry,out/'point_pair_geometry.csv')
                publish_plot(plot_points(corrected,None,{'video_width_px':int(raw.frame_width_px.iloc[0]),
                         'video_height_px':int(raw.frame_height_px.iloc[0])},float(cfg['mm_per_pixel'])),out/'corrected_trajectory')
                publish_plot(plot_kinematics(corrected,geometry),out/'corrected_kinematics')
                results={'corrected_marks':len(audit),'point_count':len(stats),'track_rows':len(corrected),
                         'main_motion_point':main,'last_tracked_time_s':motion_report.get('last_tracked_time_s'),
                         'untracked_tail_s':motion_report.get('untracked_tail_s'),
                         'note':'逐帧人工坐标覆盖相应点、相应帧；其他帧保持原状。速度和角度从修正后的位置重新计算。'}
                if cfg.get('behavior_enable','no')=='yes':
                    bstats,bwarn=add_optional_behavior(corrected);results.update(bstats)
                    warnings_behavior86=bwarn
                else:warnings_behavior86=[]
                spatial,notes=reconstruct_3d_optional(corrected);results.update(spatial)
                warnings=['只修正真正人工核对过的帧：其他帧仍由自动追踪得到。',
                          '人工点击仅是坐标选择，实际空间精度仍受镜头标定、图像分辨率和实验设计约束。']+notes+warnings_behavior86
            else:
                                                                                     
                                                             
                if {'frame','point_id','x_px','y_px'}.issubset(edits.columns):
                    if len(set(edits.point_id))!=1:raise ValueError('旧单轮廓轨迹只能修正一个中心点。请使用多点追踪模式重建轨迹。')
                    edits=edits.rename(columns={'x_px':'人工_x_px','y_px':'人工_y_px'})
                corrected,audit=apply_track_corrections(raw,edits,float(cfg['mm_per_pixel']),cfg.get('climb_axis','up'))
                save_csv(corrected,out/'trajectory_corrected.csv')
                save_csv(audit,out/'manual_changes_audit.csv')
                publish_plot(track_figure(corrected),out/'corrected_trajectory')
                results={'manually_corrected_frames':len(audit),'all_frames':len(corrected),
                         'note':'单轮廓旧格式：修正后重新计算速度；缺测段不插值。'}
                warnings=['人工修正坐标必须由研究者独立确认；未标注位置仍是自动预测坐标。']
        elif module=='显微图像':
            images=[Path(primary)] if Path(primary).is_file() else sorted(p for p in Path(primary).iterdir() if p.suffix.lower() in ('.png','.jpg','.jpeg','.tif','.tiff','.bmp'))
            if not images:raise ValueError('文件夹内未找到图片。')
            rows=[];roi=cfg.get('roi','').strip();roi=tuple(int(x) for x in _names(roi)) if roi else None
            for i,path in enumerate(images):
                metrics,mask,overlay=analyze_native_image(path,_num(cfg['um_per_pixel']),cfg['mode'],
                       int(cfg['threshold']) if cfg['threshold'].strip() else None,roi)
                metrics['filename']=path.name;rows.append(metrics)
                cv2.imwrite(str(out/(f'overlay_{i+1:03d}.png')),overlay)
                if i==0:cv2.imwrite(str(out/'segmentation_mask.png'),mask)
            flat=[{k:v for k,v in row.items() if not isinstance(v,dict)} for row in rows]
            save_csv(pd.DataFrame(flat),out/'image_metrics.csv')
            results={'images_processed':len(images),'mean_area_mm2':float(pd.DataFrame(flat).area_mm2.mean()),
                     'first_image':images[0].name}
            warnings=['单通道图像报告原始强度；16位只对分割图做1%-99%显示归一化。批次之间需统一曝光/阈值和标尺。']
        elif module=='信号处理':
            df=_table(cfg);series,events,spectrum,meta=analyze_signal(df,cfg['time_col'],cfg['value_col'],
                            cfg['filter'],int(cfg['window']),_num(cfg['cutoff_hz']),_num(cfg['prominence']))
            save_csv(series,out/'filtered_signal.csv');save_csv(events,out/'detected_events.csv')
            save_csv(spectrum,out/'fft_spectrum.csv')
            publish_plot(_chart_xy(series.time_s,series.filtered_value,'时间（秒）','Signal (original unit)','Filtered signal'),out/'signal')
                                                                              
            from .scientific_extensions102 import validated_spectrogram
            spectral=validated_spectrogram(series)
            if spectral is not None:
                scalogram,(freq,times,power)=spectral
                save_csv(scalogram,out/'time_frequency_power_density.csv')
                fig,ax=plt.subplots(figsize=(8,4.3),layout='constrained')
                img=ax.pcolormesh(times,freq,10*np.log10(np.maximum(power,1e-20)),shading='auto',cmap='viridis')
                ax.set(xlabel='时间（秒）',ylabel='频率（赫兹）',title='时频探索图（等间隔采样）')
                fig.colorbar(img,ax=ax,label='功率谱密度（分贝，相对 1 单位²/赫兹）')
                publish_plot(fig,out/'FIGURE_time_frequency_spectrogram')
                warnings.append('新增时频图为信号能量随时间的分布，仅在采样间隔偏差不超过2%且数据量适中时生成；不能消除混叠。')
            else:
                warnings.append('时频图未生成：需至少64个近均匀采样点且记录数不能过大，基础滤波与FFT结果仍完整。')
            results=meta;warnings=list(meta.get('notes',[]))+warnings
        elif module=='多源同步':
            a=read_table(cfg['file']);b=read_table(cfg['file_b'])
            applied_shift=_num(cfg['shift_b_s'])
            if cfg.get('auto_shift','no')=='yes':
                suggestion,scanned=suggest_clock_offset(a,b,cfg['time_a'],cfg['value_a'],cfg['time_b'],cfg['value_b'],
                    _num(cfg.get('shift_search_s','2')),_num(cfg['step_s']))
                save_csv(scanned,out/'clock_shift_scan.csv')
                applied_shift=suggestion['suggested_shift_b_s']
                warnings.append('自动对齐建议：'+suggestion['warning'])
                results['automatic_sync_estimate']=suggestion
            aligned,report=synchronize_signals(a,b,cfg['time_a'],cfg['value_a'],cfg['time_b'],cfg['value_b'],
                applied_shift,_num(cfg['step_s']),_num(cfg['max_gap_s']))
            save_csv(aligned,out/'aligned_signals.csv')
            fig,ax=plt.subplots(figsize=(7,4.5),layout='constrained')
            ax.plot(aligned.time_s,aligned.signal_A,label='信号甲',alpha=.8)
            ax.plot(aligned.time_s,aligned.signal_B,label='信号乙',alpha=.8)
            ax.set(xlabel='对齐后时间（秒）',ylabel='原始信号单位',title='按指定时间偏移对齐的信号')
            ax.grid(alpha=.2);ax.legend();publish_plot(fig,out/'synchronized_signals')
            results.update(report);warnings.append(report['warning'])
        elif module=='独立样本统计':
            df=_mapped(_table(cfg),cfg,('condition','sample_id','value'))
            specimens=aggregate_specimens(df)
            descriptive=describe_groups(specimens)
            save_csv(specimens,out/'specimen_means.csv');save_csv(descriptive,out/'group_summary.csv')
            diag=statistical_diagnostics(specimens,int(cfg.get('bootstrap_seed',42)),int(cfg.get('bootstrap_rounds',3000)))
            save_csv(diag,out/'statistics_diagnostics.csv')
            publish_plot(groups_figure(specimens),out/'sample_level_graph')
            publish_plot(statistical_storyboard(specimens,options=FigureOptions.from_config(cfg)),out/'FIGURE_specimen_multipanel')
            results={'groups':len(descriptive),'total_independent_specimens':int(len(specimens)),'variance_diagnostic':variance_diagnostic(specimens),'bootstrap_method':'每组独立试样水平的百分位法置信区间'}
            if len(descriptive)==2:
                try:
                    results['welch_test']=welch_comparison(specimens)
                    results['effect_sizes']=welch_effect_sizes(specimens)
                except ValueError as exc:warnings.append(str(exc))
            else:warnings.append('仅两个独立组时自动进行Welch检验；多组需事先指定合适的统计模型。')
            warnings.append('sample_id应代表独立试样；同一试样的重复帧/重复测量仅先汇总，不当成独立n。')
            warnings.append('正态性检验和方差检验仅供诊断，不能凭 p>0.05 证明数据服从正态；重复测量/批次层级应改用适当模型。')
        elif module=='高级统计':
            method=cfg.get('stat_method','paired')
                                                                                  
                                                                                   
            if method!='uncertainty':
                df=read_table(cfg['file'])
                col=cfg['col_condition'];sample=cfg['col_sample_id'];val=cfg['col_value']
            if method=='paired':
                results=paired_comparison(df,col,sample,val,int(cfg.get('bootstrap_seed','42')))
            elif method=='multi':
                spec=prepare_independent(df,col,sample,val)
                save_csv(spec,out/'independent_specimens.csv')
                results=multiple_group_comparison(spec,col,val)
                from .scientific_extensions102 import independent_posthoc_holm
                posthoc=independent_posthoc_holm(spec,col,val)
                save_csv(posthoc,out/'posthoc_pairwise_holm.csv')
                results['exploratory_holm_pair_comparisons']=len(posthoc)
            elif method=='mixed':
                results=mixed_effects(df,col,sample,val,cfg['batch_col'])
            elif method=='uncertainty':
                components=[float(x.strip()) for x in cfg['uncertainties'].split(',') if x.strip()]
                results=measurement_uncertainty(float(cfg['measurement']),components)
            else:raise ValueError('不支持的统计方法')
            if method=='mixed':
                save_csv(pd.DataFrame(results['terms']),out/'mixed_model_coefficients.csv')
                                                                                             
            report_row={key:(json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list,tuple)) else value)
                        for key,value in results.items()}
            save_csv(pd.DataFrame([report_row]),out/'advanced_statistics_report.csv')
            warnings=['统计推断仍需结合事先规定的实验设计，尤其注意缺失数据机制、相关结构与小样本效应。']
        elif module=='曲线拟合':
            df=_table(cfg)
            result,values=fit_curve(df,cfg['x_col'],cfg['y_col'],cfg['model'],cfg['robust']=='yes')
            save_csv(values,out/'fit_predictions_residuals.csv')
            fig,ax=plt.subplots(figsize=(7,4.5),layout='constrained')
            ax.scatter(values.x,values.measured,s=13,alpha=.7,label='实测值')
            ordered=values.sort_values('x')
            ax.plot(ordered.x,ordered.predicted,lw=2,label='拟合曲线');ax.legend();ax.set(xlabel=cfg['x_col'],ylabel=cfg['y_col']);ax.grid(alpha=.2)
            publish_plot(fig,out/'fit_curve');results=result
            if cfg.get('fit_diagnostics','yes')=='yes':
                comparison,_=compare_models(df,cfg['x_col'],cfg['y_col'],robust=(cfg['robust']=='yes'))
                save_csv(comparison,out/'candidate_model_comparison.csv')
                try:
                    ci,notes=parameter_ci(df,cfg['x_col'],cfg['y_col'],cfg['model'],cfg['robust']=='yes')
                    save_csv(ci,out/'approx_parameter_ci.csv');results['parameter_ci_note']=notes['warning']
                except ValueError as e:warnings.append('未生成参数置信区间：'+str(e))
                warnings.append('AICc比较仅适合同一响应数据与相同噪声假设；非线性拟合区间为近似值。')
        elif module=='公式优化':
            results=optimize_equation(cfg['bounds'],cfg['expression'],cfg['goal'],cfg['algorithm'],
                      cfg.get('constraints',''),int(cfg['seed']),int(cfg['maxiter']))
            history=pd.DataFrame(results.get('iteration_history',[]))
            if not history.empty:
                save_csv(history,out/'优化过程.csv')
                fig,ax=plt.subplots(figsize=(7.0,4.2),layout='constrained')
                good=history.dropna(subset=['best_feasible_objective'])
                if not good.empty:
                    ax.plot(good['iteration'],good['best_feasible_objective'],lw=2.15,color='#176B83',label='截至当前的最佳可行目标值')
                    ax.scatter(good['iteration'].iloc[-1],good['best_feasible_objective'].iloc[-1],color='#D56B52',s=32,zorder=3)
                ax.set(xlabel='优化器迭代次数',ylabel='当前最佳可行目标值',title='优化搜索过程')
                ax.grid(alpha=.15);ax.spines[['top','right']].set_visible(False)
                publish_plot(fig,out/'优化过程')
            warnings=[results['warning'],'图中每个点对应一次求解器回调，而不是所有目标函数计算；过程曲线不能证明找到全局最优。']
        elif module=='实验数据优化':
            df=_table(cfg)
            pars=_names(cfg['parameters']);resp=_names(cfg['responses']);goals=_names(cfg['goals']);weights=list(map(float,_names(cfg['weights'])))
            optimizer=cfg.get('surrogate','GaussianProcess')
            engine=optimize_bayesian if optimizer=='GaussianProcess' else optimize_experiments
            group_col=cfg.get('group_col','').strip() or None
            options={'parameter_bounds':cfg.get('parameter_bounds','')}
            if optimizer=='GaussianProcess':options['n_candidates']=int(cfg.get('candidate_count') or 384)
            result,candidates=engine(df,pars,resp,goals,weights,group_col,int(cfg['seed']),cfg.get('constraints',''),**options)
            save_csv(candidates,out/'predicted_candidates.csv')
            if 'shortlist_rank' in candidates:
                save_csv(candidates.loc[candidates.shortlist_rank>0].sort_values('shortlist_rank'),out/'recommended_experiments_top5.csv')
            audit=pd.DataFrame(result['validation_metrics'])
            save_csv(audit,out/'model_validation.csv')
            if optimizer=='GaussianProcess':
                oof=gp_out_of_fold_table(df,pars,resp,group_col,int(cfg['seed']))
            else:
                oof=quadratic_out_of_fold_table(df,pars,resp,group_col)
                warnings.append('二次响应面只提供根据留组绝对误差构造的经验风险范围，没有概率区间覆盖保证。')
            save_csv(oof,out/'cv_predictions.csv')
                                                                                  
                                                                       
            if optimizer in ('GaussianProcess','Quadratic'):
                fig,ax=plt.subplots(1,len(resp),figsize=(max(6,4.4*len(resp)),4.3),layout='constrained',squeeze=False)
                for i,r in enumerate(resp):
                    obs=pd.to_numeric(oof[r]).to_numpy(float)
                    pred=pd.to_numeric(oof['cv_predicted_'+r]).to_numpy(float)
                    axis=ax[0,i]
                    axis.scatter(obs,pred,s=30,alpha=.78,color='#147D85',edgecolors='white',linewidth=.3)
                    low=float(min(np.min(obs),np.min(pred))); high=float(max(np.max(obs),np.max(pred)))
                    pad=(high-low)*.06 if high>low else 1.
                    axis.plot([low-pad,high+pad],[low-pad,high+pad],color='#B46556',lw=1.5,linestyle='--',label='预测与实测完全一致')
                    met=result['validation_metrics'][i]
                    axis.set(xlabel='实测：'+r,ylabel='留组预测：'+r,
                             title=f'留组验证：决定系数={met["cv_R2"]:.2f}, MAE={met["cv_MAE"]:.3g}')
                    axis.grid(alpha=.15);axis.spines[['right','top']].set_visible(False)
                publish_plot(fig,out/'FIGURE_out_of_fold_validation')
            if len(pars)==1:
                fig,ax=plt.subplots(figsize=(7,4.5),layout='constrained')
                ss=candidates.sort_values(pars[0])
                xx=ss[pars[0]]
                ax.plot(xx,ss['predicted_'+resp[0]],label='近似模型预测',color='#176B83')
                lower='ci95_low_'+resp[0] if 'ci95_low_'+resp[0] in ss else 'heuristic_low_'+resp[0]
                upper='ci95_high_'+resp[0] if 'ci95_high_'+resp[0] in ss else 'heuristic_high_'+resp[0]
                if lower in ss and upper in ss:
                    ax.fill_between(xx.to_numpy(float),ss[lower].to_numpy(float),ss[upper].to_numpy(float),alpha=.16,color='#176B83',label='经验误差范围（无覆盖保证）')
                ax.scatter(df[pars[0]],df[resp[0]],s=24,label='实测',color='#BC7656')
                if result.get('recommended_parameters'):
                    ax.scatter([result['recommended_parameters'][pars[0]]],[result['predicted_responses'][resp[0]]],
                               marker='*',s=140,label='待实验验证的建议点',color='#D56B52')
                ax.set(xlabel=pars[0],ylabel=resp[0]);ax.legend();ax.grid(alpha=.2)
                publish_plot(fig,out/'surrogate_curve')
            if len(resp)==2:
                fig,ax=plt.subplots(figsize=(7,4.5),layout='constrained')
                pareto=candidates[candidates.estimated_pareto]
                ax.scatter(candidates['predicted_'+resp[0]],candidates['predicted_'+resp[1]],s=10,alpha=.2,label='模型预测候选')
                ax.scatter(df[resp[0]],df[resp[1]],s=26,marker='x',color='#BC7656',label='真实实测点')
                ax.scatter(pareto['predicted_'+resp[0]],pareto['predicted_'+resp[1]],s=22,label='预测非支配候选（未实测验证）')
                ax.set(xlabel=resp[0],ylabel=resp[1]);ax.legend(fontsize=8)
                publish_plot(fig,out/'predicted_pareto')
            results=result;warnings+=list(result['warnings'])
            if result.get('status')=='LOW_MODEL_RELIABILITY':
                warnings.append('模型未通过基础留组验证，未发布正式参数建议。此结果只适合用于排查数据和改进实验设计。')
            if len(resp)>=2:
                warnings.append('预测 Pareto 只是候选点相互比较；所有预测数值与可行概率均需真实实验验证。')
        elif module=='论文绘图':
            df=_table(cfg)
            fig,report=make_chart(df,cfg)
            publish_plot(fig,out/'publication_figure')
            results=report
            warnings=report.get('warnings',[])
            save_json({'x_column':cfg.get('chart_x',''),'y_column':cfg.get('chart_y',''),
                'group_column':cfg.get('chart_group',''),'sample_id_column':cfg.get('chart_sample_id',''),
                'chart_type':cfg.get('chart_type','')},out/'figure_data_mapping.json')
        elif module in ('写作辅助','分析结果整理'):
            meta_path=Path(primary).expanduser()
            from ui_outputs102 import find_output_file
            if meta_path.is_dir():meta_path=find_output_file(meta_path,'run_metadata.json')
            elif meta_path.name=='result_summary.json':
                source_folder=meta_path.parent.parent if meta_path.parent.name in ('核心结果','质量检查','运行记录') else meta_path.parent
                meta_path=find_output_file(source_folder,'run_metadata.json')
            if meta_path.name!='run_metadata.json':raise ValueError('请选择分析结果文件夹、run_metadata.json 或 result_summary.json')
            if not meta_path.is_file():raise FileNotFoundError('未找到运行记录：'+str(meta_path)+'。请先运行一个分析模块，再选择该次生成的结果文件夹。')
            meta=json.loads(meta_path.read_text(encoding='utf-8'))
            source_folder=meta_path.parent.parent if meta_path.parent.name in ('核心结果','质量检查','运行记录') else meta_path.parent
            results_path=find_output_file(source_folder,'result_summary.json')
            r=json.loads(results_path.read_text(encoding='utf-8')) if results_path.exists() else {}
            drafted=generate_draft(meta,r,cfg['language'])
            (out/'manuscript_draft.md').write_text(drafted,encoding='utf-8')
            export_docx(drafted,out/'manuscript_draft.docx')
            results={'source_run':str(source_folder),'draft_character_count':len(drafted),
                     'files':['manuscript_draft.md','manuscript_draft.docx']}
            warnings=['不自动生成论文引用、p值、机理结论；写作前检查实验记录、材料方法与纳排标准。']
        else:raise ValueError(f'未知模块：{module}')
        _runtime_check('各项科学计算完成，准备保存结果摘要')
        if warnings:results['quality_warnings']=warnings
                                                                               
                                                                                         
        try:
            from .research_insights102 import generate_insights
            insight=generate_insights(out,module)
            if len(insight):
                save_csv(insight,out/'研究增强指标_V10.2.csv')
                results['additional_scientific_indicators']=len(insight)
        except (OSError,ValueError,KeyError,TypeError,ImportError) as exc:
            warnings.append('附加描述性指标未生成；原始分析结果不受影响：'+str(exc))
            results['quality_warnings']=warnings
        try:
            from ui_outputs102 import write_index
            write_index(out,module)
        except (OSError,ValueError,KeyError,ImportError) as exc:
            warnings.append('文件分级导航未生成：'+str(exc))
            results['quality_warnings']=warnings
                                                                                      
                                                             
        try:
            from ui_result_guide101 import write_run_reader
            write_run_reader(out,module,cfg,results)
        except (OSError,ValueError,KeyError,UnicodeError,ImportError) as expl:
            warnings.append('结果阅读指南未生成；原始计算文件仍保留：'+str(expl))
            results['quality_warnings']=warnings
                                                                                    
                                                                            
        from ui_explanations_v6 import write_column_dictionary
        write_column_dictionary(out,module)
                                                                                               
        try:
            workbook=export_result_workbook(out)
            if workbook:results['excel_summary_file']=workbook.name
        except (OSError,ValueError,ImportError) as exc:
            warnings.append('Excel 汇总簿生成失败（CSV仍完整）：'+str(exc))
            results['quality_warnings']=warnings
        _runtime_check('完成后检查与整理文件')
        save_json(results,out/'result_summary.json')
        (out/'READ_ME_FIRST.txt').write_text(
            'Research Toolbox｜结果文件速查\n\n'
            '阅读顺序：先看主要指标表和相应图片，再检查质量标记与参数记录。\n'
            '阅读结果_从这里开始.txt：本次文件清单、各文件用途和必要核对项。\n'
            'analysis_tables.xlsx：将已生成的表格放在同一工作簿中，便于查阅。\n'
            'CSV：实际计算表；JSON：完整摘要、运行参数和机器可读记录。\n'
            '请核对物理单位、实验分段和独立试样身份；数据质检不会删除原始行。\n',
            encoding='utf-8-sig')
        output_files=[p for p in out.iterdir() if p.is_file()]
        guide=files_guide(module,output_files)
        if module=='数据质检':
            guide+='\n【质检表的表头翻译】\n'
            for key,meaning in QC_COLUMNS.items():guide+='\n'+key+'：'+meaning+'\n'
            guide+='\n【本次最重要的数字】\n'
            guide+=f'共 {results.get("rows",0)} 行，{results.get("columns",0)} 列。'
            guide+=f'整行重复 {results.get("exact_duplicate_rows",0)} 行。'
            guide+=f'整表空白单元格 {results.get("total_missing_cells",0)} 个。\n'
            guide+='注意：column_quality.csv 中的 duplicates_in_column 指的是单列重复值，不能和“整行重复”混为一谈。\n'
            guide+='注意：iqr_outlier_flags 是分布规则标出的“值得检查的数”，并不是确认有错的数据。\n'
        (out/'阅读结果_从这里开始.txt').write_text(guide,encoding='utf-8-sig')
                                                                                   
                                                                         
        try:
            from ui_outputs102 import write_index,build_reading_folders
            write_index(out,module)
            build_reading_folders(out,module)
        except (OSError,ValueError,KeyError,ImportError) as exc:
            (out/'OUTPUT_VIEW_WARNING.txt').write_text('结果分类阅读目录生成失败；原始计算文件仍完整保留：'+str(exc),encoding='utf-8')
        return out,results
    except Exception:
        (out/'INCOMPLETE_RUN.txt').write_text('计算未完成；请检查错误消息。本目录结果不可用于论文。',encoding='utf-8')
        raise
