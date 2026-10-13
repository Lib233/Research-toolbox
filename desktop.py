"""Research Toolbox: offline, native Windows-friendly Tk desktop UI.
Entry point uses stdlib GUI; numerical processing is separated in core/workflows.py.
"""
from __future__ import annotations
import json, os, sys, threading, traceback, subprocess, shutil, queue, time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont
from ui_guidance import MODULE_HELP, F, OPTIONS, QC_COLUMNS, field_help, field_text, option_help, module_text, files_guide, describe_file, result_help
from ui_explanations_v6 import RESULT_NAMES, column_detail, MODULE_STORIES, humanize_result_value, summary_field_detail
from ui_video81 import VIDEO_STORIES, VIDEO_FIELD_HELP
from ui_spatial89 import OrbitalNavigation, ModulePalette, MODULES
from ui_help_v10 import help_text as v10_help
from ui_copy104 import MODULE_STORIES_104, RESULT_VALUE_NAMES_104, display_name

BASE=Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
                                                                                                        
APP_DIR=(Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent)
OUT=APP_DIR/'分析结果'
                                                                       
SPECS={
'数据质检':dict(sub='看清数据，再开始分析 | 不擅自删除异常值',input='表格文件',output='column_quality.csv · data_preview_first50.csv',fields=[
 ('file','输入表格（CSV / Excel / TSV）','file','')]),
'力学分析':dict(sub='拉离峰值拉伸力与正向力—位移积分｜按试样汇总',input='表格',output='adhesion_metrics.csv · force_curves.png/svg',fields=[
 ('file','力学数据','file',''),('col_condition','实验组列','column','condition'),('col_sample_id','独立试样列','column','sample_id'),('col_time_s','时间列','column','time_s'),('time_unit','时间单位（表头无单位时使用）','choice:s|ms','s'),('col_displacement_mm','位移列','column','displacement_mm'),('displacement_unit','位移单位（表头无单位时使用）','choice:mm|um|m','mm'),('col_force_N','原始力列','column','force_N'),('force_unit','力的单位（表头没写单位时使用）','choice:N|mN|uN|gf|kgf','N'),('tension_sign','拉伸力读数正负方向','choice:positive|negative','positive'), ('area_mm2','接触面积 (mm²)，未知写 0','text','0'),
 ('force_baseline','力传感器零点校正方法','choice:first_fraction|time_window|manual|zero','first_fraction'),
 ('baseline_fraction','初段基线比例 (0–0.5)','text','0.05'),
 ('baseline_start_s','基线时间窗起点 s（可留空）','text',''),
 ('baseline_end_s','基线时间窗终点 s（可留空）','text',''),
 ('baseline_manual_N','手动基线 N（可留空）','text',''),
 ('pull_start_s','分析时间窗起点（秒，可留空）','text',''),
 ('pull_end_s','分析时间窗终点（秒，可留空）','text',''),
 ('cycle_column','循环编号列（可留空）','column','')]),
'视频追踪':dict(sub='在视频上手工定义多个物理特征点，以 LK 光流逐帧跟踪并计算各点二维轨迹、速度和两点相对角度',input='AVI/MP4 视频',output='frame_trajectory.csv · trajectory.png/svg · tracking_preview.png',fields=[
 ('file','机器人运动视频','video',''),
 ('tracking_mode','跟踪方式','choice:point_lk|contour','point_lk'),
 ('seed_file','人工选点/重置锚点 CSV','file',''),
 ('pair_point_a','两点几何计算的起点名（可留空）','text',''),
 ('pair_point_b','两点几何计算的终点名（可留空）','text',''),
 ('lk_window_px','光流追踪窗口（奇数像素 5–101）','text','25'),
 ('lk_pyramid','光流金字塔层数','text','3'),
 ('lk_fb_limit_px','前后向偏差上限（像素）','text','1.5'),
 ('stationary_threshold_mm_s','投影近似不动速度阈值（mm/s）','text','0.15'),
 ('max_processed_frames','最多处理多少帧','text','3000'),
 ('mm_per_pixel','标定 mm/pixel','text','0.05'),('mode','目标颜色','choice:dark|bright','dark'),('threshold','灰度阈值 0～255','text','105'),('min_area_px','最小目标面积 (px²)','text','60'),('climb_axis','运动正方向','choice:up|down|left|right','up'),('step','每隔多少帧取 1 帧','text','1'),('roi','ROI 左,上,右,下（可留空）','text',''),
 ('segmentation','分割方法','choice:fixed|otsu|adaptive','otsu'),
 ('clahe','局部对比度增强 CLAHE','choice:no|yes','no'),
 ('max_jump_px','最大合理跳变像素（0 表示不限）','text','40'),
 ('min_confidence','最低目标置信阈值 (0–1)','text','0'),
 ('reference_file','人工标注核验 CSV（可留空）','file',''),
 ('motion_reference_point','相对运动参考点名称（可留空）','text',''),
 ('motion_primary_point','主要整体运动点名（例如 body，需与标注一致）','text',''),
 ('motion_baseline_end_s','初始位置参考阶段结束时间（秒）','text','5'),
 ('motion_min_movement_px','持续移动初筛的最小位移（像素）','text','3'),
 ('motion_sustain_frames','持续移动初筛至少连续多少采样点','text','5'),
 ('motion_manual_event_time_s','从原视频人工确认的事件时刻（秒，可留空）','text',''),
 ('motion_manual_event_name','该时刻的实验事件名称（可留空）','text',''),
 ('motion_scale_confirmed','毫米/像素标尺是否已实际核实','choice:no|yes','no'),
 ('motion_pairs','要比较的多个点对（每行 A,B；可留空）','multi',''),
 ('motion_smooth_window','趋势线窗口（0关闭；奇数≥5）','text','11'),
 ('motion_max_speed_mm_s','超过此速度提示复核（0关闭）','text','0'),
 ('motion_fb_warning_px','光流前后向偏差接近提示值（px）','text','1.0'),
 ('motion_max_frequency_hz','待检查的最高周期频率（Hz）','text','5'),
 ('motion_focus_start_s','科研图聚焦开始时间（可留空）','text',''),
 ('motion_focus_end_s','科研图聚焦结束时间（可留空）','text',''),
 ('motion_export_overlay','导出视频叠加复核文件','choice:yes|no','yes'),
 ('motion_overlay_max_frames','复核视频最多输出的帧数（0表示全部）','text','0')]),
'显微图像':dict(sub='8/16 位原图、分割面积、背景校正信号 | 可批量',input='图片或图片文件夹',output='image_metrics.csv · segmentation_mask.png · overlay_*.png',fields=[
 ('file','单张图 / 图像文件夹','image_or_folder',''),('um_per_pixel','标定 µm/pixel','text','2'),('mode','要识别的区域','choice:bright|dark','bright'),('threshold','阈值 0～255，留空用 Otsu','text',''),('roi','ROI 左,上,右,下（可留空）','text','')]),
'信号处理':dict(sub='平滑、低通、峰值事件、频谱 | 检查采样间隔',input='时间序列表格',output='filtered_signal.csv · detected_events.csv · fft_spectrum.csv · signal.png/svg',fields=[
 ('file','传感器数据','file',''),('time_col','时间列（秒）','column','time_s'),('value_col','信号列','column','value'),('filter','滤波方式','choice:savgol|lowpass|none','savgol'),('window','Savitzky-Golay窗口（奇数）','text','11'),('cutoff_hz','低通截止 Hz','text','2.0'),('prominence','峰值突出度','text','0.1')]),
'多源同步':dict(sub='把两台设备同一时刻的读数排在一行，以便判断事件谁先发生、先后相差多久',input='两个带时间列的表格',output='aligned_signals.csv · synchronized_signals.png/svg',fields=[
 ('file','A 数据表（参考时钟）','file',''),('time_a','A 时间列（秒）','column','time_s'),('value_a','A 指标列','column','value'),('file_b','B 数据表（待校时）','file',''),('time_b','B 时间列（秒）','text','time_s'),('value_b','B 指标列','text','value'),('shift_b_s','B 时钟平移（秒）','text','0'),('step_s','重采样间隔（秒）','text','0.1'),('max_gap_s','最大允许插值间隔（秒）','text','0.5')]),
'独立样本统计':dict(sub='先合并同一件样品的多次测量，再比较不同组样品的结果',input='每行含分组/试样ID/观测值的表格',output='specimen_means.csv · group_summary.csv · sample_level_graph.png/svg',fields=[
 ('file','统计数据','file',''),('col_condition','组别列','column','condition'),('col_sample_id','独立试样 ID 列','column','sample_id'),('col_value','测量值列','column','value')]),
'曲线拟合':dict(sub='稳健最小二乘 | 同时给出参数、RMSE、R² 和残差',input='X/Y 两列的表格',output='fit_predictions_residuals.csv · fit_curve.png/svg',fields=[
 ('file','拟合数据','file',''),('x_col','自变量 X 列','column','x'),('y_col','响应 Y 列','column','y'),('model','拟合模型','choice:linear|quadratic|exponential|saturation','linear'),('robust','抗异常值稳健拟合','choice:yes|no','yes')]),
'公式优化':dict(sub='给定公式及限制条件，寻找更好参数，并显示每轮改进曲线',input='参数范围与数学表达式（不需要数据文件）',output='result_summary.json · 优化过程.csv · 优化过程.png/svg',fields=[
 ('bounds','参数名,下界,上界（每行一个）','multi','x,0,5\ny,0,5'),('expression','目标函数（支持 sin、cos、sqrt、log、where 分段）','multi','(x-2)**2+(y-3)**2'),('goal','优化方向','choice:min|max','min'),('algorithm','算法','choice:DE|SLSQP|DualAnnealing','DE'),('constraints','不等式约束（每行一个）','multi','x+y<=6'),('seed','随机种子','text','42'),('maxiter','最大迭代次数','text','200')]),
'实验数据优化':dict(sub='用真实历史实验训练预测模型，先验证是否可靠，再筛选下一轮可验证的候选参数',input='高斯过程至少15行；二次响应面至少12行，均需足够不同的参数设计',output='predicted_candidates.csv · predicted_pareto.png/svg · result_summary.json',fields=[
 ('file','设计-响应实验表','file',''),('surrogate','代理模型','choice:GaussianProcess|Quadratic','GaussianProcess'),('parameters','输入参数列（逗号分隔；GP最多5个）','text','frequency_hz,preload_N'),('responses','响应指标列（逗号分隔；GP最多3个）','text','speed_mm_s,adhesion_N'),('goals','各指标目标方向（对应顺序）','text','max,max'),('weights','权重（对应顺序）','text','0.5,0.5'),('group_col','独立实验 ID 列（强烈建议填写）','column','experiment_id'),('parameter_bounds','设备允许的参数范围（可留空；每行：列名,最小,最大）','multi',''),('constraints','预测响应约束（可留空）','multi','adhesion_N>=0.2'),('candidate_count','GP搜索候选数（32～3000）','text','384'),('seed','随机种子','text','42')]),
'分析结果整理':dict(sub='依据真实运行记录，生成可编辑方法描述与图注草稿',input='结果文件夹中的 run_metadata.json',output='manuscript_draft.md · manuscript_draft.docx',fields=[
 ('file','已完成任务中的 run_metadata.json','metadata',''),('language','写作语言','choice:zh|en','zh')]),
}

                                                                                        
SPECS['批量力学']=dict(sub='文件夹批量处理 · 显式基线与拉离过程分析时间窗 · 按独立试样汇总',input='放有多个 CSV / Excel 的文件夹',output='import_manifest.csv · cycle_metrics.csv · independent_specimens.csv · group_summary.csv',fields=[
 ('file','力学表格文件夹','folder',''),
 ('time_col','时间列（可自动匹配常见列名）','text','time_s'),('time_unit','时间单位（表头无单位时使用）','choice:s|ms','s'),('displacement_col','位移列','text','displacement_mm'),('displacement_unit','位移单位（表头无单位时使用）','choice:mm|um|m','mm'),
 ('force_col','原始力列','text','force_N'),('condition_col','条件分组列（缺少时使用文件夹名）','text','condition'),
 ('sample_col','独立试样编号列（缺少时使用文件名）','text','sample_id'),('force_unit','力的单位（表头没写单位时使用）','choice:N|mN|uN|gf|kgf','N'),
 ('tension_sign','拉伸力读数正负方向','choice:positive|negative','positive'),('area_mm2','名义面积 mm²（可留空）','text',''),
 ('force_baseline','力传感器零点校正方法','choice:first_fraction|time_window|manual|zero','first_fraction'),
 ('baseline_fraction','起始基线占比','text','0.05'),('baseline_start_s','基线时间起点 s（可留空）','text',''),
 ('baseline_end_s','基线时间终点 s（可留空）','text',''),('baseline_manual_N','手动基线 N（可留空）','text',''),
 ('pull_start_s','分析时间窗起点（秒，可留空）','text',''),('pull_end_s','分析时间窗终点（秒，可留空）','text',''),
 ('cycle_column','循环编号列（留空时按文件分）','text','')])
SPECS['高级统计']=dict(sub='配对分析、多组比较、批次与试样混合效应、不确定度合成',input='含试样编号与测量值的表格',output='统计结果及分析记录',fields=[
 ('file','统计数据','file',''),('stat_method','统计分析方法','choice:paired|multi|mixed|uncertainty','paired'),
 ('col_condition','条件/组别列','column','condition'),('col_sample_id','独立试样编号列','column','sample_id'),
 ('col_value','测量结果列','column','value'),('batch_col','批次列（混合效应必需）','column','batch'),
 ('measurement','测量值（仅不确定度合成）','text','10.0'),
 ('uncertainties','独立标准不确定度（逗号分隔）','text','0.2,0.1'),
 ('bootstrap_seed','Bootstrap 随机种子','text','42')])
SPECS['轨迹人工修正']=dict(sub='对照视频逐帧点击或键入坐标，修正某个特征点的位置，重新计算相邻速度和角度并保留审计记录',input='frame_trajectory.csv + 已填写人工坐标的 CSV',output='trajectory_corrected.csv · manual_changes_audit.csv',fields=[
 ('file','原始轨迹 CSV','file',''),('video_file','原始视频（供画面点选）','video',''),('corrections_file','人工坐标校正表 CSV','file',''),
 ('pair_point_a','两点几何计算的起点名（可留空）','text',''),('pair_point_b','两点几何计算的终点名（可留空）','text',''),
 ('mm_per_pixel','实际标定 mm/pixel','text','0.05'),('climb_axis','运动正方向','choice:up|down|left|right','up'),
 ('motion_reference_point','修正后相对参考点（可留空）','text',''),
 ('motion_primary_point','修正后的主要整体运动点（需与点名一致）','text',''),
 ('motion_baseline_end_s','初始位置参考结束时间（秒）','text','5'),
 ('motion_min_movement_px','持续移动初筛最小距离（像素）','text','3'),
 ('motion_sustain_frames','持续移动初筛连续点数','text','5'),
 ('motion_manual_event_time_s','原视频人工确认事件时刻（秒，可留空）','text',''),
 ('motion_manual_event_name','人工事件名称（可留空）','text',''),
 ('motion_scale_confirmed','毫米/像素标尺是否已核实','choice:no|yes','no'),
 ('motion_pairs','修正后多个点对（A,B;C,D）','multi',''),
 ('motion_smooth_window','趋势线窗口（0关闭；奇数≥5）','text','11'),
 ('motion_max_speed_mm_s','异常速度核查阈值（0关闭）','text','0'),
 ('motion_max_frequency_hz','周期初筛最高频率 Hz','text','5')])
                                                                                                                             
THREE_D_FIELDS=[
 ('enable_3d','启用三维分析（默认不勾选；二维不用任何三维文件）','checkbox','no'),
 ('reconstruction_3d','真实三维分析条件','choice:none|stereo|rigid_pnp','none'),
 ('stereo_calibration_file','三维相机标定 JSON（双目/PnP 用）','file',''),
 ('stereo_right_track_file','右相机独立追踪 CSV（双目模式必填）','file',''),
 ('stereo_time_offset_s','右相机时钟修正量（秒；已实测）','text','0'),
 ('stereo_match_tolerance_s','双相机时间匹配最大误差（秒）','text','0.012'),
 ('stereo_max_reprojection_px','最大单相机重投影误差（px）','text','2'),
 ('stereo_min_ray_angle_deg','最小视线夹角（°）','text','0.5'),
 ('rigid_geometry_file','已知刚体三维点坐标 CSV（PnP 模式）','file',''),
]
THREE_D_KEYS={f[0] for f in THREE_D_FIELDS if f[0]!='enable_3d'}
for _m in ('视频追踪','轨迹人工修正'):
 SPECS[_m]['fields'].extend(THREE_D_FIELDS)

                                                                                    
V10_LABELS = {'pipeline_kind': '选择项目类型（直接在下拉框选择）', 'pipeline_integrated_response': '联合指标主图想突出哪一列（可留空）', 'pipeline_integrated_reference': '视频相对运动的参考点名（可留空）', 'pipeline_integrated_targets': '视频中希望分析的点名（可多选，逗号隔开）', 'pipeline_integrated_max_frames': '单个视频最多读取多少帧', 'pipeline_integrated_design': '历史实验中可主动调节的参数列名（仅优化）', 'pipeline_integrated_opt_confirm': '已确认历史参数、物理范围与独立实验设计？（仅优化）', 'pipeline_integrated_image_confirm': '已核实显微图像的像素标定和分割依据？（仅图像）', 'pipeline_integrated_um_per_pixel': '显微图像标尺：每像素对应微米数（仅图像）', 'pipeline_integrated_image_mode': '显微图像的目标亮暗（仅图像）', 'pipeline_integrated_signal_time': '外部传感器 CSV 中的时间列表头（仅同步）', 'pipeline_integrated_signal_value': '外部传感器 CSV 中的测量列表头（仅同步）', 'pipeline_integrated_signal_shift': '传感器时间相对视频的已知偏移秒数（仅同步）', 'pipeline_confirm_id': '已核实独立试样编号（仅推断统计/专项力学）', 'pipeline_protocol_confirm': '已核实拉离实验规程（仅专项力学）', 'pipeline_integrated_sync': '已核对相机和传感器的真实时间关系？（仅同步）', 'pipeline_table_x': '横轴列名（填写表头）', 'pipeline_table_y': '要画出的测量结果列名（填写表头）', 'pipeline_integrated_stats': '联合指标是否进行独立试样统计（可选）', 'pipeline_integrated_opt': '是否推荐下一组待测实验参数（可选）', 'behavior_body': '用哪个点作为相对运动参考（点名，可留空）', 'behavior_feet': '要分析哪些特征点（留空=全部；逗号隔开）', 'behavior_substrate': '固定画面参考标记名称（可留空）', 'behavior_force_file': '需要与运动对照的外部传感器 CSV（可留空）', 'behavior_force_time_col': '外部传感器 CSV 的时间列表头', 'behavior_force_value_col': '外部传感器 CSV 的测量列表头', 'behavior_force_shift_s': '外部传感器时钟偏移（秒；需同步依据）', 'behavior_force_max_gap_s': '外部传感器可插值的最大时间缺口（秒）', 'behavior_speed_threshold_px_s': '判作低速候选的最大速度（像素/秒）', 'behavior_min_dwell_s': '低速候选最短持续时间（秒）', 'climb_axis': '运动正方向', 'mm_per_pixel': '视频每像素对应多少毫米（没有标定请勿将默认值当实测）', 'roi': '只分析图中的一个矩形区域 ROI（可留空）', 'prominence': '峰值突出度（相对周围谷底的高度）', 'measurement': '要报告不确定度的测量结果（只在不确定度模式）', 'uncertainties': '各来源的标准不确定度（用逗号分隔，非误差上限）',  'group_col': '独立实验编号所在列的表头（防止重复实验泄漏）', 'parameters': '实验前主动设置的参数列名（多个逗号隔开）', 'responses': '实验后真实测得的性能列名（多个逗号隔开）', 'motion_reference_point': '相对运动用哪个点作参考（名称，可留空）', 'motion_primary_point': '代表整体运动的特征点名（请核实真实位置）', 'max_processed_frames': '本次最多分析原视频多少帧', 'stereo_calibration_file': '相机标定向导生成的 JSON（仅真实三维）', 'stereo_right_track_file': '另一台相机的对应点轨迹 CSV（仅双目）', 'stereo_time_offset_s': '右相机时间需要校正多少秒（仅双目）', 'stereo_match_tolerance_s': '左右两相机允许相差多少秒才配对', 'stereo_max_reprojection_px': '反投影回相机允许的最大像素差', 'stereo_min_ray_angle_deg': '双摄像机视线至少相交多少度', 'rigid_geometry_file': '刚性机构已知三维标记点 CSV（仅 PnP）', 'motion_manual_event_time_s': '已人工核验的事件发生时刻（可留空）', 'motion_manual_event_name': '上述事件的名称（可留空）', 'behavior_track_format': '输入的坐标表是一点一行还是一时刻一行', 'behavior_enable': '是否增加可选的多点关系与运动阶段分析'}
V10_CONTEXT_LABELS = {('视频追踪', 'file'): '原始视频文件（MP4/AVI/MOV）', ('轨迹人工修正', 'file'): '视频追踪生成的坐标轨迹 CSV', ('运动关系分析', 'file'): '已经追踪好的坐标 CSV/Excel（不是视频）', ('实验数据优化', 'file'): '历史实验记录表（可调参数 + 实测结果）', ('项目工作流', 'file'): '本项目的实验清单或所选快捷数据文件', ('高级统计', 'file'): '实验结果表（不确定度模式按界面要求）'}
                                                                                      
V10_CORE = {
 '项目工作流':{'pipeline_kind','file'},
 '视频追踪':{'file','tracking_mode','seed_file','motion_primary_point','max_processed_frames','mm_per_pixel','motion_scale_confirmed'},
 '轨迹人工修正':{'file','video_file','corrections_file','mm_per_pixel'},
 '运动关系分析':{'file','behavior_track_format','behavior_source_unit','behavior_body','behavior_feet'},
 '高级统计':{'file','stat_method','col_condition','col_sample_id','col_value','measurement','uncertainties'},
 '显微图像':{'file','um_per_pixel','mode'},
 '信号处理':{'file','time_col','value_col','filter'},
 '实验数据优化':{'file','surrogate','parameters','responses','goals'},
 '多源同步':{'file','file_b','time_a','time_b','value_a','value_b'},
 '曲线拟合':{'file','x_col','y_col','model'},
 '批量力学':{'file','time_col','displacement_col','force_col','tension_sign','force_baseline'},
 '力学分析':{'file','col_time_s','col_displacement_mm','col_force_N','tension_sign','force_baseline'},
}
V10_GROUPS = {
 '视频追踪':{
  '光流与质量检查':{'lk_window_px','lk_pyramid','lk_fb_limit_px','reference_file','motion_fb_warning_px','max_jump_px','min_confidence'},
  '运动几何与事件（可选）':{'pair_point_a','pair_point_b','motion_reference_point','motion_baseline_end_s','motion_min_movement_px','motion_sustain_frames','motion_manual_event_time_s','motion_manual_event_name','motion_pairs','motion_smooth_window','motion_max_speed_mm_s','motion_max_frequency_hz','motion_focus_start_s','motion_focus_end_s','motion_export_overlay','motion_overlay_max_frames','step','climb_axis','stationary_threshold_mm_s'},
  '旧版轮廓识别专用（LK 模式通常不用）':{'mode','threshold','min_area_px','segmentation','clahe'},
  '框选视频分析区域 ROI（LK 与轮廓均可用）':{'roi'},
  '外部传感器联合分析（可选）':{'behavior_enable','behavior_mode','behavior_body','behavior_feet','behavior_substrate','behavior_speed_threshold_px_s','behavior_min_dwell_s','behavior_force_file','behavior_force_time_col','behavior_force_value_col','behavior_force_shift_s','behavior_force_max_gap_s'},
  '三维相机标定与重建（默认不用）':set(k for k,_,_,_ in THREE_D_FIELDS),
 },
 '轨迹人工修正':{
  '修正后运动分析（可选）':{'motion_reference_point','motion_primary_point','motion_baseline_end_s','motion_min_movement_px','motion_sustain_frames','motion_manual_event_time_s','motion_manual_event_name','motion_pairs','motion_smooth_window','motion_max_speed_mm_s','motion_max_frequency_hz','pair_point_a','pair_point_b','climb_axis'},
  '真实三维重建（默认不用）':set(k for k,_,_,_ in THREE_D_FIELDS),
 },
 '运动关系分析':{
  '坐标列与真实尺度':{'behavior_time_col','behavior_point_col','behavior_x_col','behavior_y_col','mm_per_pixel','motion_scale_confirmed','climb_axis'},
  '运动阶段与点对':{'behavior_mode','behavior_substrate','behavior_speed_threshold_px_s','behavior_min_dwell_s'},
  '外部设备信号（可选）':{'behavior_force_file','behavior_force_time_col','behavior_force_value_col','behavior_force_shift_s','behavior_force_max_gap_s'},
 },
 '项目工作流':{
  '当前任务的输入与输出':{'pipeline_integrated_response','pipeline_integrated_reference','pipeline_integrated_targets','pipeline_integrated_max_frames','pipeline_integrated_stats','pipeline_integrated_opt','pipeline_table_x','pipeline_table_y','pipeline_table_group','pipeline_table_chart','pipeline_table_stats','pipeline_table_sample','behavior_track_format','behavior_time_col','behavior_point_col','behavior_x_col','behavior_y_col','behavior_source_unit','behavior_body','behavior_feet','climb_axis','mm_per_pixel','motion_scale_confirmed','pipeline_metric','condition_col','sample_col','pipeline_confirm_id'},
  '多源图像与传感器（仅有对应数据才展开）':{'pipeline_integrated_sync','pipeline_integrated_signal_time','pipeline_integrated_signal_value','pipeline_integrated_signal_shift','pipeline_integrated_image_confirm','pipeline_integrated_um_per_pixel','pipeline_integrated_image_mode','pipeline_integrated_image_threshold'},
  '实验优化（可选）':{'pipeline_integrated_design','pipeline_integrated_goal','pipeline_integrated_opt_confirm'},
  '专业计算细节（需核对实验规程）':{'pipeline_protocol_confirm','time_col','displacement_col','force_col','time_unit','displacement_unit','force_unit','tension_sign','force_baseline','baseline_fraction','baseline_start_s','baseline_end_s','baseline_manual_N','pull_start_s','pull_end_s','behavior_speed_threshold_px_s','behavior_min_dwell_s'},
 },
 '高级统计':{'统计诊断与随机设置':{'batch_col','bootstrap_seed'}},
 '显微图像':{'分割细节':{'threshold','roi'}},
 '信号处理':{'滤波与峰值检测高级设置':{'window','cutoff_hz','prominence'}},
 '实验数据优化':{'候选约束与模型搜索':{'weights','group_col','parameter_bounds','constraints','candidate_count','seed'}},
}
                                                                          
for _module,_spec in SPECS.items():
 _spec['fields']=[(k,V10_CONTEXT_LABELS.get((_module,k),V10_LABELS.get(k,l)),typ,d) for k,l,typ,d in _spec['fields']]

def v10_field_group(module,key):
 if key in V10_CORE.get(module,set()):return '基础输入'
 for title,keys in V10_GROUPS.get(module,{}).items():
  if key in keys:return title
 return '更多参数（高级）'

                                                            
                                                                               
RELATION_FIELDS=[
 ('behavior_mode','分析方式：通用运动关系 / 专项足端支撑候选','choice:generic|support','generic'),
 ('behavior_body','相对运动参考点（可留空；无需必须叫 body）','text',''),
 ('behavior_feet','要分析的点名（逗号分隔；留空自动读取全部）','text',''),
 ('behavior_substrate','固定画面参考点（可留空；相机移动时推荐）','text',''),
 ('behavior_speed_threshold_px_s','低速候选阈值（px/s，根据拍摄精度设定）','text','12'),
 ('behavior_min_dwell_s','低速候选最短持续时间（秒）','text','0.25'),
 ('behavior_force_file','可选：时间对应的外部力/电压/控制信号 CSV','file',''),
 ('behavior_force_time_col','外部信号时间列（秒）','text','time_s'),
 ('behavior_force_value_col','外部信号数值列','text','force_N'),
 ('behavior_force_shift_s','外部信号时钟平移（秒；必须有同步依据）','text','0'),
 ('behavior_force_max_gap_s','外部信号最大插值时间缺口（秒）','text','0.1')]
SPECS['运动关系分析']=dict(
 sub='对任意真实标记点计算投影轨迹、速度、低速时段和点对相对运动；兼容各类机器人与生物运动',
 input='本软件或高速相机软件输出的特征点坐标表（长表/宽表）',
 output='motion_relation_frames.csv · motion_relation_pairs.csv · FIGURE_motion_relation_overview',
 fields=[
 ('file','跟踪坐标 CSV / Excel','file',''),
 ('behavior_track_format','轨迹表组织形式','choice:auto|long|wide','auto'),
 ('behavior_time_col','时间列（秒）','text','time_s'),
 ('behavior_point_col','长表的特征点名称列','text','point_id'),
 ('behavior_x_col','长表的 X 坐标列','text','x_px'),
 ('behavior_y_col','长表的 Y 坐标列','text','y_px'),
 ('behavior_source_unit','原始坐标单位','choice:px|mm','px'),
 ('mm_per_pixel','已经标定的毫米/像素（没有真实标定不要解释为毫米）','text','0.05'),
 ('climb_axis','运动正方向','choice:up|down|left|right','right'),
 ('motion_scale_confirmed','实际毫米比例尺是否已核实','choice:no|yes','no'),
 ]+RELATION_FIELDS)
                                                                                          
SPECS['运动关系分析']['fields'].extend([
 ('spatial_3d_track_file','可选：已标定的三维特征点轨迹 CSV（非单目视频）','file',''),
 ('spatial_3d_reference','三维相对位置参考点名（可留空）','text',''),
 ('spatial_3d_pairs','研究哪些三维点对（如 head,tail；多个用分号）','text',''),
 ('spatial_3d_triplets','研究哪些三点空间夹角（如 A,B,C；中间点为顶点）','text','')])

                                                                                                    
for _m in ('视频追踪','轨迹人工修正'):
 SPECS[_m]['fields'].extend([('behavior_enable','附加通用运动关系分析（可选；默认关闭）','choice:no|yes','no')]+RELATION_FIELDS)

                                                                                    
SPECS['项目工作流']=dict(
 sub='统一多源实验项目：视频 / 轨迹 / 力学 / 图像 / 传感器 / 测量 → 核实实验身份 → 联合指标 → 统计与优化 → 可编辑科研图；快捷单项流程保留',
 input='多源实验清单 CSV/Excel（推荐）；也可使用原来的普通表格、运动轨迹、专项力学快捷流程',
 output='各阶段完整 CSV/Excel · workflow_index.csv · 项目结果导航.html · FIGURE_project_main.pdf/svg',fields=[
 ('pipeline_kind','① 选择项目模式：统一多源或快捷单项','choice:integrated|table|motion|force','integrated'),
 ('file','② 项目实验清单（多源）或快捷流程原始文件','pipeline_input',''),
 ('pipeline_integrated_response','联合分析关注的指标列名（先留空看实际生成的联合表）','text',''),
 ('pipeline_integrated_reference','视频特征点参考名称（例如 body，可留空）','text',''),
 ('pipeline_integrated_targets','要分析的视频点名（留空=全部）','text',''),
 ('pipeline_integrated_max_frames','每段视频最多处理多少帧','text','1200'),
 ('pipeline_integrated_stats','联合指标是否进行独立试样统计？','choice:no|yes','no'),
 ('pipeline_integrated_opt','是否根据跨实验参数与结果推荐下一组实验？','choice:no|yes','no'),
 ('pipeline_integrated_design','可人为设置的实验参数列（如 param_frequency_hz）','text',''),
 ('pipeline_integrated_goal','优化方向','choice:max|min','max'),
 ('pipeline_integrated_opt_confirm','已确认训练数据覆盖与参数物理含义？','choice:no|yes','no'),
 ('pipeline_integrated_sync','已核对仪器时钟，允许将传感器与运动数据对齐？','choice:no|yes','no'),
 ('pipeline_integrated_signal_time','传感器时间列','text','time_s'),
 ('pipeline_integrated_signal_value','传感器数值列','text','value'),
 ('pipeline_integrated_signal_shift','传感器与视频的已知时间平移（秒）','text','0'),
 ('pipeline_integrated_image_confirm','已核对图像标定和阈值含义？','choice:no|yes','no'),
 ('pipeline_integrated_um_per_pixel','图像微米/像素（必须真实标定）','text','1'),
 ('pipeline_integrated_image_mode','图像目标明暗','choice:bright|dark','bright'),
 ('pipeline_integrated_image_threshold','图像阈值（留空自动）','text',''),
                                                              
 ('pipeline_table_x','横轴 / 自变量列（填写表头）','text','time_s'),
 ('pipeline_table_y','需要展示的测量结果列（填写表头）','text','response'),
 ('pipeline_table_group','实验条件或图形分组列（可留空）','text','condition'),
 ('pipeline_table_chart','图表形式','choice:散点图|折线图|箱线散点图|直方图|累积分布图','折线图'),
 ('pipeline_table_stats','进一步做独立样本组间统计？（默认不做）','choice:no|yes','no'),
 ('pipeline_table_sample','独立试样编号列（仅做统计时需要）','text','sample_id'),
 ('pipeline_confirm_id','已核对物理独立试样身份？（仅用于力学/统计）','choice:no|yes','no'),
                                                                                  
 ('behavior_track_format','运动轨迹表组织','choice:auto|long|wide','auto'),
 ('behavior_time_col','运动轨迹时间列（秒）','text','time_s'),
 ('behavior_point_col','特征点名称列','text','point_id'),
 ('behavior_x_col','轨迹 X 坐标列','text','x_px'),('behavior_y_col','轨迹 Y 坐标列','text','y_px'),
 ('behavior_source_unit','运动坐标单位','choice:px|mm','px'),
 ('behavior_body','相对运动参考点名称（可留空）','text',''),
 ('behavior_feet','关注的特征点名称（空=全部）','text',''),
 ('behavior_substrate','固定图像参考点名称（可留空）','text',''),
 ('behavior_speed_threshold_px_s','慢速候选筛选阈值（像素/秒）','text','12'),
 ('behavior_min_dwell_s','候选阶段最短持续时间（秒）','text','0.25'),
 ('climb_axis','运动正方向','choice:up|down|left|right','right'),
 ('mm_per_pixel','毫米/像素标尺（必须有真实标定）','text','0.05'),
 ('motion_scale_confirmed','真实尺度是否已核实','choice:no|yes','no'),
                                                                         
 ('pipeline_metric','力学汇总指标（保持原始单位）','choice:peak_force_N|separation_work_mJ','peak_force_N'),
 ('pipeline_protocol_confirm','已核对拉伸力读数正负方向、力传感器零点偏移和拉离过程分析时间窗？','choice:no|yes','no'),
 ('condition_col','力学：实验条件列','text','condition'),
 ('sample_col','力学：独立试样编号列','text','sample_id'),
 ('time_col','力学：时间列','text','time_s'),
 ('displacement_col','力学：位移列','text','displacement_mm'),
 ('force_col','力学：传感器原始力列','text','force_N'),
 ('time_unit','时间单位','choice:s|ms','s'),
 ('displacement_unit','位移单位','choice:mm|um|m','mm'),
 ('force_unit','力单位','choice:N|mN|uN|gf|kgf','N'),
 ('tension_sign','拉伸力读数正负方向','choice:positive|negative','positive'),
 ('force_baseline','力传感器基线方法','choice:first_fraction|time_window|manual|zero','first_fraction'),
 ('baseline_fraction','开头多少比例估计空载基线','text','0.05'),
 ('baseline_start_s','空载基线起点（秒，可留空）','text',''),
 ('baseline_end_s','空载基线终点（秒，可留空）','text',''),
 ('baseline_manual_N','手动基线（N，可留空）','text',''),
 ('pull_start_s','拉离分析时间窗起点（秒，可留空）','text',''),
 ('pull_end_s','拉离分析时间窗终点（秒，可留空）','text',''),
])

SPECS['独立样本统计']['fields'].extend([('bootstrap_seed','Bootstrap 随机种子','text','42'),('bootstrap_rounds','Bootstrap 重采样次数','choice:1000|3000|5000|10000','3000')])
SPECS['论文绘图']=dict(sub='一键生成高清科研图，包括完整四联图 · 支持可编辑矢量文字',input='含测量列的 CSV / Excel',output='publication_figure.png/.tiff/.pdf/.svg · 图形配置与质量提示',fields=[
 ('file','绘图数据表','file',''),
 ('chart_type','选择图类型','choice:散点图|折线图|柱状图|箱线散点图|小提琴散点图|误差棒图|直方图|核密度图|累积分布图|回归图|热图|Pareto 散点图|科研四联图','箱线散点图'),
 ('chart_x','横轴 / 分组类别列','column','condition'),('chart_y','纵轴数值列','column','value'),
 ('chart_group','颜色分组列（可留空）','column',''),('chart_sample_id','独立样本 ID 列（分组统计图建议必填）','column','sample_id'),
 ('chart_xlabel','自定义 X 轴标题（留空用数据列名，建议附单位）','text',''),('chart_ylabel','自定义 Y 轴标题（留空用数据列名，建议附单位）','text',''),
 ('chart_error','柱状图 / 误差棒类型','choice:95% CI|SD|SEM|无','95% CI'),
 ('chart_goal_x','Pareto 横轴方向','choice:max|min','max'),('chart_goal_y','Pareto 纵轴方向','choice:max|min','max'),
 ('chart_title','图内标题（投稿通常留空）','text',''),
])
FIGURE_FIELDS=[
 ('plot_xlabel','单幅结果图 X 轴标题（可留空）','text',''),
 ('plot_ylabel','单幅结果图 Y 轴标题（可留空）','text',''),
 ('plot_style','绘图版式（仅控制外观）','choice:顶刊实验风|工程对比风|数据强调|期刊简洁|汇报展示','顶刊实验风'),
 ('plot_palette','图表颜色方案','choice:论文经典|冷暖对照|色盲友好|蓝绿渐层|黑白打印|灰阶','论文经典'),
 ('plot_size','最终尺寸','choice:单栏 89 mm|双栏 183 mm|汇报 16:9','双栏 183 mm'),
 ('plot_dpi','导出分辨率','choice:300|450|600|900','600'),
 ('plot_title','保留图内标题','choice:否|是','否'),
]
NO_FIGURE={'数据质检','公式优化','分析结果整理','高级统计'}
CHOICE_CN={
 'pipeline_kind':{'integrated':'多源科研项目 · 视频/力学/图像/传感器联合分析（推荐）','table':'快捷：普通实验表格 · 质检与作图','motion':'快捷：运动轨迹 · 相对运动与图版','force':'快捷：专项力学 · 批量测试与独立试样'},
 'pipeline_table_stats':{'no':'不做统计，只检查与绘图（默认）','yes':'做独立试样分组统计（需实验ID）'},
 'behavior_mode':{'generic':'通用特征点运动关系（默认）','support':'足端运动专项分析（明确标点后才用）'},
 'reconstruction_3d':{'none':'仅二维 / 单目深度不可测（默认）','stereo':'两台同步且标定的摄像机：三角测量','rigid_pnp':'单台已标定相机 + 已知刚体CAD几何：PnP位姿'},
 'tracking_mode':{'point_lk':'人工点锚定 LK 光流（推荐）','contour':'旧版明暗轮廓中心（兼容）'},
 'motion_scale_confirmed':{'yes':'已使用真实物理尺寸标定','no':'尚未核实（毫米读数仅供参考）'},
 'tension_sign':{'positive':'力传感器显示正数','negative':'力传感器显示负数'},
 'plot_palette':{'色盲友好':'清晰易分辨配色'},
 'force_baseline':{'first_fraction':'用测试开始时的空载读数归零（先确认）','time_window':'用指定的空载时间段归零（推荐）','manual':'直接填空载时的仪器读数','zero':'原始力数据已经归零'},
 'segmentation':{'fixed':'固定阈值','otsu':'Otsu 自动阈值','adaptive':'局部自适应阈值'},
 'clahe':{'no':'不增强','yes':'启用局部对比度增强'},
 'mode':{'dark':'深色目标','bright':'浅色目标'},
 'climb_axis':{'up':'向上','down':'向下','left':'向左','right':'向右'},
 'filter':{'savgol':'Savitzky–Golay 平滑','lowpass':'低通滤波','none':'不滤波'},
 'surrogate':{'GaussianProcess':'高斯过程（GP）· 不确定性约束实验推荐','Quadratic':'二次响应面（兼容旧版）'},
 'stat_method':{'paired':'配对样本检验','multi':'多独立组比较','mixed':'批次 + 试样混合效应','uncertainty':'测量不确定度合成'},
 'auto_shift':{'yes':'自动估计（需人工检查）','no':'手动输入偏移'},
 'fit_diagnostics':{'yes':'生成模型诊断','no':'不生成'},
 'model':{'linear':'线性模型','quadratic':'二次模型','exponential':'指数模型','saturation':'饱和模型'},
 'robust':{'yes':'启用','no':'不启用'},
 'goal':{'min':'最小化','max':'最大化'},
 'language':{'zh':'中文','en':'英文'},
 'algorithm':{'DE':'差分进化（DE）','SLSQP':'序列二次规划（SLSQP）','DualAnnealing':'双重退火'},
 'chart_goal_x':{'max':'越大越好','min':'越小越好'},
 'chart_goal_y':{'max':'越大越好','min':'越小越好'},
}

DEMO={
'项目工作流':'BATCH_DEMO',
'批量力学':'BATCH_DEMO','高级统计':'demo_paired.csv','轨迹人工修正':'DEMO_TRACK',
'数据质检':'demo_force.csv','力学分析':'demo_force.csv','视频追踪':'demo_climbing.avi','运动关系分析':'通用轨迹/demo_generic_points.csv','运动机制分析':'足端运动关系/demo_foot_motion.csv',
'显微图像':'demo_contact.png','信号处理':'demo_signal.csv','独立样本统计':'demo_stats.csv',
'曲线拟合':'demo_fit.csv','论文绘图':'demo_stats.csv','实验数据优化':'demo_optimization.csv','多源同步':'demo_signal.csv'}

NAVY='#0F172A'; SIDEBAR='#111C30'; PANEL='#F8FAFC'; WHITE='#FFFFFF'; TEXT='#15253D'; MUTED='#64748B'; ACCENT='#0E7490'; ACCENT_HOVER='#155E75'; BORDER='#DDE5EE'

PALETTE89={
 '经典蓝色':('#111C30','#F8FAFC','#FFFFFF','#0E7490','#15253D','#64748B'),
 '深色配色':('#101728','#141D2D','#202C3F','#9FC8E6','#EDF2FC','#B5C3D9'),
 '粉色配色':('#503D55','#FFF4FA','#FFFBFE','#C66B9D','#503A53','#95788E'),
}
UI_LAYOUTS=('均衡双栏','顶部导航','环形浮动工作台')

class Desktop(tk.Tk):
 def __init__(self):
  super().__init__()
  self.title('Research Toolbox · 科研数据分析')
  screen_w,screen_h=self.winfo_screenwidth(),self.winfo_screenheight()
                                                                  
  self.geometry(f'{min(1440,max(880,screen_w-45))}x{min(900,max(650,screen_h-75))}')
  self.minsize(880,620)
  try:self.tk.call('tk','scaling',1.23)
  except Exception:pass
  self.configure(bg=PANEL)
  self._run_messages=queue.Queue();self.last_output=None;self.recent_completed_result=None;self.module=None;self.controls={};self.busy=False;self.choice_maps={};self.figures=[];self.figure_index=0;self.figure_ref=None
  self.output_var=tk.StringVar(value=str(OUT))
  self.fonts={}
  self._help_windows=[];self._result_popups=[]
  self._ui_chinese_font=self._select_ui_font()
  self._metrics_window=None
  self._ui_theme='经典蓝色';self._ui_layout='均衡双栏';self.nav_bg=SIDEBAR;self.nav_active_bg='#176077'
  self.orbit_nav=None;self.top_nav=None;self._module_palette=None;self._spatial_window=None;self.floating_results=None
  self._suspend_invalidation=True;self._run_token=0;self._result_snapshot=None
  self._observed_values={};self._locked_inputs=[];self._start_monotonic=None;self._cancel_event=None
  MODULE_STORIES.update(VIDEO_STORIES)
  MODULE_STORIES.update(MODULE_STORIES_104)
  MODULE_STORIES.setdefault('项目工作流','【用它解决什么问题】把已经做过的力学实验或外部轨迹文件串成一个可审核的项目结果：分阶段运行现成模块、保留原始表格、输出导航、按真实试样制图。\n【什么时候需要】多份文件需要重复做质检、汇总、对比和出图，或希望把外部高速相机的运动数据接入研究平台。\n【什么时候不需要】只看一段曲线、暂时没有真实试样编号、或尚不清楚实验力方向和仪器标定时，先用单独模块核对。\n【真实例子】对20块足垫的多次力学循环先求每块试样均值，再进行独立试样比较和生成结果图；或者输入翅根翅尖坐标，查看投影运动与时间阶段。\n【输入与输出】输入整个仪器数据文件夹或轨迹CSV；力学必须核对零点、单位、独立试样ID，轨迹必须确认真实点名。输出每阶段子文件夹、workflow_index.csv、分析准备表、PDF/SVG和本地结果导航页。')
  self._style();self._layout();self.switch('项目工作流')
  try:
   saved=json.loads((APP_DIR/'ui_preferences.json').read_text(encoding='utf-8'))
   theme=saved.get('theme','经典蓝色');layout=saved.get('layout','均衡双栏')
   if theme=='柔粉配色':theme='粉色配色'                             
   if theme!='经典蓝色' or layout!='均衡双栏':self.apply_appearance(theme,layout,save=False)
  except (OSError,ValueError,KeyError,TypeError):pass
  self._suspend_invalidation=False

 def open_appearance(self):
  """Three deliberate themes and three different navigation layouts."""
  if self.busy:return                                                     
  w=tk.Toplevel(self);w.title('外观与布局');w.geometry('490x375');w.minsize(440,360)
  color=self._theme_colors();w.configure(bg=color['card'])
  tk.Label(w,text='选择工作台外观',bg=color['card'],fg=color['text'],font=self._font(15,True)).pack(anchor='w',padx=24,pady=(22,8))
  tk.Label(w,text='保留原有字体和操作流程；可随时恢复经典双栏。',bg=color['card'],fg=color['muted'],font=self._font(10)).pack(anchor='w',padx=24,pady=(0,14))
  theme=tk.StringVar(value=self._ui_theme);lay=tk.StringVar(value=self._ui_layout)
  for title,var,values in [('界面配色',theme,list(PALETTE89)),('界面布局',lay,UI_LAYOUTS)]:
   tk.Label(w,text=title,bg=color['card'],fg=color['text'],font=self._font(11,True)).pack(anchor='w',padx=24,pady=(10,4))
   ttk.Combobox(w,textvariable=var,values=values,state='readonly',font=self._font(10)).pack(fill='x',padx=24)
  tk.Label(w,text='环形浮动工作台在独立居中窗口里显示放大、缓慢旋转的导航；关闭后可以随时从主窗口重新打开。',
     bg=color['card'],fg=color['muted'],justify='left',font=self._font(10),wraplength=424).pack(anchor='w',padx=24,pady=(13,8))
  tk.Button(w,text='应用',command=lambda:(self.apply_appearance(theme.get(),lay.get()),w.destroy()),
      bg=color['accent'],fg=color['button_fg'],relief='flat',padx=20,pady=9,font=self._font(10,True)).pack(anchor='e',padx=24,pady=(7,0))

 def _make_top_nav(self):
  if self.top_nav is not None and self.top_nav.winfo_exists():return
  self.top_nav=tk.Frame(self,bg='#E7F0F6')
  self.top_bar=tk.Frame(self.top_nav,bg='#E7F0F6');self.top_bar.pack(fill='x',padx=9,pady=7)
  tk.Button(self.top_bar,text='◉  打开模块导航',command=self.open_module_palette,
       bg='#D7E8F3',fg='#1F4055',relief='flat',padx=13,pady=9,font=self._font(10,True)).pack(side='left',padx=(0,9))
  for name in ('项目工作流','视频追踪','运动关系分析','实验数据优化'):
   tk.Button(self.top_bar,text=name,command=lambda m=name:self.switch(m),
       bg='#FFFFFF',fg='#23445A',relief='flat',padx=9,pady=9,cursor='hand2').pack(side='left',padx=3)
  tk.Button(self.top_bar,text='弹出结果',command=self.open_floating_results,
       bg='#D7E8F3',fg='#1F4055',relief='flat',padx=9,pady=9).pack(side='right')

 def open_module_palette(self):
  """One launcher for ring + search; closing never removes the reopen button."""
  if self._spatial_window is not None:
   try:
    if self._spatial_window.winfo_exists():
     self._spatial_window.lift();self._spatial_window.focus_force();return
   except tk.TclError:pass
  from ui_spatial90 import SpatialModuleLauncher
  self._spatial_window=SpatialModuleLauncher(self,self.switch,self._font(15,True),self._ui_theme)
  self._module_palette=self._spatial_window

 def open_floating_results(self):
  if self.floating_results is not None:
   try:
    if self.floating_results.winfo_exists():self.floating_results.lift();self._refresh_floating_results();return
   except tk.TclError:pass
  w=tk.Toplevel(self);self.floating_results=w;w.title('独立结果摘要 · 可移动、可缩放');w.geometry('780x590');w.minsize(480,320)
  main=tk.Frame(w,bg='#F8FAFC');main.pack(fill='both',expand=True)
  top=tk.Frame(main,bg='#E6F0F5');top.pack(fill='x')
  tk.Label(top,text='分析结果 · 独立阅读窗口',bg='#E6F0F5',fg='#213C52',font=self._font(14,True)).pack(side='left',padx=14,pady=11)
  tk.Button(top,text='刷新',command=self._refresh_floating_results,bg='#D2E7EF',relief='flat').pack(side='right',padx=12)
  self.floating_text=tk.Text(main,wrap='word',font=self._font(11),bg='white',fg='#203747',relief='flat',padx=18,pady=15)
  self.floating_text.pack(fill='both',expand=True,padx=12,pady=12)
  self._refresh_floating_results()
  w.protocol('WM_DELETE_WINDOW',lambda:(w.destroy(),setattr(self,'floating_results',None)))

 def _refresh_floating_results(self):
  w=self.floating_results
  if w is None or not w.winfo_exists():return
  result=self.result_text.get('1.0','end-1c')
  self.floating_text.configure(state='normal');self.floating_text.delete('1.0','end')
  self.floating_text.insert('1.0',f'当前模块：{self.module}\n\n'+result)
  self.floating_text.configure(state='disabled')

 def _set_navigation_layout(self,layout):
  """No analysis widgets are recreated; only navigation is rearranged."""
  self.left.pack_forget()
  if self.orbit_nav is not None:self.orbit_nav.pack_forget()
  if self.top_nav is not None:self.top_nav.pack_forget()
  if layout=='均衡双栏':
   self.left.pack(side='left',fill='y',before=self.main)
  else:
   self._make_top_nav();self.top_nav.pack(side='top',fill='x',before=self.main)
  for item in (self.inputs_card,self.output_card):item.pack_forget()
  self.inputs_card.pack(side='left',fill='both',expand=False,padx=(0,10))
  self.output_card.pack(side='right',fill='both',expand=True,padx=(10,0))
  self._resize_input_scroll()

 def _theme_colors(self):
  base=PALETTE89[self._ui_theme]
  return {'sidebar':base[0],'panel':base[1],'card':base[2],
          'accent':base[3],'text':base[4],'muted':base[5],
          'button_fg':'#FFFFFF' if self._ui_theme!='粉色配色' else '#FFFFFF'}

 def _style_theme_widgets(self):
  """Normalize the ORIGINAL semantic colors on every pass.

  This includes widgets newly rebuilt when changing modules and solves the
  old dark-mode problem where some labels became dark-on-dark and some cards
  kept their pale, unrelated backgrounds.
  """
  colors=self._theme_colors();mode=self._ui_theme
  base_palette=set(PALETTE89['经典蓝色'])
  darkbg={'#111C30','#0F172A','#14283F','#172337','#223B55','#1F4055','#334155'}
  panels={'#F8FAFC','#F1F7F9','#F0F6F8','#F2F5F6','#F4F8FB','#E7F0F6','#E9F2F8','#E6F0F5','#EAF6F5','#F0F8F9','#EEF8FA','#EFF5FC','#ECF7FA','#EAF5F7','#E6F4F0','#E0F2FE','#E2EDF3','#F1F5F9','#E9F1F5','#E4F4EF','#DBEAFE','#DDF1F7','#D7E8F3','#D3EDF4','#D8F0E9','#F0F6F8','#ECF6F8','#F1F7F9'}
  prominent={'#0E7490','#155E75','#146B82','#176077','#135E69','#B77798','#C66B9D'}
  light_text={'#FFFFFF','#F8FAFC','#E7EDF4','#E9F3FA'}
  muted_text={'#64748B','#708090','#516675','#6B7A75','#647B8B','#82736A','#987C8B','#B1C2CE'}
  def norm(widget):
   try:
    if not getattr(widget,'_rt90_base',None):
     original={}
     for option in ('bg','fg','activebackground','activeforeground','insertbackground','selectcolor'):
      try:original[option]=str(widget.cget(option)).upper()
      except (tk.TclError,KeyError):pass
     widget._rt90_base=original
    original=widget._rt90_base
    opts={}
    bg=original.get('bg','')
    fg=original.get('fg','')
    if bg:
     if bg in (x.upper() for x in darkbg):dest=colors['sidebar']
     elif bg in ('#FFFFFF','#FFFEFA','#FFFCF8'):dest=colors['card']
     elif bg in (x.upper() for x in panels):
      dest=('#29364B' if mode=='深色配色' else '#FFEDF5' if mode=='粉色配色' else '#EFF6FA')
     elif bg in (x.upper() for x in prominent):dest=colors['accent']
     elif bg.startswith('#'):
      dest=('#2B3950' if mode=='深色配色' else '#FBE6F0' if mode=='粉色配色' else bg)
     else:dest=bg
     opts['bg']=dest
    else:dest=colors['card']
    if fg:
     if fg in (x.upper() for x in light_text) and dest==colors['accent']:
      opts['fg']='#FFFFFF'
     elif dest==colors['sidebar']:
      opts['fg']='#F6F3FC' if mode!='经典蓝色' else '#CBD5E1'
     elif dest==colors['accent']:
      opts['fg']='#FFFFFF'
     elif fg in (x.upper() for x in muted_text):
      opts['fg']=colors['muted']
     else:
      opts['fg']=colors['text']
    if isinstance(widget,tk.Text):
     opts['insertbackground']=colors['text']
    if isinstance(widget,tk.Checkbutton):
     opts['selectcolor']=colors['panel']
    if isinstance(widget,tk.Button):
     opts['activebackground']=colors['accent']
     opts['activeforeground']='#FFFFFF'
    if opts:widget.configure(**opts)
   except (tk.TclError,ValueError):pass
   try:
    for ch in widget.winfo_children():norm(ch)
   except tk.TclError:pass
  norm(self)
  self.s.configure('TLabel',background=colors['card'],foreground=colors['text'])
  self.s.configure('Treeview',background=colors['card'],foreground=colors['text'],fieldbackground=colors['card'])
  self.s.map('Treeview',background=[('selected',colors['accent'])],foreground=[('selected','#FFFFFF')])
  self.s.configure('TEntry',fieldbackground=colors['card'],foreground=colors['text'])
  self.s.configure('TCombobox',fieldbackground=colors['card'],foreground=colors['text'])
  self.s.map('TCombobox',fieldbackground=[('readonly',colors['card'])],foreground=[('readonly',colors['text'])])
  self.s.configure('TNotebook',background=colors['panel'],borderwidth=0)
  self.s.configure('TNotebook.Tab',background=colors['panel'],foreground=colors['text'],padding=(12,8))
  self.s.map('TNotebook.Tab',background=[('selected',colors['card'])],foreground=[('selected',colors['accent'])])
  self.nav_bg=colors['sidebar'];self.nav_active_bg=colors['accent']
  for module,button in getattr(self,'nav',{}).items():
   try:
    button.configure(bg=colors['accent'] if module==self.module else colors['sidebar'],
                     fg='#FFFFFF' if module==self.module else '#D5E2F0')
   except tk.TclError:pass

 def apply_appearance(self,theme,layout,save=True):
  """Three themes × three layouts; old preferences mapped to valid choices."""
  if self.busy:return
  alias={'深海蓝（原版）':'经典蓝色','晨雾浅蓝':'经典蓝色','薄荷奶油':'经典蓝色',
         '暖砂杏色':'经典蓝色','极简灰白':'经典蓝色','深色夜航':'深色配色','柔粉配色':'粉色配色'}
  theme=alias.get(theme,theme)
  if theme not in PALETTE89:theme='经典蓝色'
  if layout in ('环形导航','浮动导航'):layout='环形浮动工作台'
  if layout not in UI_LAYOUTS:layout='均衡双栏'
  self._ui_theme=theme;self._ui_layout=layout
  if self.module:self.heading.configure(text=('✿  ' if theme=='粉色配色' else '')+self.module)
  self.inputs_card.configure(width=450)
  self.left.configure(width=218)
  if layout!='环形浮动工作台' and self._spatial_window is not None:
   try:
    if self._spatial_window.winfo_exists():self._spatial_window.close()
   except tk.TclError:pass
  self._set_navigation_layout(layout)
  self._style_theme_widgets()
  self.update_idletasks()
  if layout=='环形浮动工作台':self.after_idle(self.open_module_palette)
  if self._spatial_window is not None:
   try:
    if self._spatial_window.winfo_exists() and self._spatial_window.theme!=theme:
     self._spatial_window.close();self._spatial_window=None
     if layout=='环形浮动工作台':self.after_idle(self.open_module_palette)
   except tk.TclError:pass
  if save:
   try:(APP_DIR/'ui_preferences.json').write_text(json.dumps({'theme':theme,'layout':layout},ensure_ascii=False,indent=2),encoding='utf-8')
   except OSError:pass

 def _select_ui_font(self):
  """Use real YaHei on Windows; avoid silently falling back to serif elsewhere."""
  installed={f.casefold():f for f in tkfont.families(self)}
  for family in ('Microsoft YaHei UI','Microsoft YaHei','微软雅黑','Noto Sans CJK SC','Noto Sans SC','Arial'):
   if family.casefold() in installed:return installed[family.casefold()]
  return 'TkDefaultFont'

 def _font(self,size=10,bold=False,family=None):
  if family in (None,'SimSun','Times New Roman'):
   family=self._ui_chinese_font
  key=(family,size,bold)
  if key not in self.fonts:self.fonts[key]=tkfont.Font(root=self,family=family,size=size,weight='bold' if bold else 'normal')
  return self.fonts[key]

 def _style(self):
  self.option_add('*Font',self._font(11))
  self.s=ttk.Style(self);self.s.theme_use('clam')
  self.s.configure('TLabel',background=WHITE,foreground=TEXT,font=self._font(11))
  self.s.configure('Muted.TLabel',background=WHITE,foreground=MUTED,font=self._font(10))
  self.s.configure('TEntry',padding=8,font=self._font(10),fieldbackground='#FFFFFF',foreground=TEXT)
  self.s.configure('TCombobox',padding=8,font=self._font(10),fieldbackground=WHITE,foreground=TEXT)
  self.s.configure('Treeview',rowheight=33,font=self._font(10),borderwidth=0,background=WHITE,fieldbackground=WHITE)
  self.s.configure('Treeview.Heading',font=self._font(10,True),background='#E9F1F5',foreground=TEXT)
  self.s.map('Treeview',background=[('selected','#CBEBF0')],foreground=[('selected',TEXT)])
  self.s.configure('Vertical.TScrollbar',gripcount=0,background='#CBD5E1',troughcolor=WHITE)

 def _layout(self):
  self.left=tk.Frame(self,bg=SIDEBAR,width=218);self.left.pack(side='left',fill='y');self.left.pack_propagate(False)
  tk.Label(self.left,text='◈  Toolbox',bg=SIDEBAR,fg='#E0F2FE',font=self._font(19,True)).pack(anchor='w',padx=19,pady=(26,2))
  self.nav={}
  navwrap=tk.Frame(self.left,bg=SIDEBAR);navwrap.pack(fill='both',expand=True)
                                                                          
                                                                                   
  navcanvas=tk.Canvas(navwrap,bg=SIDEBAR,highlightthickness=0,width=195,bd=0)
  navscroll=ttk.Scrollbar(navwrap,orient='vertical',command=navcanvas.yview)
  self._nav_scrollbar=navscroll
  self._nav_canvas=navcanvas
  navcanvas.configure(yscrollcommand=navscroll.set)
  navcanvas.pack(side='left',fill='both',expand=True)
  self.nav_inner=tk.Frame(navcanvas,bg=SIDEBAR)
  navwindow=navcanvas.create_window((0,0),window=self.nav_inner,anchor='nw')
  self._nav_scrolling=False
  def nav_autoscroll(_event=None):
   try:
    available=navcanvas.winfo_height()
    if available<=1:return
    overflow=self.nav_inner.winfo_reqheight()>available+3
    self._nav_scrolling=bool(overflow)
    if overflow:
     if not navscroll.winfo_manager():navscroll.pack(side='right',fill='y')
    else:
     navcanvas.yview_moveto(0)
     if navscroll.winfo_manager():navscroll.pack_forget()
   except tk.TclError:pass
  self.nav_inner.bind('<Configure>',lambda e:(navcanvas.configure(scrollregion=navcanvas.bbox('all')),self.after_idle(nav_autoscroll)))
  navcanvas.bind('<Configure>',lambda e:(navcanvas.itemconfigure(navwindow,width=e.width),self.after_idle(nav_autoscroll)))
  def nav_wheel(e):
                                                                      
   if self._nav_scrolling:
    delta=getattr(e,'delta',0)
    step=-1 if delta>0 or getattr(e,'num',None)==4 else 1
    navcanvas.yview_scroll(step,'units')
   return 'break'
  navcanvas.bind('<MouseWheel>',nav_wheel)
  navcanvas.bind('<Button-4>',nav_wheel)
  navcanvas.bind('<Button-5>',nav_wheel)
  sections=[(name,f'{i:02d}') for i,name in enumerate(('项目工作流','数据质检','批量力学','力学分析','高级统计','视频追踪','轨迹人工修正','运动关系分析','显微图像','信号处理','多源同步','独立样本统计','曲线拟合','公式优化','实验数据优化','分析结果整理','论文绘图'),start=1)]
  for m,n in sections:
   btn=tk.Button(self.nav_inner,text=f' {n}    {display_name(m)}',command=lambda name=m:self.switch(name),anchor='w',cursor='hand2',relief='flat',bd=0,padx=15,pady=4,bg=SIDEBAR,fg='#CBD5E1',activebackground='#1C3852',activeforeground='white',font=self._font(10))
   btn.pack(fill='x',padx=8,pady=1);self.nav[m]=btn
   btn.bind('<MouseWheel>',nav_wheel)
   btn.bind('<Enter>',lambda e,b=btn,name=m: b.configure(bg=(self.nav_active_bg if self.module==name else '#28516A' if self._ui_theme=='深海蓝（原版）' else '#3B6571')))
   btn.bind('<Leave>',lambda e,b=btn,name=m: b.configure(bg=self.nav_active_bg if self.module==name else self.nav_bg))
   self._bind_help(btn,lambda name=m:(display_name(name),module_text(name)))
  tk.Frame(self.left,bg='#334155',height=1).pack(fill='x',padx=20,pady=(10,8))
  self.main=tk.Frame(self,bg=PANEL);self.main.pack(fill='both',expand=True)
  head=tk.Frame(self.main,bg=PANEL);head.pack(fill='x',padx=28,pady=(21,14))
  title_row=tk.Frame(head,bg=PANEL);title_row.pack(fill='x')
  self.heading=tk.Label(title_row,text='',bg=PANEL,fg=TEXT,font=self._font(23,True));self.heading.pack(side='left',anchor='w')
  tk.Button(title_row,text='◎  模块导航',command=self.open_module_palette,bg='#E2EDF3',fg=TEXT,relief='flat',cursor='hand2',padx=11,pady=8,font=self._font(10,True)).pack(side='right',padx=(0,8),anchor='n')
  tk.Button(title_row,text='◐  主题与布局',command=self.open_appearance,bg='#E2EDF3',fg=TEXT,relief='flat',cursor='hand2',padx=12,pady=8,font=self._font(10,True)).pack(side='right',anchor='n')
  tk.Button(title_row,text='▢ 弹出结果',command=self.open_floating_results,bg='#E2EDF3',fg=TEXT,relief='flat',cursor='hand2',padx=10,pady=8,font=self._font(10)).pack(side='right',padx=(0,8),anchor='n')
  self._bind_help(self.heading,lambda:(display_name(self.module),module_text(self.module)))
  tk.Button(head,text='？ 实际作用',command=lambda:self.show_help(display_name(self.module),module_text(self.module)),bg='#DBEAFE',fg=ACCENT,relief='flat',padx=12,pady=5,cursor='hand2',font=self._font(10,True)).pack(anchor='w',pady=(7,0))
  self.subtitle=tk.Label(head,text='',bg=PANEL,fg=MUTED,font=self._font(10));self.subtitle.pack(anchor='w',pady=(3,0))
  self.work=tk.Frame(self.main,bg=PANEL);self.work.pack(fill='both',expand=True,padx=18)
  self.inputs_card=tk.Frame(self.work,bg=WHITE,highlightbackground=BORDER,highlightthickness=1,width=450);self.inputs_card.pack(side='left',fill='both',expand=False,padx=(0,10));self.inputs_card.pack_propagate(False)
  self.topline=tk.Frame(self.inputs_card,bg=WHITE);self.topline.pack(fill='x',padx=20,pady=(17,8))
  tk.Label(self.topline,text='实验输入与参数',bg=WHITE,fg=TEXT,font=self._font(13,True)).pack(side='left')
  self.demo_button=tk.Button(self.topline,text='使用演示数据',bg='#E0F2FE',fg=ACCENT,activebackground='#BAE6FD',relief='flat',cursor='hand2',padx=10,pady=6,command=self.use_demo,font=self._font(10,True));self.demo_button.pack(side='right')
                                                                                        
  self.input_scroll_holder=tk.Frame(self.inputs_card,bg=WHITE)
  self.input_scroll_holder.pack(fill='both',expand=True)
  self.cv=tk.Canvas(self.input_scroll_holder,highlightthickness=0,bg=WHITE)
  self.sc=ttk.Scrollbar(self.input_scroll_holder,orient='vertical',command=self.cv.yview)
  self.input_xscroll=ttk.Scrollbar(self.input_scroll_holder,orient='horizontal',command=self.cv.xview)
  self.cv.configure(yscrollcommand=self.sc.set,xscrollcommand=self.input_xscroll.set)
  self.cv.grid(row=0,column=0,sticky='nsew');self.sc.grid(row=0,column=1,sticky='ns')
  self.input_xscroll.grid(row=1,column=0,sticky='ew')
  self.input_scroll_holder.grid_rowconfigure(0,weight=1)
  self.input_scroll_holder.grid_columnconfigure(0,weight=1)
  self.form=tk.Frame(self.cv,bg=WHITE)
  self.canvas_id=self.cv.create_window((0,0),window=self.form,anchor='nw')
  self.form.bind('<Configure>',self._resize_input_scroll)
  self.cv.bind('<Configure>',self._resize_input_scroll)
  self.cv.bind_all('<MouseWheel>',self._wheel)
  self.output_card=tk.Frame(self.work,bg=WHITE,highlightbackground=BORDER,highlightthickness=1,width=430);self.output_card.pack(side='right',fill='both',expand=True,padx=(10,0));self.output_card.pack_propagate(False)
  tk.Label(self.output_card,text='预览与分析结果',bg=WHITE,fg=TEXT,font=self._font(13,True)).pack(anchor='w',padx=18,pady=(18,8))
  self.view_tabs=ttk.Notebook(self.output_card);self.view_tabs.pack(fill='both',expand=True,padx=15,pady=(0,15))
  self.preview=tk.Frame(self.view_tabs,bg=WHITE);self.results=tk.Frame(self.view_tabs,bg=WHITE)
  self.view_tabs.add(self.preview,text='数据预览');self.view_tabs.add(self.results,text='结果摘要')
  self.graph=tk.Frame(self.view_tabs,bg=WHITE);self.view_tabs.add(self.graph,text='高清图片')
  self.view_tabs.bind('<<NotebookTabChanged>>',lambda e:self.after_idle(self._show_figure) if (str(self.view_tabs.select())==str(self.graph) and self.figures) else None)
  self.detail_tab=tk.Frame(self.view_tabs,bg=WHITE)
  self.view_tabs.add(self.detail_tab,text='结果表格')
  self._make_detail_view()
  self._make_graph_view()
  self._make_preview()
  self.result_top=tk.Frame(self.results,bg='#EAF6F5');self.result_top.pack(fill='x',padx=10,pady=(11,4))
  self.result_head=tk.Label(self.result_top,text='尚未运行分析',bg='#EAF6F5',fg=ACCENT,font=self._font(12,True),padx=12,pady=12,anchor='w');self.result_head.pack(fill='x')
  self.result_info_card=tk.Frame(self.results,bg=WHITE,highlightbackground='#DCE9EF',highlightthickness=1)
  self.result_info_card.pack(fill='x',padx=13,pady=(4,6))
  self.result_info_toggle=tk.Button(self.result_info_card,text='▸  结果文件与阅读方法',command=self._toggle_result_info,
    bg='#EEF6F8',fg=ACCENT,relief='flat',anchor='w',padx=10,pady=8,cursor='hand2',font=self._font(10,True))
  self.result_info_toggle.pack(fill='x')
  self.result_info_body=tk.Frame(self.result_info_card,bg=WHITE)
  self.read_files_btn=tk.Button(self.result_info_body,text='📁  本次输出文件',command=self.open_result_guide,bg='#E0F2FE',fg=ACCENT,relief='flat',padx=10,pady=9,cursor='hand2',font=self._font(10,True));self.read_files_btn.pack(fill='x',padx=12,pady=(10,5))
  self.reader_btn=tk.Button(self.result_info_body,text='📘  指标、图表和参数说明',command=self.open_run_reader,bg='#EEF6F8',fg=ACCENT,relief='flat',padx=10,pady=8,cursor='hand2',font=self._font(10));self.reader_btn.pack(fill='x',padx=12,pady=(0,5))
  self.file_tiers_btn=tk.Button(self.result_info_body,text='📂  按用途查看文件：核心结果／质量检查／运行记录',command=self.open_output_tiers,bg='#F3F5F8',fg=ACCENT,relief='flat',padx=10,pady=8,font=self._font(10));self.file_tiers_btn.pack(fill='x',padx=12,pady=(0,5))
  self.project_nav_button=tk.Button(self.result_info_body,text='◈  打开本次项目导航',command=self.open_project_navigation,
    bg='#D8F0E9',fg='#145C56',relief='flat',padx=10,pady=9,cursor='hand2',font=self._font(10,True))
  self.result_info_open=False
  self._bind_help(self.read_files_btn,lambda:('结果文件','列出这次实际生成的表格、图片和运行记录。选文件可查看用途和字段说明，双击可直接打开。'))
  self.metric_row=tk.Frame(self.results,bg=WHITE);self.metric_row.pack(fill='x',padx=12,pady=(5,7))
  self.metric_cards=[]
  self._metric_keys=[]
  for _ in range(3):
   card=tk.Frame(self.metric_row,bg='#F1F7F9',highlightbackground='#DEEAF0',highlightthickness=1)
   card.pack(side='left',expand=True,fill='x',padx=3)
   value=tk.Label(card,text='—',bg='#F1F7F9',fg=ACCENT,font=self._font(12,True));value.pack(anchor='w',padx=8,pady=(8,0))
   name=tk.Label(card,text='等待分析',bg='#F1F7F9',fg=MUTED,font=self._font(8));name.pack(anchor='w',padx=8,pady=(1,8))
   self.metric_cards.append((value,name))
   i=len(self.metric_cards)-1
   tk.Button(card,text='？',command=lambda ix=i:self.show_help(*self._metric_help_pair(ix)),
             bg='#E0F2FE',fg=ACCENT,relief='flat',font=self._font(9,True),
             cursor='hand2',padx=4,pady=0).place(relx=1.0,x=-4,y=4,anchor='ne')
   self._bind_help(name,lambda ix=i:self._metric_help_pair(ix))
   self._bind_help(value,lambda ix=i:self._metric_help_pair(ix))
  self.metrics_header=tk.Frame(self.results,bg=WHITE)
  self.metrics_header.pack(fill='x',padx=12,pady=(7,2))
  self.metrics_toggle=tk.Button(self.metrics_header,text='▸  全部指标与计算结果',
       command=self._toggle_metrics,bg='#ECF6F8',fg=ACCENT,relief='flat',anchor='w',
       font=self._font(10,True),cursor='hand2',padx=10,pady=8)
  self.metrics_toggle.pack(fill='x')
  self.metric_open=False
  self.metrics_body=tk.Frame(self.results,bg=WHITE)
  results_box=tk.Frame(self.metrics_body,bg=WHITE)
  results_box.pack(fill='both',expand=True,padx=11,pady=(1,5))
  self.all_results_scroll=tk.Canvas(results_box,bg=WHITE,highlightthickness=0,height=290)
  self.all_results_ybar=ttk.Scrollbar(results_box,orient='vertical',command=self.all_results_scroll.yview)
  self.all_results_ybar.pack(side='right',fill='y')
  self.all_results_scroll.pack(side='left',fill='both',expand=True)
  self.all_results_scroll.configure(yscrollcommand=self.all_results_ybar.set)
  self.all_results_inner=tk.Frame(self.all_results_scroll,bg=WHITE)
  self.all_results_window=self.all_results_scroll.create_window((0,0),window=self.all_results_inner,anchor='nw')
  self.all_results_inner.bind('<Configure>',lambda e:self.all_results_scroll.configure(scrollregion=self.all_results_scroll.bbox('all')))
  self.all_results_scroll.bind('<Configure>',lambda e:self.all_results_scroll.itemconfigure(self.all_results_window,width=e.width))
  self.result_text=tk.Text(self.results,bg=WHITE,fg=TEXT,relief='flat',padx=12,pady=12,font=self._font(10),wrap='word');self.result_text.pack(fill='both',expand=True)
  self.result_text.insert('1.0','选择一个分析模块并填写输入。\n\n开始分析后，这里会显示本次核心结果、主要提醒和建议阅读顺序。\n\n完整表格、图片和原始数值会自动保存到新的结果文件夹。');self.result_text.configure(state='disabled')
  self.result_text.bind('<Button-3>',self._result_help_click)
  self.result_text.bind('<Control-Button-1>',self._result_help_click)
  footer=tk.Frame(self.main,bg=PANEL);footer.pack(fill='x',padx=28,pady=(14,23))
  self.status=tk.Label(footer,text='就绪 · 结果默认在程序文件夹 · 不修改原文件',bg=PANEL,fg=MUTED,font=self._font(10));self.status.pack(side='left')
  self.run_btn=tk.Button(footer,text='▶  开始分析',command=self.run,bg=ACCENT,fg='white',activebackground=ACCENT_HOVER,activeforeground='white',relief='flat',padx=24,pady=11,cursor='hand2',font=self._font(11,True));self.run_btn.pack(side='right')
  self.cancel_btn=tk.Button(footer,text='请求停止（安全检查点）',command=self.request_cancel,bg='#E6EBF2',fg=TEXT,relief='flat',padx=8,pady=11,state='disabled',font=self._font(9));self.cancel_btn.pack(side='right',padx=(0,4))
  tk.Button(footer,text='打开结果目录',command=self.open_output,bg='#E2E8F0',fg=TEXT,relief='flat',padx=14,pady=11,cursor='hand2',font=self._font(10)).pack(side='right',padx=9)

 def _close_metrics(self):
  win=getattr(self,'_metrics_window',None)
  self._metrics_window=None
  self.metric_open=False
  try:
   if win and win.winfo_exists():win.destroy()
  except tk.TclError:pass
  self.metrics_toggle.configure(text='▸  全部指标与计算结果')

 def _toggle_result_info(self):
  if not getattr(self,'result_info_body',None):return
  self.result_info_open=not getattr(self,'result_info_open',False)
  if self.result_info_open:
   self.result_info_body.pack(fill='x')
   self.result_info_toggle.configure(text='▾  收起结果文件与阅读方法')
  else:
   self.result_info_body.pack_forget()
   self.result_info_toggle.configure(text='▸  结果文件与阅读方法')
 
 def _toggle_metrics(self):
  """Open all metrics OUTSIDE the result page; clicking again reliably closes."""
  if getattr(self,'_metrics_window',None) is not None:
   self._close_metrics();return
  win=tk.Toplevel(self)
  self._metrics_window=win;self.metric_open=True
  win.title('全部指标与计算结果')
  win.geometry('850x650');win.minsize(510,390)
  win.configure(bg=WHITE)
  win.protocol('WM_DELETE_WINDOW',self._close_metrics)
  self.metrics_toggle.configure(text='▾  关闭结果字段窗口')
  top=tk.Frame(win,bg='#EAF5F7');top.pack(fill='x')
  tk.Label(top,text='全部结果字段',font=self._font(15,True),bg='#EAF5F7',fg=TEXT).pack(anchor='w',padx=18,pady=(15,4))
  tk.Label(top,text='逐项查看本次摘要中的完整数值。点击问号可核对计算口径、用途和限制；原始字段名与数值保存在结果文件中。',
           font=self._font(10),bg='#EAF5F7',fg=MUTED,anchor='w',justify='left',wraplength=760).pack(fill='x',padx=18,pady=(0,12))
  outer=tk.Frame(win,bg=WHITE);outer.pack(fill='both',expand=True,padx=12,pady=10)
  canvas=tk.Canvas(outer,bg=WHITE,highlightthickness=0)
  vs=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
  hs=ttk.Scrollbar(outer,orient='horizontal',command=canvas.xview)
  canvas.configure(xscrollcommand=hs.set,yscrollcommand=vs.set)
  canvas.grid(row=0,column=0,sticky='nsew');vs.grid(row=0,column=1,sticky='ns');hs.grid(row=1,column=0,sticky='ew')
  outer.grid_rowconfigure(0,weight=1);outer.grid_columnconfigure(0,weight=1)
  inner=tk.Frame(canvas,bg=WHITE)
  window=canvas.create_window((0,0),window=inner,anchor='nw')
  wrap_targets=[]
  def update_scroll(_=None):
   canvas.configure(scrollregion=canvas.bbox('all'))
  inner.bind('<Configure>',update_scroll)
  def resize(e):
   available=max(380,e.width-8)
   canvas.itemconfigure(window,width=available)
   for label in wrap_targets:
    if label.winfo_exists():label.configure(wraplength=max(260,available-120))
   update_scroll()
  canvas.bind('<Configure>',resize)
  data=getattr(self,'_complete_result',{})
  if not data:
   tk.Label(inner,text='分析完成后在这里查看各项指标值及其定义。',bg=WHITE,fg=MUTED,font=self._font(11)).pack(anchor='w',padx=15,pady=20)
  for i,(key,value) in enumerate(data.items()):
   bg=WHITE if i%2==0 else '#F0F6F8'
   row=tk.Frame(inner,bg=bg);row.pack(fill='x',padx=3,pady=3)
   chinese,meaning=summary_field_detail(self.module,key)
   top_row=tk.Frame(row,bg=bg);top_row.pack(fill='x',padx=12,pady=(10,2))
   title_box=tk.Frame(top_row,bg=bg);title_box.pack(side='left',fill='x',expand=True)
   title_label=tk.Label(title_box,text=chinese,bg=bg,fg=TEXT,font=self._font(10,True),anchor='w',justify='left',wraplength=590)
   title_label.pack(anchor='w');wrap_targets.append(title_label)
   key_label=tk.Label(title_box,text=str(key),bg=bg,fg=MUTED,font=self._font(9),anchor='w',wraplength=590)
   key_label.pack(anchor='w',pady=(2,0));wrap_targets.append(key_label)
   tk.Button(top_row,text='？',command=lambda k=key,t=chinese,m=meaning,owner=win:self.show_help(t+' ('+k+')',m,parent=owner),
             bg='#DDF1F7',fg=ACCENT,font=self._font(11,True),relief='flat',padx=8).pack(side='right')
   readable=(json.dumps(value,ensure_ascii=False,indent=2,default=str)
             if isinstance(value,(dict,list)) else self._format_output(key,value))
   value_label=tk.Label(row,text=readable,bg=bg,fg=ACCENT,font=self._font(10),justify='left',anchor='w',wraplength=590)
   value_label.pack(fill='x',padx=14,pady=(3,11));wrap_targets.append(value_label)
  tk.Button(win,text='关闭并返回分析结论',command=self._close_metrics,bg='#E1EFF3',fg=ACCENT,
            font=self._font(10,True),relief='flat',padx=16,pady=9).pack(anchor='e',padx=18,pady=(0,12))

 def _resize_input_scroll(self,event=None):
  """Keep a usable form width; horizontal scroll reveals everything on small screens."""
  if not getattr(self,'cv',None):return
  canvas_width=max(1,self.cv.winfo_width())
  self.cv.itemconfigure(self.canvas_id,width=max(canvas_width,410,self.form.winfo_reqwidth()))
  self.cv.configure(scrollregion=self.cv.bbox('all'))
  try:
   need_x=self.form.winfo_reqwidth()>canvas_width+7
   if need_x and not self.input_xscroll.winfo_ismapped():self.input_xscroll.grid()
   elif not need_x and self.input_xscroll.winfo_ismapped():self.input_xscroll.grid_remove()
  except tk.TclError:pass

 def _toggle_guide(self):
  if not getattr(self,'guide_body',None):return
  self.guide_open=not self.guide_open
  if self.guide_open:
   self.guide_body.pack(fill='x',padx=10,pady=(2,11))
   self.guide_toggle.config(text='▾  收起详细说明')
  else:
   self.guide_body.pack_forget()
   self.guide_toggle.config(text='▸  展开计算口径、输出与限制')

 def _build_guide(self,module):
  """Compact guide with real paragraph spacing and genuinely responsive wrapping."""
  guide=tk.Frame(self.form,bg='#F0F8F9',highlightbackground='#D4E7ED',highlightthickness=1)
  guide.pack(fill='x',padx=15,pady=(12,13))
  content=MODULE_STORIES[module]
  tk.Label(guide,text='本模块要点',bg='#F0F8F9',fg=ACCENT,
           font=self._font(12,True),anchor='w').pack(fill='x',padx=14,pady=(14,8))
  import re
  def extract(title):
   match=re.search(r'【'+re.escape(title)+r'】\s*(.*?)(?=【|\Z)',content,re.S)
   return re.sub(r'\s+',' ',match.group(1)).strip() if match else ''
  intro=extract('用它解决什么问题') or SPECS[module]['sub']
  when=extract('什么时候需要')
  notneed=extract('什么时候不需要')
  def preview(text,limit=50):
                                  
   sentence=text.strip().split('。',1)[0].strip(' 。；，、')
   if len(sentence)>limit:
    sentence=sentence[:limit].rstrip(' ，、；：')+'…'
   return sentence
  for title,body,color in [('实际作用',preview(intro),TEXT),
                           ('适用情况',preview(when),'#1D6860')]:
   if not body:continue
   block=tk.Frame(guide,bg='#F0F8F9');block.pack(fill='x',padx=14,pady=(0,9))
   tk.Label(block,text=title,bg='#F0F8F9',fg=ACCENT,font=self._font(10,True),anchor='w').pack(fill='x',pady=(0,2))
   label=tk.Label(block,text=body,bg='#F0F8F9',fg=color,font=self._font(10),anchor='w',justify='left',wraplength=305)
   label.pack(fill='x')
                                                                            
  self.guide_toggle=tk.Button(guide,text='▸  展开计算口径、输出与限制',command=self._toggle_guide,
        bg='#DCEFF3',fg=ACCENT,relief='flat',cursor='hand2',font=self._font(10,True),anchor='w',padx=12,pady=9)
  self.guide_toggle.pack(fill='x',padx=13,pady=(4,13))
  self.guide_body=tk.Frame(guide,bg=WHITE)
  self.guide_open=False
  parts=re.split(r'【([^】]+)】',content)
  for i in range(1,len(parts),2):
   heading=parts[i]
   body=parts[i+1].strip() if i+1<len(parts) else ''
   if not body:continue
                                                                                      
   body=re.sub(r'(?<!\n)\n(?!\n)',' ',body)
   section=tk.Frame(self.guide_body,bg=WHITE,highlightbackground='#E6EDF1',highlightthickness=1)
   section.pack(fill='x',padx=11,pady=(9,5))
   tk.Label(section,text=heading,bg=WHITE,fg=ACCENT,font=self._font(11,True),anchor='w').pack(fill='x',padx=14,pady=(13,7))
   label=tk.Label(section,text=body,bg=WHITE,fg=TEXT,font=self._font(10),justify='left',anchor='nw',wraplength=305)
   label.pack(fill='x',padx=14,pady=(0,15))
                                                                     

 def _metric_help_pair(self,i):
  key=self._metric_keys[i] if i<len(self._metric_keys) else ''
  label=self.metric_cards[i][1].cget('text')
  return ('指标：'+label,result_help(key) if key else '运行分析后这里显示本次计算的关键数值。统计意义需结合实验设计核对。')

 def _result_help_click(self,event):
  try:
                                                                            
   idx=self.result_text.index(f'@{event.x},{event.y}')
   line=self.result_text.get(idx+' linestart',idx+' lineend').strip()
   import re
   raw_field=re.search(r'（([A-Za-z_][A-Za-z0-9_]*)）\s*[：:]',line)
   found=re.match(r'^·\s*([^：:]+)[：:]',line)
   key=raw_field.group(1) if raw_field else (found.group(1).strip() if found else '')
   if not key and self.module=='数据质检':
    if '整行完全相同' in line:key='exact_duplicate_rows'
    elif '空白格子' in line:key='total_missing_cells'
    elif '本次表格' in line:key='rows'
   self.show_help('结果字段：'+key if key else '结果摘要怎么阅读',summary_field_detail(self.module,key)[1] if key else '右键字段所在行可查看解释。建议先看上方的“结果文件与阅读方法”；完整数据以 Excel 工作簿和 CSV 为准。')
  except Exception as exc:messagebox.showwarning('暂无法查看',str(exc))
  return 'break'

 def _bind_help(self,widget,getter):
  """Windows right-click; also control-click for laptop users."""
  def trigger(event):
   try:title,body=getter();self.show_help(title,body)
   except Exception as exc:messagebox.showwarning('说明暂不可用',str(exc))
   return 'break'
  widget.bind('<Button-3>',trigger,add='+')
  widget.bind('<Control-Button-1>',trigger,add='+')

 def _field_help_pair(self,module,key,label,kind):
  current=self.controls.get(key)
  visible=current.get('1.0','end-1c') if isinstance(current,tk.Text) else (current.get() if current is not None else '')
  raw=self.choice_maps.get(key,{}).get(visible,visible)
  if kind.startswith('choice:'):
   choices=[(v,CHOICE_CN.get(key,{}).get(v,v)) for v in kind.split(':',1)[1].split('|')]
  else:choices=[]
  return label,v10_help(module,key,label,kind,choices)

 def show_help(self,title,body,parent=None):
  """A non-modal help window; keep its invoking result window independent."""
  owner=parent if parent is not None and parent.winfo_exists() else self
  win=tk.Toplevel(owner);win.title('字段或参数说明 · '+str(title))
  win.geometry('760x590');win.minsize(460,340);win.configure(bg=WHITE)
  win.transient(owner)
  top=tk.Frame(win,bg='#EAF5F7');top.pack(fill='x')
  tk.Label(top,text='？ '+str(title),bg='#EAF5F7',fg=TEXT,font=self._font(15,True),wraplength=695,justify='left').pack(anchor='w',padx=20,pady=(18,3))
  tk.Label(top,text='定义、计算口径、用途和适用条件',bg='#EAF5F7',fg=MUTED,font=self._font(10)).pack(anchor='w',padx=23,pady=(0,16))
  frame=tk.Frame(win,bg=WHITE);frame.pack(fill='both',expand=True,padx=17,pady=(14,8))
  scroll=ttk.Scrollbar(frame,orient='vertical');scroll.pack(side='right',fill='y')
  words=tk.Text(frame,wrap='word',yscrollcommand=scroll.set,bg=WHITE,fg=TEXT,relief='flat',font=self._font(11),padx=8,pady=7,spacing1=3,spacing3=5)
  scroll.configure(command=words.yview);words.pack(fill='both',expand=True)
  words.insert('1.0',body);words.configure(state='disabled')
  bottom=tk.Frame(win,bg=WHITE);bottom.pack(fill='x',padx=24,pady=(3,16))
  tk.Button(bottom,text='关闭说明',command=win.destroy,bg='#E2E8F0',fg=TEXT,relief='flat',padx=18,pady=8).pack(side='right')
  self._help_windows.append(win)
  return win

 def open_output_tiers(self):
  """Three-level result browser. No file deletion, export changes or recalculation."""
  from ui_outputs102 import group_files
  if not self.last_output or not Path(self.last_output).is_dir():
   messagebox.showinfo('还没有结果','请先完成一次分析。');return
  win=tk.Toplevel(self);win.title('按用途查看文件')
  win.geometry('910x680');win.minsize(620,420)
  top=tk.Label(win,text='先看核心结果；需要核对时再看质量检查和运行记录',font=self._font(13,True))
  top.pack(fill='x',padx=16,pady=13)
  tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True,padx=13,pady=7)
  groups=group_files(self.last_output,self.module)
  for category,items in groups.items():
   frame=tk.Frame(tabs);tabs.add(frame,text=f'{category}（{len(items)}项）')
   box=tk.Listbox(frame,font=self._font(11),selectmode='browse',activestyle='none')
   scrollbar=ttk.Scrollbar(frame,orient='vertical',command=box.yview)
   scrollbar.pack(side='right',fill='y');box.pack(fill='both',expand=True,padx=10,pady=10)
   box.configure(yscrollcommand=scrollbar.set)
   for family in items:
    if len(family)>1:box.insert('end','图：'+family[0].stem+'  ['+' / '.join(f.suffix[1:].upper() for f in family)+']')
    else:box.insert('end',family[0].name)
   def open_selected(ev=None,b=box,files=items):
    selected=b.curselection()
    if not selected:return
    f=files[selected[0]][0]
    try:
     if sys.platform=='win32':os.startfile(str(f))
     elif sys.platform=='darwin':subprocess.Popen(['open',str(f)])
     else:subprocess.Popen(['xdg-open',str(f)])
    except Exception:messagebox.showinfo('本地文件路径',str(f),parent=win)
   box.bind('<Double-Button-1>',open_selected)
   tk.Button(frame,text='打开所选文件（双击也可以）',command=open_selected).pack(anchor='e',padx=12,pady=9)
  tk.Label(win,text='同一图的 PNG/PDF/SVG 合并成一项；所有原始文件仍保存在结果文件夹。',font=self._font(10)).pack(anchor='w',padx=18,pady=(0,10))

 def open_result_guide(self):
  """Show actual files and allow easy Windows opening; no need to read JSON."""
  if self.last_output and Path(self.last_output).is_dir():
   folder=Path(self.last_output)
   from ui_outputs102 import result_files
   names=sorted(result_files(folder),key=lambda p:(p.suffix.lower() not in ('.xlsx','.csv'),p.name))
   text=files_guide(self.module,[p for p in names if p.name!='阅读结果_从这里开始.txt'])
   win=tk.Toplevel(self);win.title('本次输出文件')
   self._result_popups.append(win)
   win.geometry('920x690');win.minsize(640,410);win.configure(bg=WHITE)
   tk.Label(win,text='📁  本次输出文件',bg=WHITE,fg=TEXT,font=self._font(16,True)).pack(anchor='w',padx=21,pady=(18,4))
   tk.Label(win,text='左侧选择文件，右侧显示用途、关键字段和阅读方法。双击文件用系统默认程序打开。',bg=WHITE,fg=MUTED,font=self._font(10),wraplength=800,justify='left').pack(anchor='w',padx=22,pady=(0,13))
   body=tk.PanedWindow(win,orient='horizontal',bg='#E2E8F0',sashwidth=5);body.pack(fill='both',expand=True,padx=14,pady=5)
   left=tk.Frame(body,bg=WHITE);body.add(left,minsize=200,width=275)
   tk.Label(left,text='文件列表',bg=WHITE,fg=TEXT,font=self._font(10,True)).pack(anchor='w',padx=10,pady=8)
   ls=tk.Listbox(left,selectmode='browse',font=self._font(10),activestyle='none',bg=WHITE,fg=TEXT,bd=0,highlightthickness=0)
   ls.pack(fill='both',expand=True,padx=10,pady=(0,12))
   for file in names:ls.insert('end',file.name)
   right=tk.Frame(body,bg=WHITE);body.add(right,minsize=325)
   tscroll=ttk.Scrollbar(right,orient='vertical');tscroll.pack(side='right',fill='y')
   words=tk.Text(right,yscrollcommand=tscroll.set,wrap='word',bg=WHITE,fg=TEXT,relief='flat',font=self._font(10),padx=16,pady=14,spacing1=4,spacing2=2,spacing3=9)
   tscroll.config(command=words.yview);words.pack(fill='both',expand=True)
   def insert(text):
    words.config(state='normal');words.delete('1.0','end');words.insert('1.0',text);words.config(state='disabled')
   insert(text)
   def select_file(event=None):
    sel=ls.curselection()
    if not sel:return
    file=names[sel[0]]
    extra=''
    if file.suffix.lower()=='.csv':
     try:
      import pandas as pd
      cols=pd.read_csv(file,nrows=0,encoding='utf-8-sig').columns
      extra='\n【这张表的字段】\n'
      for c in cols:
       chinese,desc=column_detail(file.name,c)
       extra+='\n'+c+'   —   '+chinese+'\n'+desc+'\n\n'
     except Exception as exc:extra='无法读取字段：'+str(exc)
    insert('【'+file.name+'】\n\n'+describe_file(file.name)+extra)
   ls.bind('<<ListboxSelect>>',select_file)
   def open_selected(event=None):
    sel=ls.curselection()
    if not sel:return
    file=names[sel[0]]
    try:
     if sys.platform=='win32':os.startfile(str(file))
     elif sys.platform=='darwin':subprocess.Popen(['open',str(file)])
     else:subprocess.Popen(['xdg-open',str(file)])
    except Exception as exc:messagebox.showerror('打开文件失败',str(exc),parent=win)
   ls.bind('<Double-Button-1>',open_selected)
   bottom=tk.Frame(win,bg=WHITE);bottom.pack(fill='x',padx=19,pady=(4,12))
   tk.Button(bottom,text='打开所选文件',command=open_selected,bg='#E0F2FE',fg=ACCENT,relief='flat',padx=12,pady=8).pack(side='left')
   tk.Button(bottom,text='打开结果文件夹',command=self.open_output,bg='#E2E8F0',fg=TEXT,relief='flat',padx=12,pady=8).pack(side='left',padx=8)
   tk.Button(bottom,text='关闭',command=win.destroy,bg='#E2E8F0',fg=TEXT,relief='flat',padx=18,pady=8).pack(side='right')
  else:
   self.show_help('文件怎么看',module_text(self.module)+'\n\n完成分析后打开“本次输出文件”，查看这次实际生成的指标表、图与质量检查。')

 def _wheel(self,e):
                                                                          
                                                                         
  widget=getattr(e,'widget',None)
  if widget is None:return
  delta=getattr(e,'delta',0)
  steps=(-max(1,round(abs(delta)/120)) if delta>0 else max(1,round(abs(delta)/120))) if delta else 0
  if getattr(e,'num',None)==4:steps=-1
  if getattr(e,'num',None)==5:steps=1
  if not steps:return
  if widget==self.cv or str(widget).startswith(str(self.form)):
   self.cv.yview_scroll(steps,'units')
   return 'break'
  if str(widget).startswith(str(self.graph)):
   self.figure_scroll.yview_scroll(steps,'units')
   return 'break'

 def _protect_combobox_wheel(self,combo):
  """Stop the Tk combobox class from changing selections on a wheel scroll.

  A handler bound to the root with bind_all is too late in Tk's bindtags:
  the combobox class may have already written into its StringVar and
  invalidated results.  Bind directly to every real Combobox instance.
  """
  for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):
   combo.bind(sequence,lambda event:self._combo_wheel(event),add=False)

 def _combo_wheel(self,event):
                                                                        
                                                                    
  self._wheel(event)
  return 'break'

 def _freeze_form_inputs(self,freeze):
  """Prevent mid-computation edits; restore previous disabled states."""
  if freeze:
   if self._locked_inputs:return
   for key,control in self.controls.items():
    widget=(control if isinstance(control,tk.Text) else getattr(self,'_control_widgets',{}).get(key))
    if widget is None or not widget.winfo_exists():continue
    try:
     state=str(widget.cget('state'))
     if state not in ('normal','readonly'):continue
     self._locked_inputs.append((widget,state))
     widget.configure(state='disabled')
    except (tk.TclError,AttributeError):pass
   return
  for widget,state in self._locked_inputs:
   try:
    if widget.winfo_exists():widget.configure(state=state)
   except tk.TclError:pass
  self._locked_inputs.clear()

 def _make_preview(self):
  self.preview_info=tk.Label(self.preview,text='请选择 CSV / Excel / 图像 / 视频，查看文件预览',bg=WHITE,fg=MUTED,font=self._font(10),wraplength=330,justify='left');self.preview_info.pack(anchor='w',padx=10,pady=10)
  wrapper=tk.Frame(self.preview,bg=WHITE);wrapper.pack(fill='both',expand=True,padx=6,pady=6)
  self.table=ttk.Treeview(wrapper,show='headings',height=12)
  sy=ttk.Scrollbar(wrapper,orient='vertical',command=self.table.yview);sx=ttk.Scrollbar(wrapper,orient='horizontal',command=self.table.xview)
  self.table.configure(yscroll=sy.set,xscroll=sx.set)
  self.table.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew');wrapper.grid_rowconfigure(0,weight=1);wrapper.grid_columnconfigure(0,weight=1)
  self.thumbnail=tk.Label(self.preview,bg=WHITE);self.thumbnail.pack(padx=10,pady=5)

 def _invalidate_current_results(self,reason='输入或设置已变化，请重新开始分析。'):
  """Never show a previous file's metrics, figures or tables as current data."""
  if self.busy:
   self._changed_while_running=True
   return
  for win in self._result_popups:
   try:
    if win.winfo_exists():win.destroy()
   except tk.TclError:pass
  self._result_popups.clear()
  self.last_output=None
  self._complete_result={}
  self._result_snapshot=None
  self.figures=[];self.figure_index=0;self.figure_ref=None
  self._metric_keys=[]
  for value,label in getattr(self,'metric_cards',[]):
   value.configure(text='—');label.configure(text='等待分析')
  try:
   self._close_metrics()
  except (tk.TclError,AttributeError):pass
  for child in self.all_results_inner.winfo_children():child.destroy()
  if hasattr(self,'detail_tree'):
   self.detail_tree.delete(*self.detail_tree.get_children())
   self.detail_tree['columns']=()
   self.detail_selector.configure(values=[])
   self.detail_table_var.set('')
   self.detail_info.configure(text='当前输入尚未生成新结果。请先运行分析。')
  self.figures=[]
  self._show_figure()
  self.project_nav_button.pack_forget()
  self.result_head.configure(text='尚未运行当前输入')
  self._set_result(reason+'\n\n之前的结果文件仍保留在磁盘；新计算完成后才会显示新的摘要、图表和 CSV。')
  self.status.configure(text='当前输入已变化 · 等待重新分析')
  self._refresh_floating_results()

 def _input_changed(self,field):
  if self._suspend_invalidation:return
  control=self.controls.get(field)
  if control is None:return
  current=(control.get('1.0','end-1c') if isinstance(control,tk.Text) else control.get())
  if self._observed_values.get(field)==current:return                      
  self._observed_values[field]=current
                                                                         
                                                                           
  if (field=='file' and self.module=='视频追踪') or (field=='video_file' and self.module=='轨迹人工修正'):
   self._suspend_invalidation=True
   try:
    derived=(('seed_file','reference_file','motion_primary_point','motion_reference_point','pair_point_a','pair_point_b','motion_pairs')
       if self.module=='视频追踪' else ('corrections_file','motion_primary_point','motion_reference_point','pair_point_a','pair_point_b','motion_pairs'))
    for key in derived:
     widget=self.controls.get(key)
     if isinstance(widget,tk.StringVar):
      widget.set('');self._observed_values[key]=''
     elif isinstance(widget,tk.Text):
      widget.delete('1.0','end');self._observed_values[key]=''
    if hasattr(self,'video_mode_status') and self.module=='视频追踪':
     self.video_mode_status.configure(text='已更换视频。请打开视频标点器，为这段视频重新选择真实特征点并保存。不会沿用上一个视频的点。')
   finally:self._suspend_invalidation=False
  self._invalidate_current_results('已修改输入：'+str(field)+'。右侧旧结果已清空，避免误认为当前输入的计算结果。')
  if field in ('behavior_force_file',):
   self.after_idle(self._refresh_conditional_fields)
  if field in ('file','video_file'):
   self._clear_preview()
   self.preview_info.configure(text='已切换输入文件，请核对新的文件路径与预览，再开始分析。')

 def _install_input_change_watchers(self):
  """React only to real changes of form values, not scroll/re-layout."""
  self._observed_values={}
  for key,control in self.controls.items():
   if isinstance(control,tk.Variable):
    self._observed_values[key]=control.get()
    control.trace_add('write',lambda *_unused,k=key:self._input_changed(k))
   elif isinstance(control,tk.Text):
    self._observed_values[key]=control.get('1.0','end-1c')
    def changed(event,widget=control,k=key):
     if not widget.edit_modified():return
     widget.edit_modified(False)
     self._input_changed(k)
    control.bind('<<Modified>>',changed,add='+')
    control.edit_modified(False)

 def _build_video_quick_start(self):
  if self.module not in ('视频追踪','轨迹人工修正'):return
  panel=tk.Frame(self.form,bg='#ECF7FA');panel.pack(fill='x',padx=14,pady=(4,12))
  heading=('第一步：选择视频并在画面中标记要跟踪的部位' if self.module=='视频追踪'
           else '第一步：在原视频中核对并纠正已有轨迹')
  tk.Label(panel,text=heading,bg='#ECF7FA',fg='#155E75',anchor='w',
           font=self._font(11,True)).pack(fill='x',padx=12,pady=(9,5))
  tk.Button(panel,text='⊕ 打开视频 · 放大标点 / 逐帧修正',command=self.open_video_point_editor,
            bg='#146B82',fg='white',relief='flat',font=self._font(11,True),padx=8,pady=10).pack(fill='x',padx=12)
  description=('先选择视频，在首帧点击实际可见的部位并命名，例如 body、tip 或 P1；保存后自动回填标注 CSV，并选择 LK 自动追踪。不是每帧都手动点。'
         if self.module=='视频追踪' else '选择此前追踪得到的坐标 CSV 和同一段原视频；在错误帧直接点击正确位置，保存后自动回填人工修正表。')
  self.video_mode_status=tk.Label(panel,text=description,bg='#ECF7FA',fg='#516675',wraplength=345,
      justify='left',anchor='w',font=self._font(10))
  self.video_mode_status.pack(fill='x',padx=12,pady=(7,12))

 def _make_input_section(self,title,expanded=False):
  outer=tk.Frame(self.form,bg=WHITE)
  outer.pack(fill='x',padx=9,pady=(2,3))
  if title=='基础输入':
   tk.Label(outer,text='基础输入 · 一般只需填写这里',bg=WHITE,fg=ACCENT,
       font=self._font(11,True),anchor='w').pack(fill='x',padx=8,pady=(8,3))
   body=tk.Frame(outer,bg=WHITE);body.pack(fill='x')
   return {'outer':outer,'body':body,'button':None,'expanded':True,'title':title}
  state={'expanded':expanded}
  body=tk.Frame(outer,bg=WHITE)
  def toggle():
   state['expanded']=not state['expanded']
   if state['expanded']:body.pack(fill='x')
   else:body.pack_forget()
   button.configure(text=('▾  ' if state['expanded'] else '▸  ')+title)
   self._resize_input_scroll()
  button=tk.Button(outer,text=('▾  ' if expanded else '▸  ')+title,
      command=toggle,bg='#ECF6F8',fg=ACCENT,relief='flat',anchor='w',padx=11,pady=9,
      font=self._font(10,True))
  button.pack(fill='x',padx=6,pady=(3,1))
  if expanded:body.pack(fill='x')
  state.update({'outer':outer,'body':body,'button':button,'title':title})
  return state

 def switch(self,module):
  if self.busy:return
  self._suspend_invalidation=True
  self._invalidate_current_results('已切换到「'+module+'」，请设置此模块的实验输入。')
  if getattr(self,'metric_open',False):self._toggle_metrics()
  self.module=module; spec=SPECS[module];self.heading.config(text=('✿  ' if self._ui_theme=='粉色配色' else '')+display_name(module));self.subtitle.config(text=spec['sub'])
  for k,b in self.nav.items():b.config(bg=self.nav_active_bg if k==module else self.nav_bg,fg='white' if k==module else '#CBD5E1')
  if self.orbit_nav is not None:self.orbit_nav.set_active(module)
  for c in self.form.winfo_children():c.destroy()
  self.controls={};self.choice_maps={};self._three_d_input_widgets=[];self._control_widgets={};self._project_field_frames={};self._project_field_order=[];self._project_last_kind=None
  self.guide_body=None
  self._integrated_advanced_open=False
                                                                              
  if module in ('视频追踪','轨迹人工修正'):
   self._build_video_quick_start()
  if module=='轨迹人工修正':
   tk.Label(self.form,text='连续几十帧跟错？不要逐帧手改：返回【视频追踪】，在错误开始处或再次清楚看见目标的帧，为同名点新增人工锚点，重新运行 LK 自动追踪。本模块适合少量离散错误。',wraplength=350,justify='left',bg='#F2F7FB',fg=TEXT,font=self._font(10),padx=12,pady=10).pack(fill='x',padx=12,pady=5)
  if module in MODULE_STORIES:self._build_guide(module)
  self._v10_sections={};self._v10_field_frames={};self._v10_order=[]

  fields=list(spec['fields'])+([f for f in FIGURE_FIELDS if module!='论文绘图' or f[0] not in ('plot_xlabel','plot_ylabel')] if module not in NO_FIGURE else [])
                                                          
  _rank={'基础输入':0}
  def _order(f):
   section=v10_field_group(module,f[0]);return (_rank.get(section,1),list(V10_GROUPS.get(module,{})).index(section) if section in V10_GROUPS.get(module,{}) else 99)
  fields.sort(key=_order)
  for key,label,kind,default in fields:
   group=v10_field_group(module,key)
   if group not in self._v10_sections:
    self._v10_sections[group]=self._make_input_section(group,expanded=group in ('基础输入','当前任务的输入与输出'))
   holder=self._v10_sections[group]['body']
   frame=tk.Frame(holder,bg=WHITE);frame.pack(fill='x',padx=9,pady=(4,7))
   self._v10_field_frames[key]=frame;self._v10_order.append(key)
   if module=='项目工作流':
    self._project_field_frames[key]=frame;self._project_field_order.append(key)
   headrow=tk.Frame(frame,bg=WHITE);headrow.pack(fill='x',pady=(0,5))
   label_widget=tk.Label(headrow,text=label,bg=WHITE,fg=TEXT,font=self._font(10,True),anchor='w',justify='left',wraplength=300)
   label_widget.pack(side='left',fill='x',expand=True)
   getter=lambda m=module,k=key,l=label,t=kind:self._field_help_pair(m,k,l,t)
   self._bind_help(label_widget,getter)
   help_btn=tk.Button(headrow,text='？',command=lambda g=getter:self.show_help(*g()),bg='#E0F2FE',fg=ACCENT,relief='flat',padx=7,pady=1,cursor='question_arrow',font=self._font(10,True))
   help_btn.pack(side='right',padx=(4,0));self._bind_help(help_btn,getter)
   r=tk.Frame(frame,bg=WHITE);r.pack(fill='x')
   if kind=='checkbox':
    var=tk.StringVar(value=default)
    w=tk.Checkbutton(r,variable=var,onvalue='yes',offvalue='no',bg=WHITE,fg=TEXT,
                     activebackground=WHITE,anchor='w',font=self._font(10,True),
                     text='启用额外三维计算（只有双摄像机或已知刚体几何才勾选）',
                     command=self._refresh_3d_inputs)
    w.pack(fill='x');self.controls[key]=var
    self._control_widgets[key]=w;self._protect_combobox_wheel(w)
    self._bind_help(w,getter)
   elif kind=='multi':
    widget=tk.Text(r,height=3,bg='#F8FAFC',fg=TEXT,font=self._font(10),relief='solid',bd=1,insertbackground=TEXT,wrap='none',width=32)
    widget.pack(fill='x');widget.insert('1.0',default);self.controls[key]=widget
    self._bind_help(widget,getter)
   elif kind.startswith('choice:'):
    raw_options=kind.split(':',1)[1].split('|')
    translations=CHOICE_CN.get(key,{})
    shown=[translations.get(v,v) for v in raw_options]
    var=tk.StringVar(value=translations.get(default,default))
    w=ttk.Combobox(r,textvariable=var,values=shown,state='readonly')
    w.pack(fill='x');self.controls[key]=var
    self._control_widgets[key]=w;self._protect_combobox_wheel(w)
    self._bind_help(w,getter)
    self.choice_maps[key]={translations.get(v,v):v for v in raw_options}
    if key in ('pipeline_kind','pipeline_table_stats','pipeline_integrated_stats','pipeline_integrated_opt','pipeline_integrated_sync','pipeline_integrated_image_confirm') and module=='项目工作流':
     w.bind('<<ComboboxSelected>>',lambda e:self._refresh_project_inputs(),add='+')
    if key=='reconstruction_3d':w.bind('<<ComboboxSelected>>',lambda e:self._refresh_3d_inputs(),add='+')
    if key in ('stat_method','tracking_mode','filter'):
     w.bind('<<ComboboxSelected>>',lambda e:self._refresh_conditional_fields(),add='+')
    if key in THREE_D_KEYS:self._three_d_input_widgets.append((key,w,frame))
   elif kind=='column':
    var=tk.StringVar(value=default);w=ttk.Combobox(r,textvariable=var,values=[]);w.pack(fill='x');self.controls[key]=var
    self._control_widgets[key]=w;self._protect_combobox_wheel(w)
    self._bind_help(w,getter)
   else:
    var=tk.StringVar(value=default);w=ttk.Entry(r,textvariable=var);w.pack(side='left',fill='x',expand=True);self.controls[key]=var;self._control_widgets[key]=w
    self._bind_help(w,getter)
    if key in THREE_D_KEYS:self._three_d_input_widgets.append((key,w,frame))
    if key=='roi':tk.Button(r,text='框选分析区域 ROI',command=self.pick_roi,bg='#E0F2FE',fg=ACCENT,relief='flat',padx=7,pady=6).pack(side='right',padx=(8,0))
    if kind in ('file','video','metadata','image_or_folder','folder','pipeline_input'):
     tk.Button(r,text='浏览…',command=lambda k=key,t=kind:self.browse(k,t),bg='#E9F1F5',fg=TEXT,relief='flat',padx=11,pady=6,cursor='hand2').pack(side='right',padx=(8,0))
     if kind=='pipeline_input':
      tk.Button(r,text='文件夹',command=lambda k=key:self.browse(k,'folder'),bg='#E4F4EF',fg=TEXT,relief='flat',padx=8,pady=6).pack(side='right',padx=(7,0))
     if kind=='image_or_folder':tk.Button(r,text='文件夹',command=lambda k=key:self.browse(k,'folder'),bg='#F1F5F9',fg=MUTED,relief='flat',padx=9,pady=6).pack(side='right',padx=(7,0))
  if module in ('视频追踪','轨迹人工修正'):
   self._refresh_3d_inputs()
  if module in ('视频追踪','轨迹人工修正'):
   calib_area=tk.Frame(self.form,bg='#EFF5FC')
   def toggle_calib():
    if calib_area.winfo_manager():calib_area.pack_forget();calib_btn.configure(text='▸  展开三维标定与演示（二维通常不用）')
    else:calib_area.pack(fill='x',padx=20,pady=(3,12));calib_btn.configure(text='▾  收起三维标定与演示')
   calib_btn=tk.Button(self.form,text='▸  展开三维标定与演示（二维通常不用）',command=toggle_calib,relief='flat',bg='#E6EEF3',fg=ACCENT,font=self._font(10,True),padx=12,pady=8)
   calib_btn.pack(fill='x',padx=20,pady=(4,6))
   tk.Label(calib_area,text='三维实验帮助（二维模式无需操作此区域）',bg='#EFF5FC',fg='#164A6B',font=self._font(11,True)).pack(anchor='w',padx=10,pady=(10,3))
   tk.Label(calib_area,text='单目普通视频只能得到二维投影；双相机配对可三角测量；已知刚体CAD尺寸可估计6自由度位姿。不可凭一条二维轨迹自动制造深度。',
        bg='#EFF5FC',fg=TEXT,justify='left',wraplength=345,font=self._font(10)).pack(fill='x',padx=10,pady=6)
   tk.Button(calib_area,text='◈ 双相机棋盘格标定向导…',command=self.open_stereo_calibration,
        bg='#D7ECFB',fg='#155479',relief='flat',padx=9,pady=9).pack(fill='x',padx=10,pady=(4,8))
   tk.Button(calib_area,text='📂 打开合成左右相机示例文件夹',command=self.open_stereo_samples,
        bg='#E2F4ED',fg='#126355',relief='flat',padx=9,pady=9).pack(fill='x',padx=10,pady=(0,12))
  if module=='公式优化':
   tk.Label(self.form,text='公式示例：sin(x)+sqrt(y) ；log(x) 是自然对数；x**2 是平方。\n分段：where(x<2, (x-1)**2, sqrt(x))；可以直接复制修改。\n角度默认用弧度：sin(pi/2)=1。除数不能为零，对数参数必须大于零。',
       bg='#EEF8FA',fg=TEXT,justify='left',wraplength=325,padx=12,pady=12,font=self._font(11)).pack(fill='x',padx=20,pady=8)
  tips={
    '批量力学':'把一整个文件夹的力学测试表格逐份计算，再合成总表。先看任意一个文件，确认单位、拉力方向和开头是否真正没有受力。文件表头不一样时会尝试匹配常见叫法，无法确认就提示你。',
    '高级统计':'请按实验设计选择配对、多组或混合效应，不要依据检验后的 p 值事后更换方法。',
    '轨迹人工修正':'修正追踪点：先选择已有轨迹 CSV 和原视频，再点击顶部「打开视频」在对应帧点击真实特征点；保存后自动填入人工坐标 CSV。框选 ROI 只用于限定识别区域，不是修正单个坐标。原始轨迹不会被覆盖。',
    '力学分析':'建议：先确认力传感器零点偏移，再指定拉离过程分析时间窗；若数据包含加载与拉离循环，必须明确时间窗或填写循环编号。',
    '视频追踪':'LK 多点模式优先在视频画面中标出真实特征点；不需要框选 ROI。ROI 和 Otsu 只在旧轮廓模式常用。真实毫米位移必须先标定。检查实际追踪叠加视频。',
    '论文绘图':'推荐：使用顶刊实验风 + 论文经典配色；自定义轴标题后可直接另存 SVG。请核对图注、单位、独立样本 n。',
    '实验数据优化':'举例：每次改变频率和接触压力，测出速度与附着力。软件分析已有记录，再建议下次试什么设置；预测值必须通过新实验验证。',
    '独立样本统计':'例如制作 5 块 A 材料与 5 块 B 材料，每块测 3 次。软件先求每块的平均值，再比较 A、B 两组，不会把 30 次读数误认为 30 块材料。'}
  if module in tips and module not in MODULE_STORIES:
   tk.Label(self.form,text='操作建议 · '+tips[module],bg='#EAF5F7',fg='#135E69',
            justify='left',wraplength=365,padx=11,pady=9,font=self._font(10)).pack(fill='x',padx=20,pady=(3,10))
  if module in ('力学分析','批量力学','视频追踪','独立样本统计','论文绘图'):
   self.panel_axis_vars={f'plot_panel_{letter}_{axis}':tk.StringVar(value='')
                         for letter in 'abcd' for axis in ('xlabel','ylabel')}
   self.controls.update(self.panel_axis_vars)
   box=tk.Frame(self.form,bg=WHITE);box.pack(fill='x',padx=20,pady=(4,8))
   tk.Button(box,text='✎  自定义四联图各子图的 X / Y 轴标题…',command=self.edit_panel_axes,
             bg='#F1F5F9',fg=TEXT,relief='flat',padx=11,pady=9).pack(fill='x')
   tk.Label(box,text='a、b、c、d 可分别填写；留空保留各自物理量与单位，避免误标。',
            bg=WHITE,fg=MUTED,wraplength=320,justify='left',font=self._font(10)).pack(anchor='w',pady=(4,0))
  if module not in NO_FIGURE:
   hint=tk.Label(self.form,text='PNG / TIFF / PDF / SVG 均自动生成。结果页可直接另存高清 SVG；文字仍为可编辑矢量文字。',bg=WHITE,fg=MUTED,wraplength=320,justify='left',font=self._font(10))
   hint.pack(anchor='w',padx=20,pady=(0,10))
  f=tk.Frame(self.form,bg=WHITE);f.pack(fill='x',padx=20,pady=(15,7))
  outputlabel=tk.Label(f,text='结果保存位置（默认在本软件旁的【分析结果】文件夹）  ？',bg=WHITE,fg=TEXT,font=self._font(10,True),wraplength=300,justify='left')
  outputlabel.pack(anchor='w',pady=(0,5))
  output_getter=lambda:('输出文件夹','这是你希望软件把结果保存到哪里。\n\n填写什么？\n点击“选择…”挑一个已有文件夹，例如 D:/科研结果；默认直接保存在软件解压目录内的“分析结果”文件夹。每运行一次会自动新建带日期时间的子文件夹，不会覆盖上次结果。\n\n先看什么？\n运行后点击“本次输出文件”，不要先从 JSON 看起。')
  self._bind_help(outputlabel,output_getter)
  x=tk.Frame(f,bg=WHITE);x.pack(fill='x')
  output_entry=ttk.Entry(x,textvariable=self.output_var);output_entry.pack(side='left',fill='x',expand=True)
  self._bind_help(output_entry,output_getter)
  tk.Button(x,text='选择…',command=self.choose_output,bg='#E9F1F5',fg=TEXT,relief='flat',padx=10,pady=6).pack(side='left',padx=(7,0))
  output_hint=tk.Label(self.form,text='结果文件：'+spec['output']+'  （右键查看文件说明）',bg=WHITE,fg=MUTED,justify='left',wraplength=325,font=self._font(10))
  output_hint.pack(anchor='w',padx=20,pady=(8,25))
  self._bind_help(output_hint,lambda m=module:('结果文件都是什么？',module_text(m)+'\n\n具体怎么看：运行后点结果页的“本次输出文件是什么？怎么打开？”，会列出本次实际生成的文件和建议阅读顺序。'))
  if module=='项目工作流':self._refresh_project_inputs()
  else:self._refresh_conditional_fields()
  self.demo_button.configure(text='选择最近一次分析结果' if module=='分析结果整理' else '使用演示数据')
  self.cv.yview_moveto(0);self.preview_info.config(text=f'输入：{spec["input"]}\n提示：先使用演示数据，确认输出格式再加载自己的数据。');self._clear_preview()
  self._style_theme_widgets()
  self._install_input_change_watchers()
  self._suspend_invalidation=False

 def _refresh_conditional_fields(self):
  """Hide unrelated options without changing their values or numerical contracts."""
  module=self.module
  if module not in ('视频追踪','高级统计','信号处理','运动关系分析'):return
  frames=getattr(self,'_v10_field_frames',{})
  if not frames:return
  visible=set(frames)
  if module=='高级统计':
   method=self._cfg_choice('stat_method')
   if method=='uncertainty':
    visible={'stat_method','measurement','uncertainties'}
   else:
    visible-={'measurement','uncertainties'}
    if method!='mixed':visible.discard('batch_col')
    if method!='paired':visible.discard('bootstrap_seed')
  elif module=='视频追踪':
   tracking=self._cfg_choice('tracking_mode')
   if tracking=='point_lk':
    visible-=V10_GROUPS['视频追踪']['旧版轮廓识别专用（LK 模式通常不用）']
   elif tracking=='contour':
    visible-=set(['seed_file','lk_window_px','lk_pyramid','lk_fb_limit_px'])
  elif module=='信号处理':
   mode=self._cfg_choice('filter')
   if mode!='savgol':visible.discard('window')
   if mode!='lowpass':visible.discard('cutoff_hz')
  if module in ('视频追踪','运动关系分析'):
                                                                      
   sig=self.controls.get('behavior_force_file')
   if sig is None or not sig.get().strip():
    visible-={'behavior_force_time_col','behavior_force_value_col','behavior_force_shift_s','behavior_force_max_gap_s'}
  for f in frames.values():f.pack_forget()
  for key in self._v10_order:
   if key in visible and key in frames:frames[key].pack(fill='x',padx=9,pady=(4,7))
  for group,state in self._v10_sections.items():
   active=any(key in visible and v10_field_group(module,key)==group for key in frames)
   if active:state['outer'].pack(fill='x',padx=9,pady=(2,3))
   else:state['outer'].pack_forget()
  self._resize_input_scroll()

 def _toggle_integrated_advanced(self):
                                                                            
  section=self._v10_sections.get('多源图像与传感器（仅有对应数据才展开）')
  if section and section['button']:section['button'].invoke()

 def _refresh_project_inputs(self):
  """Only display controls relevant to the selected project task.
   categories remain collapsible, no computation-side key changes.
  """
  if self.module!='项目工作流' or 'pipeline_kind' not in self.controls:return
  raw=self.controls['pipeline_kind'].get()
  kind=self.choice_maps.get('pipeline_kind',{}).get(raw,raw)
  previous=getattr(self,'_project_last_kind',None)
  if previous is not None and previous!=kind and 'file' in self.controls:
   self.controls['file'].set('');self._clear_preview()
   self.preview_info.configure(text='已切换任务类型。请重新选择对应数据，或点击“使用演示数据”。')
  self._project_last_kind=kind
  core={'pipeline_kind','file'}
  integrated={'pipeline_integrated_response','pipeline_integrated_reference','pipeline_integrated_targets',
    'pipeline_integrated_max_frames','pipeline_integrated_stats','pipeline_integrated_opt',
    'pipeline_integrated_design','pipeline_integrated_goal','pipeline_integrated_opt_confirm',
    'pipeline_integrated_sync','pipeline_integrated_signal_time','pipeline_integrated_signal_value',
    'pipeline_integrated_signal_shift','pipeline_integrated_image_confirm',
    'pipeline_integrated_um_per_pixel','pipeline_integrated_image_mode','pipeline_integrated_image_threshold',
    'pipeline_confirm_id','pipeline_protocol_confirm','time_col','displacement_col','force_col',
    'time_unit','displacement_unit','force_unit','tension_sign','force_baseline',
    'baseline_fraction','baseline_start_s','baseline_end_s','baseline_manual_N',
    'pull_start_s','pull_end_s','motion_scale_confirmed','mm_per_pixel',
    'behavior_speed_threshold_px_s','behavior_min_dwell_s'}
  table={'pipeline_table_x','pipeline_table_y','pipeline_table_group','pipeline_table_chart','pipeline_table_stats','pipeline_table_sample','pipeline_confirm_id'}
  motion={'behavior_track_format','behavior_time_col','behavior_point_col','behavior_x_col','behavior_y_col',
   'behavior_source_unit','behavior_body','behavior_feet','behavior_substrate',
   'behavior_speed_threshold_px_s','behavior_min_dwell_s','climb_axis','mm_per_pixel','motion_scale_confirmed'}
  force={'pipeline_metric','pipeline_protocol_confirm','pipeline_confirm_id','condition_col','sample_col',
   'time_col','displacement_col','force_col','time_unit','displacement_unit','force_unit','tension_sign',
   'force_baseline','baseline_fraction','baseline_start_s','baseline_end_s','baseline_manual_N',
   'pull_start_s','pull_end_s'}
  visible=core|({'integrated':integrated,'table':table,'motion':motion,'force':force}.get(kind,set()))
                                                                              
  if kind=='integrated':
   if self._cfg_choice('pipeline_integrated_opt')!='yes':
    visible-={'pipeline_integrated_design','pipeline_integrated_goal','pipeline_integrated_opt_confirm'}
   if self._cfg_choice('pipeline_integrated_sync')!='yes':
    visible-={'pipeline_integrated_signal_time','pipeline_integrated_signal_value','pipeline_integrated_signal_shift'}
   if self._cfg_choice('pipeline_integrated_image_confirm')!='yes':
    visible-={'pipeline_integrated_um_per_pixel','pipeline_integrated_image_mode','pipeline_integrated_image_threshold'}
   if self._cfg_choice('pipeline_integrated_stats')!='yes':visible-={'pipeline_confirm_id'}
  if kind=='table' and self._cfg_choice('pipeline_table_stats')!='yes':
   visible-={'pipeline_table_sample','pipeline_confirm_id'}
  frames=getattr(self,'_project_field_frames',{})
  for key,frame in frames.items():
   frame.pack_forget()
  for key in self._project_field_order:
   if key in visible and key in frames:
    frames[key].pack(fill='x',padx=9,pady=(4,7))
  for title,state in self._v10_sections.items():
   has_content=any(key in visible and v10_field_group('项目工作流',key)==title for key in frames)
   if has_content:
    state['outer'].pack(fill='x',padx=9,pady=(2,3))
   else:state['outer'].pack_forget()
  self._resize_input_scroll()

 def _cfg_choice(self,key):
  value=self.controls[key].get() if key in self.controls else ''
  return self.choice_maps.get(key,{}).get(value,value)

 def open_stereo_calibration(self):
  if self.busy:return                                                    
  from stereo_calibration_gui84 import open_stereo_wizard
  def saved(p):
   v=self.controls.get('stereo_calibration_file')
   if v is not None:v.set(str(p))
  open_stereo_wizard(self,on_saved=saved)

 def open_video_point_editor(self):
  if self.busy:return                                                    
  if self.module not in ('视频追踪','轨迹人工修正'):return
  k='file' if self.module=='视频追踪' else 'video_file'
  video=self.controls.get(k).get().strip() if k in self.controls else ''
  if not video or not Path(video).is_file():
   video=filedialog.askopenfilename(title='请选择原始实验视频（坐标依照此原始画面）',
        filetypes=[('视频','*.avi *.mp4 *.mov *.mkv *.wmv'),('全部文件','*.*')])
   if not video:return
   self.controls[k].set(video)
  track=self.controls['file'].get().strip() if self.module=='轨迹人工修正' else None
  if track and Path(track).is_file():
   try:
    import pandas as pd
    cols=pd.read_csv(track,nrows=1).columns
    if 'point_id' not in cols:messagebox.showinfo('旧版轨迹提示','这是单目标旧版轨迹，请在标点器把当前点命名为 center。')
   except Exception:pass
  key='seed_file' if self.module=='视频追踪' else 'corrections_file'
  existing=self.controls[key].get().strip()
  try:
   from video_point_editor import VideoPointEditor
   VideoPointEditor(self,video,output_callback=lambda path:self._video_marks_saved(key,path),
       track_file=track if track and Path(track).is_file() else None,
       initial_csv=existing if existing and Path(existing).is_file() else None,
       calibration_callback=lambda scale:self.controls['mm_per_pixel'].set(f'{scale:.9g}'))
  except Exception as exc:messagebox.showerror('无法打开精细视频标注器',str(exc))

 def _video_marks_saved(self,key,path):
  """Save markers AND make it impossible to accidentally run legacy contour mode."""
  if self.busy:
   messagebox.showwarning('计算正在进行','请等待当前计算结束，再保存新的视频标注。');return
  self.controls[key].set(path)
  if self.module!='视频追踪':return
  translated=CHOICE_CN.get('tracking_mode',{}).get('point_lk','point_lk')
  self.controls['tracking_mode'].set(translated)
  try:
   import pandas as pd
   marks=pd.read_csv(path,encoding='utf-8-sig')
   names=list(dict.fromkeys(marks.point_id.astype(str)))
   candidates=['body','body_center','thorax','robot_center','身体','躯干','机身']
   body=next((n for n in names if n.lower() in [c.lower() for c in candidates]),None)
   if body and not self.controls['motion_primary_point'].get().strip():
    self.controls['motion_primary_point'].set(body)
   if body and not self.controls['motion_reference_point'].get().strip():
    self.controls['motion_reference_point'].set(body)
   if hasattr(self,'video_mode_status'):
    self.video_mode_status.config(text=(
      '✓ 标点已保存，已自动选择【人工点锚定 LK 光流】；不是旧版轮廓模式。\n'
      +'这次包含点：'+', '.join(names)+'。请核对“主要整体运动点名”是否为身体点；'
      +'P1/P2若标在翅膀上，不能当作身体速度。保存后请点击主窗口「开始分析」。'))
  except Exception as exc:
   if hasattr(self,'video_mode_status'):
    self.video_mode_status.config(text='已回填标点文件，但读取点名失败：'+str(exc))

 def edit_panel_axes(self):
  if self.busy:return                                                    
  """Edit scientific axes individually instead of overriding incompatible units."""
  if not hasattr(self,'panel_axis_vars'):return
  win=tk.Toplevel(self);win.title('四联图 · 分别设置 a / b / c / d 坐标轴标题')
  win.geometry('630x405');win.configure(bg=WHITE)
  win.transient(self);win.grab_set()
  tk.Label(win,text='四联图坐标轴文字',bg=WHITE,fg=TEXT,font=self._font(13,True)).pack(anchor='w',padx=22,pady=(18,4))
  tk.Label(win,text='每幅图的 X/Y 物理量可能不同，请仅修改你确定含义的标签。空白即保持默认。',
           bg=WHITE,fg=MUTED,font=self._font(10),wraplength=575).pack(anchor='w',padx=22,pady=(0,14))
  local={name:tk.StringVar(value=var.get()) for name,var in self.panel_axis_vars.items()}
  for letter in 'abcd':
   row=tk.Frame(win,bg=WHITE);row.pack(fill='x',padx=22,pady=8)
   tk.Label(row,text=f'子图 {letter}',width=8,bg=WHITE,fg=TEXT,font=self._font(10,True)).pack(side='left')
   for axis,title in (('xlabel','X 轴'),('ylabel','Y 轴')):
    tk.Label(row,text=title,bg=WHITE,fg=MUTED).pack(side='left',padx=(8,3))
    entry=ttk.Entry(row,textvariable=local[f'plot_panel_{letter}_{axis}'],width=23)
    entry.pack(side='left',fill='x',expand=True)
    self._bind_help(entry,lambda a=axis,let=letter:('子图 '+let+' '+('横轴' if a=='xlabel' else '纵轴')+'标题',
      '这里只修改当前子图显示的文字，不改变数据。\n\n例如填写 时间 (s) 或 拉力 (N)。\n\n不同子图通常不是同一物理量，若不确定应留空保留默认；修改轴标题不会帮你完成单位换算。'))
  buttons=tk.Frame(win,bg=WHITE);buttons.pack(fill='x',padx=22,pady=20)
  def save():
   for key,var in local.items():self.panel_axis_vars[key].set(var.get().strip())
   win.destroy()
  tk.Button(buttons,text='保存轴标题',command=save,bg=ACCENT,fg=WHITE,relief='flat',padx=20,pady=9).pack(side='right')
  tk.Button(buttons,text='取消',command=win.destroy,bg='#E2E8F0',fg=TEXT,relief='flat',padx=17,pady=9).pack(side='right',padx=10)

 def _get_cfg(self):
  values={k:(c.get('1.0','end-1c') if isinstance(c,tk.Text) else c.get().strip()) for k,c in self.controls.items()}
  cfg={k:self.choice_maps.get(k,{}).get(v,v) for k,v in values.items()}
  if self.module in ('视频追踪','轨迹人工修正'):
   from core.video_mode85 import normalized_video_config
                                                                                          
   cfg=normalized_video_config(cfg)
  return cfg

 def _refresh_3d_inputs(self):
  if self.module not in ('视频追踪','轨迹人工修正'):return
  enabled=(self.controls.get('enable_3d').get()=='yes') if 'enable_3d' in self.controls else False
  mode_raw=self.controls.get('reconstruction_3d').get() if 'reconstruction_3d' in self.controls else ''
  mode=self.choice_maps.get('reconstruction_3d',{}).get(mode_raw,mode_raw)
  for key,w,frame in getattr(self,'_three_d_input_widgets',[]):
   relevant=enabled and (key=='reconstruction_3d' or
            (mode=='stereo' and key in ('stereo_calibration_file','stereo_right_track_file','stereo_time_offset_s',
                                        'stereo_match_tolerance_s','stereo_max_reprojection_px','stereo_min_ray_angle_deg')) or
            (mode=='rigid_pnp' and key in ('stereo_calibration_file','rigid_geometry_file','stereo_max_reprojection_px')))
   try:
    if isinstance(w,ttk.Combobox):w.configure(state='readonly' if relevant else 'disabled')
    else:w.configure(state='normal' if relevant else 'disabled')
    frame.configure(bg=WHITE if relevant else '#F2F5F6')
   except tk.TclError:pass

 def open_stereo_samples(self):
  folder=BASE/'samples'/'双目标定演示'
  if not folder.is_dir():
   messagebox.showerror('没有找到合成演示文件',str(folder));return
  try:
   if sys.platform=='win32':os.startfile(str(folder))
   elif sys.platform=='darwin':subprocess.Popen(['open',str(folder)])
   else:subprocess.Popen(['xdg-open',str(folder)])
  except Exception as exc:
   messagebox.showinfo('合成样例文件位置',str(folder)+'\n\n请在文件管理器中打开上述路径。\n'+str(exc))

 def browse(self,key,kind):
  if self.busy:return                                                    
  if kind=='folder':p=filedialog.askdirectory(title='选择数据文件夹')
  else:
   filters={'video':[('视频文件','*.avi *.mp4 *.mov *.mkv'),('所有文件','*.*')],
            'metadata':[('分析记录','run_metadata.json'),('JSON','*.json')],
            'image_or_folder':[('图像文件','*.png *.jpg *.jpeg *.tif *.tiff *.bmp'),('所有文件','*.*')]}.get(kind,[('实验表格','*.csv *.tsv *.txt *.xlsx *.xlsm'),('所有文件','*.*')])
   if key=='stereo_calibration_file':
    filters=[('相机标定 JSON','*.json'),('所有文件','*.*')]
   elif key in ('stereo_right_track_file','rigid_geometry_file'):
    filters=[('轨迹或CAD CSV','*.csv'),('所有文件','*.*')]
   options={}
   if kind=='metadata' and self.module=='分析结果整理':
    initial_dir=Path(self.output_var.get()).expanduser()
    if not initial_dir.is_dir():initial_dir=OUT if OUT.is_dir() else APP_DIR
    options['initialdir']=str(initial_dir)
   p=filedialog.askopenfilename(title='选择原始数据文件',filetypes=filters,**options)
  if p:self.controls[key].set(p);self.preview_file(p)

 def choose_output(self):
  if self.busy:return                                                    
  path=filedialog.askdirectory(title='选择结果输出位置')
  if path:self.output_var.set(path)

 def use_demo(self):
  if self.busy:return                                                    
  if self.module=='分析结果整理':
   candidates=[]
   recent=getattr(self,'recent_completed_result',None)
   if recent:candidates.append(Path(recent))
   base=Path(self.output_var.get()).expanduser()
   if base.is_dir():
    candidates.extend(sorted((p for p in base.iterdir() if p.is_dir()),key=lambda p:p.stat().st_mtime,reverse=True))
   for folder in candidates:
    record=folder/'run_metadata.json'
    if not record.is_file() or not (folder/'result_summary.json').is_file() or (folder/'INCOMPLETE_RUN.txt').exists():continue
    try:
     info=json.loads(record.read_text(encoding='utf-8'))
     if info.get('module') in ('分析结果整理','写作辅助'):continue
    except (ValueError,OSError):continue
    self.controls['file'].set(str(folder))
    self.preview_info.configure(text='已选中分析结果目录：'+str(folder)+'\n点击“开始分析”后将在新的结果目录生成 Markdown 和 Word 草稿。')
    return
   messagebox.showinfo('尚无分析结果','请先完成一次分析；也可以点击“选择…”直接选已有结果文件夹中的 run_metadata.json。')
   return
  if self.module not in DEMO:
   if self.module=='公式优化':messagebox.showinfo('已就绪','公式优化已填好一组演示参数。直接点击“开始分析”。')
   else:messagebox.showinfo('演示数据','当前模块需要真实的上一阶段结果。')
   return
  if self.module=='项目工作流':
   raw=self.controls['pipeline_kind'].get()
   kind=self.choice_maps['pipeline_kind'].get(raw,raw)
   if kind=='integrated':
    p=BASE/'samples'/'多源科研项目'/'project_manifest.csv'
    for k,v in {'pipeline_integrated_response':'peak_force_N',
                'pipeline_integrated_stats':'yes','pipeline_confirm_id':'yes',
                'pipeline_protocol_confirm':'yes','force_baseline':'time_window',
                'baseline_start_s':'0','baseline_end_s':'0.15',
                'pull_start_s':'0.2','pull_end_s':'2',
                'pipeline_integrated_image_confirm':'yes',
                'pipeline_integrated_um_per_pixel':'2',
                'pipeline_integrated_signal_value':'value',
                'pipeline_integrated_opt':'no','pipeline_integrated_sync':'no'}.items():
     self.controls[k].set(v)
    messagebox.showinfo('多源合成项目',
        '已选择与软件配套的合成项目清单（实验、轨迹、力学、图像、传感器、其他测量）。\n'
        '演示确认只对配套合成数据成立。使用真实项目时必须重新核对物理试样、基线、图像标定与时间同步。')
   elif kind=='force':
    p=BASE/'samples'/'batch_force'
                                                                            
    for k,v in {'pipeline_protocol_confirm':'yes','pipeline_confirm_id':'yes',
                'time_col':'time_s','displacement_col':'displacement_mm','force_col':'force_N',
                'condition_col':'condition','sample_col':'sample_id',
                'tension_sign':'positive','force_baseline':'first_fraction','baseline_fraction':'0.05'}.items():
     self.controls[k].set(v)
    messagebox.showinfo('合成力学示例已预设',
       '仅对随软件提供的合成测试文件，使用已记录的拉力方向、基线策略和独立试样编号。\n\n'
       '换成自己的仪器数据时，必须重新核对规程；演示的确认不能证明真实数据适用。')
   elif kind=='motion':p=BASE/'samples'/'通用轨迹'/'demo_generic_points.csv'
   else:
    p=BASE/'samples'/'科研表格工作流'/'general_measurements.csv'
    for k,v in {'pipeline_table_x':'time_s','pipeline_table_y':'response',
                'pipeline_table_group':'condition','pipeline_table_chart':'折线图',
                'pipeline_table_stats':'no','pipeline_table_sample':'sample_id',
                'pipeline_confirm_id':'no'}.items():
     self.controls[k].set(v)
   self.controls['file'].set(str(p));self.preview_file(str(p));self._refresh_project_inputs()
   return
  if self.module=='批量力学':p=BASE/'samples'/'batch_force'
  elif self.module=='轨迹人工修正':
   messagebox.showinfo('操作说明','请先完成一次视频追踪，选择输出的 frame_trajectory.csv 与已填写人工坐标的“人工复核模板” CSV。');return
  else:p=BASE/'samples'/DEMO[self.module]
  self.controls['file'].set(str(p));self.preview_file(str(p))
  if self.module=='视频追踪':
   if 'enable_3d' in self.controls:self.controls['enable_3d'].set('no');self._refresh_3d_inputs()
   demo_anchor=BASE/'samples'/'demo_video_point_anchors.csv'
   if demo_anchor.exists():self.controls['seed_file'].set(str(demo_anchor))
   self.controls['tracking_mode'].set('人工点锚定 LK 光流' if 'tracking_mode' not in CHOICE_CN else CHOICE_CN['tracking_mode'].get('point_lk','point_lk'))
  if self.module=='多源同步':
   self.controls['file_b'].set(str(BASE/'samples'/'demo_signal_B.csv'))
   self.controls['time_b'].set('time_s');self.controls['value_b'].set('value')
   self.controls['shift_b_s'].set('-0.4')
  if self.module=='运动关系分析':
   self.controls['behavior_mode'].set(CHOICE_CN['behavior_mode']['generic'])
   self.controls['behavior_body'].set('')
   self.controls['behavior_feet'].set('')
   self.controls['behavior_substrate'].set('')
  if self.module=='论文绘图':
   self.controls['chart_x'].set('condition');self.controls['chart_y'].set('value');self.controls['chart_sample_id'].set('sample_id')
   self.controls['chart_xlabel'].set('实验表面');self.controls['chart_ylabel'].set('模拟响应 (a.u.)')
  if self.module=='实验数据优化':
   for k,v in {'parameters':'frequency_hz,preload_N','responses':'speed_mm_s,adhesion_N','goals':'max,max','weights':'0.5,0.5','group_col':'experiment_id','constraints':'adhesion_N>=0.2'}.items():
    c=self.controls[k];c.delete('1.0','end') if isinstance(c,tk.Text) else c.set(v)
    if isinstance(c,tk.Text):c.insert('1.0',v)

 def _clear_preview(self):
  for x in self.table.get_children():self.table.delete(x)
  self.table['columns']=();self.thumbnail.configure(image='');self.thumb_ref=None

 def preview_file(self,path):
  p=Path(path);self._clear_preview()
  try:
   if p.is_dir():
    members=sorted(x for x in p.iterdir() if x.is_file() and x.suffix.lower() in ('.csv','.xlsx','.xlsm','.tsv'))
    details=[f'数据文件夹：{len(members)} 份表格（这里只预检前 5 份）']
    if members and self.module=='批量力学':
     from core.common import read_table,identify_column,infer_source_unit
     for path0 in members[:5]:
      try:
       table0=read_table(path0,sheet='auto' if path0.suffix.lower() in ('.xlsx','.xlsm') else 0)
       found=[identify_column(table0.columns,k) for k in ('time_s','displacement_mm','force_N')]
       if any(x is None for x in found):
        details.append('⚠ '+path0.name+'：无法自动找到完整的时间/位移/力列')
       else:
        units=[infer_source_unit(found[i],q,d) for i,(q,d) in enumerate((('time','s'),('displacement','mm'),('force','N')))]
        details.append('✓ '+path0.name+'：'+', '.join(found)+' | '+'/'.join(units))
      except Exception as e:details.append('⚠ '+path0.name+'：'+str(e)[:80])
     details.append('开始分析后先查看 import_manifest.csv：全部文件的识别结果会记录在表里。')
    self.preview_info.config(text='\n'.join(details))
   elif p.suffix.lower() in ('.png','.jpg','.jpeg','.tif','.tiff','.bmp','.avi','.mp4','.mov','.mkv'):
    from PIL import Image,ImageTk
    if p.suffix.lower() in ('.avi','.mp4','.mov','.mkv'):
     import cv2
     capture=cv2.VideoCapture(str(p));ok,frame=capture.read();fps=capture.get(cv2.CAP_PROP_FPS);n=capture.get(cv2.CAP_PROP_FRAME_COUNT);capture.release()
     if not ok:raise ValueError('无法获取视频首帧')
     im=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));desc=f'视频预览 | {n:.0f} 帧 · {fps:.2f} FPS'
    else: im=Image.open(p).convert('RGB');desc=f'图像预览 | {im.width} × {im.height} pixel'
    im.thumbnail((345,245));photo=ImageTk.PhotoImage(im);self.thumb_ref=photo;self.thumbnail.configure(image=photo);self.preview_info.config(text=desc+'\n'+p.name)
   elif p.suffix.lower()=='.json':
    data=json.loads(p.read_text(encoding='utf-8'));self.preview_info.config(text='分析记录\n'+p.name+'\n'+str(data.get('module','')))
   else:
    from core.common import read_table
    d=read_table(p,sheet='auto' if p.suffix.lower() in ('.xlsx','.xlsm') else 0);cols=[str(c) for c in d.columns][:18]
    from core.common import identify_column,infer_source_unit
    aliases={'col_time_s':'time_s','time_col':'time_s','col_displacement_mm':'displacement_mm','displacement_col':'displacement_mm',
      'col_force_N':'force_N','force_col':'force_N','col_condition':'condition','condition_col':'condition',
      'col_sample_id':'sample_id','sample_col':'sample_id','col_value':'value','value_col':'value',
      'x_col':'x','y_col':'y','batch_col':'batch'}
    for field,canon in aliases.items():
     if field in self.controls and isinstance(self.controls[field],tk.StringVar):
      current=self.controls[field].get()
      if current not in cols and (current in (canon,'',field) or current.endswith('_N') or current.endswith('_s')):
       candidate=identify_column(d.columns,canon)
       if candidate:self.controls[field].set(candidate)
                                                                                    
    for key,canonical,kind in (('time_unit','time_s','time'),('displacement_unit','displacement_mm','displacement'),('force_unit','force_N','force')):
     if key in self.controls:
      column=identify_column(d.columns,canonical)
      if column:
       user_unit=self.controls[key].get()
       inferred=infer_source_unit(column,kind,user_unit)
       if inferred!=user_unit:self.controls[key].set(inferred)
    self.table['columns']=cols
    for c in cols:self.table.heading(c,text=c);self.table.column(c,width=108,stretch=False)
    for row in d.head(30).itertuples(index=False,name=None):self.table.insert('', 'end',values=[(f'{v:.6g}' if isinstance(v,(int,float)) and not isinstance(v,bool) else str(v)[:55]) for v in row[:len(cols)]])
    for key,var in self.controls.items():
     if key.startswith('col_') or key in ('batch_col','time_col','value_col','x_col','y_col','group_col','cycle_column','chart_x','chart_y','chart_group','chart_sample_id'):
                                                                       
      for f in self.form.winfo_children():
       for w in f.winfo_children():
        for v in w.winfo_children():
         if isinstance(v,ttk.Combobox) and str(v.cget('textvariable'))==str(var):v['values']=cols
    self.preview_info.config(text=f'表格预览 | {len(d):,} 行 × {len(d.columns)} 列\n显示前 30 行 · 已明确识别的列名和单位会自动带入；请人工核对')
  except Exception as exc:self.preview_info.config(text='预览失败：'+str(exc))

 def run(self):
  if self.busy:return
  try:cfg=self._get_cfg()
  except ValueError as exc:
   messagebox.showwarning('三维模式设置',str(exc));return
  m=self.module;output=self.output_var.get().strip()
  if m!='公式优化' and not (m=='高级统计' and cfg.get('stat_method')=='uncertainty') and not cfg.get('file'):
   messagebox.showwarning('需要输入文件','请先选择文件，或点击“使用演示数据”。');return
  if m=='视频追踪' and cfg.get('tracking_mode','point_lk')=='point_lk' and not cfg.get('seed_file'):
   messagebox.showwarning('缺少人工特征点','请先点击「打开视频 · 高倍精细标点」，为需要追踪的物理位置至少标记一个点。');return
  if m=='视频追踪' and cfg.get('tracking_mode')=='contour' and cfg.get('seed_file'):
   if not messagebox.askyesno('你已经标了人工点，仍要运行旧模式吗？',
      '当前选择的是【旧版明暗轮廓中心】，它不会使用你标注的 P1/P2。\n'
      '对于昆虫、翅膀或软体机器人，请选择人工点锚定 LK 光流。\n\n确定忽略人工点并运行旧模式吗？'):
    return
  if m=='轨迹人工修正' and not cfg.get('corrections_file'):
   messagebox.showwarning('缺少人工校正表','请选择人工填写后的坐标表 CSV');return
  if m=='多源同步' and not cfg.get('file_b'):
   messagebox.showwarning('需要第二个输入','多源同步必须选择 B 数据文件。');return
  if m in ('视频追踪','轨迹人工修正') and cfg.get('enable_3d')=='yes':
   if cfg.get('reconstruction_3d')=='stereo' and (not cfg.get('stereo_calibration_file') or not cfg.get('stereo_right_track_file')):
    messagebox.showwarning('双目三维需要补充文件','双目模式需要相机标定 JSON 和另一台相机的已追踪 CSV；若只想二维，请取消三维勾选。');return
   if cfg.get('reconstruction_3d')=='rigid_pnp' and (not cfg.get('stereo_calibration_file') or not cfg.get('rigid_geometry_file')):
    messagebox.showwarning('刚体PnP需要补充文件','PnP模式需要相机标定 JSON 和已知刚体三维点 CSV；若只想二维，请取消三维勾选。');return
  if not output:messagebox.showwarning('需要输出路径','请指定输出文件夹。');return
                                                                                
  self._invalidate_current_results('正在开始一次新的计算；之前的预览已撤下。')
  self._run_token+=1;token=self._run_token
  self._changed_while_running=False
  self._result_snapshot={'module':m,'file':cfg.get('file',''),'parameters':dict(cfg)}
  self.busy=True;self._start_monotonic=time.monotonic();self._freeze_form_inputs(True);self.run_btn.configure(text='计算中…',state='disabled');self.status.configure(text=f'正在处理：{m} · 输入保持只读')
  self._cancel_event=threading.Event();self.cancel_btn.configure(state='normal',text='请求停止（安全检查点）')
  self.view_tabs.select(self.results);self._set_result('计算运行中…\n\n视频或批量图像可能需要一些时间。程序正在本地处理，没有上传文件。')
  def task():
   try:
    from core.workflows import run_module
    out,result=run_module(m,cfg,output,cancel_event=self._cancel_event,
                  progress_callback=lambda stage:self._run_messages.put((token,'progress',stage,None)))
    self._run_messages.put((token,'success',out,result))
   except Exception as exc:
    self._run_messages.put((token,'error',str(exc),traceback.format_exc()))
  threading.Thread(target=task,daemon=True).start()
  self.after(100,self._poll_run_queue)

 def request_cancel(self):
  if not self.busy or self._cancel_event is None:return
  self._cancel_event.set()
  self.cancel_btn.configure(state='disabled',text='已请求停止')
  self.status.configure(text='正在等待下一安全检查点停止；当前耗时计算可能不会立即退出。')

 def _poll_run_queue(self):
                                                        
  if not self.busy:return
  try:token,kind,a,b=self._run_messages.get_nowait()
  except queue.Empty:
   self.after(100,self._poll_run_queue)
   return
  if token!=self._run_token:
   self.after(10,self._poll_run_queue)
   return
  if kind=='progress':
   elapsed=time.monotonic()-self._start_monotonic if self._start_monotonic else 0
   self.status.configure(text=f'进行中 · {elapsed:.0f}秒 · {a}（可请求停止）')
   self.after(80,self._poll_run_queue)
   return
  if self._changed_while_running:
   self.busy=False;self._freeze_form_inputs(False);self.cancel_btn.configure(state='disabled')
   self._invalidate_current_results('计算运行时输入发生修改：结果已另存，但不与当前输入绑定。请重新分析。')
   self.run_btn.configure(text='▶  开始分析',state='normal')
   messagebox.showwarning('输入在计算期间修改','本次运行不能视为当前输入的结果。请确认参数后重新分析。')
   return
  if kind=='success':self._done(a,b)
  else:self._failed(a,b)

 def _format_output(self,key,value):
  human=humanize_result_value(key,value)
  if human is not None:return human
  if isinstance(value,str) and value in RESULT_VALUE_NAMES_104:return RESULT_VALUE_NAMES_104[value]
  if key=='project_main_metric' and isinstance(value,str):
   display=RESULT_NAMES.get(value,column_detail('result_summary.json',value)[0])
   if not display.startswith('未收录字段（'):return display
  if isinstance(value,float):return f'{value:.7g}'
  if isinstance(value,(dict,list,tuple)):
   text=json.dumps(value,ensure_ascii=False,default=str)
   return text if len(text)<260 else text[:257]+'…（完整值见 JSON）'
  return str(value)

 def _render_result_metrics(self,results):
  for child in self.all_results_inner.winfo_children():child.destroy()
  for i,(key,value) in enumerate(results.items()):
   if key=='quality_warnings':continue
   title,meaning=summary_field_detail(self.module,key)
   line=tk.Frame(self.all_results_inner,bg=WHITE if i%2==0 else '#F1F7F9')
   line.pack(fill='x')
   info=lambda k=key,t=title,m=meaning:self.show_help(t+' ('+k+')',m)
   tk.Button(line,text='？',command=info,bg='#E0F2FE',fg=ACCENT,relief='flat',font=self._font(10,True),padx=6).pack(side='right',padx=5,pady=5)
   tk.Label(line,text=title,bg=line.cget('bg'),fg=TEXT,justify='left',anchor='w',wraplength=290,font=self._font(9,True)).pack(fill='x',padx=8,pady=(4,0))
   tk.Label(line,text=key,bg=line.cget('bg'),fg=MUTED,justify='left',anchor='w',wraplength=290,font=self._font(8)).pack(fill='x',padx=8)
   tk.Label(line,text=self._format_output(key,value),bg=line.cget('bg'),fg=ACCENT,justify='left',anchor='w',wraplength=310,font=self._font(10,True)).pack(fill='x',padx=8,pady=(0,5))
  self.all_results_scroll.yview_moveto(0)

 def _make_detail_view(self):
  header=tk.Frame(self.detail_tab,bg=WHITE);header.pack(fill='x',padx=8,pady=8)
  tk.Label(header,text='本次结果表格：',bg=WHITE,fg=TEXT,font=self._font(10,True)).pack(anchor='w')
  self.detail_table_var=tk.StringVar()
  self.detail_selector=ttk.Combobox(header,textvariable=self.detail_table_var,state='readonly')
  self.detail_selector.pack(fill='x',pady=4)
  self.detail_selector.bind('<<ComboboxSelected>>',lambda e:self._load_detail_table())
  tk.Button(header,text='？ 当前列定义',command=self._detail_column_help,bg='#E0F2FE',fg=ACCENT,relief='flat').pack(anchor='e')
  holder=tk.Frame(self.detail_tab,bg=WHITE);holder.pack(fill='both',expand=True,padx=8,pady=(0,8))
  self.detail_tree=ttk.Treeview(holder,show='headings',selectmode='browse')
  sy=ttk.Scrollbar(holder,orient='vertical',command=self.detail_tree.yview)
  sx=ttk.Scrollbar(holder,orient='horizontal',command=self.detail_tree.xview)
  self.detail_tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
  self.detail_tree.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
  holder.grid_rowconfigure(0,weight=1);holder.grid_columnconfigure(0,weight=1)
  self.detail_tree.bind('<Button-3>',self._detail_column_help)
  self.detail_info=tk.Label(self.detail_tab,text='计算完成后可以在这里直接查看 CSV 前 60 行，完整表仍在结果文件夹。',bg=WHITE,fg=MUTED,wraplength=335,justify='left')
  self.detail_info.pack(fill='x',padx=8,pady=(0,6))

 def _load_detail_table(self):
  if not self.last_output:return
  from ui_outputs102 import find_output_file
  name=self.detail_table_var.get();file=find_output_file(self.last_output,name)
  if not file.is_file():return
  try:
   import pandas as pd
   df=pd.read_csv(file,nrows=60,encoding='utf-8-sig')
   cols=list(df.columns.astype(str))
   self.detail_tree.delete(*self.detail_tree.get_children())
   self.detail_tree['columns']=cols
   for col in cols:
    zh,_=column_detail(name,col)
    self.detail_tree.heading(col,text=zh+' / '+col)
    self.detail_tree.column(col,width=190,minwidth=95,anchor='w')
   for row in df.itertuples(index=False,name=None):
    self.detail_tree.insert('', 'end', values=[self._format_output('',v)[:220] for v in row])
   self.detail_info.config(text=f'{name}：显示前 {len(df)} 行。列名上方为中文名称；选择或右键表头可查看详细解释。')
  except Exception as exc:self.detail_info.config(text='读取表格失败：'+str(exc))

 def _detail_column_help(self,event=None):
  name=self.detail_table_var.get()
  cols=list(self.detail_tree['columns'])
  if not cols:return
  col=cols[0]
  if event is not None:
   try:
    which=self.detail_tree.identify_column(event.x)
    ix=int(which.lstrip('#'))-1
    if 0<=ix<len(cols):col=cols[ix]
   except Exception:pass
                                                                          
  lines=[]
  for c in cols:
   zh,desc=column_detail(name,c)
   lines.append(c+' — '+zh+'\n'+desc)
  self.show_help('本次表格所有列的解释 / '+name,'\n\n'.join(lines))

 def _refresh_detail_tables(self):
  if not self.last_output:return
  from ui_outputs102 import result_files
  choices=[p.name for p in result_files(self.last_output) if p.suffix.lower()=='.csv']
  self.detail_selector.configure(values=choices)
  if choices:
   prioritize=['group_summary.csv','independent_specimens.csv','cycle_metrics.csv','column_quality.csv','predicted_candidates.csv']
   chosen=next((n for n in prioritize if n in choices),choices[0])
   self.detail_table_var.set(chosen)
   self._load_detail_table()

 def _set_result(self,s):
  self.result_text.configure(state='normal');self.result_text.delete('1.0','end');self.result_text.insert('1.0',s);self.result_text.configure(state='disabled')
  self._refresh_floating_results()

 def _make_graph_view(self):
  """Scroll the WHOLE figure page; export buttons remain reachable on short screens."""
  self.figure_scroll=tk.Canvas(self.graph,bg=WHITE,highlightthickness=0)
  self.figure_ybar=ttk.Scrollbar(self.graph,orient='vertical',command=self.figure_scroll.yview)
  self.figure_ybar.pack(side='right',fill='y')
  self.figure_scroll.pack(side='left',fill='both',expand=True)
  self.figure_scroll.configure(yscrollcommand=self.figure_ybar.set)
  body=tk.Frame(self.figure_scroll,bg=WHITE)
  self.figure_body=body
  self.figure_window=self.figure_scroll.create_window((0,0),window=body,anchor='nw')
  body.bind('<Configure>',lambda e:self.figure_scroll.configure(scrollregion=self.figure_scroll.bbox('all')))
  self.figure_scroll.bind('<Configure>',lambda e:self.figure_scroll.itemconfigure(self.figure_window,width=e.width))
  bar=tk.Frame(body,bg=WHITE);bar.pack(fill='x',padx=8,pady=(12,6))
  self.figure_title=tk.Label(bar,text='运行分析后在此预览输出图片',bg=WHITE,fg=TEXT,wraplength=280,font=self._font(10,True))
  self.figure_title.pack(side='left',fill='x',expand=True)
  tk.Button(bar,text='◀',command=lambda:self._turn_figure(-1),bg='#E9F1F5',relief='flat',padx=7).pack(side='right',padx=2)
  tk.Button(bar,text='▶',command=lambda:self._turn_figure(1),bg='#E9F1F5',relief='flat',padx=7).pack(side='right',padx=2)
  self.figure_canvas=tk.Label(body,bg=WHITE,fg=MUTED,text='将显示本次分析的 PNG 高清预览',wraplength=300)
  self.figure_canvas.pack(fill='x',padx=7,pady=(2,4))
  self.figure_note=tk.Label(body,text='原始矢量文件保存在本次结果文件夹',bg=WHITE,fg=MUTED,font=self._font(10),wraplength=335)
  self.figure_note.pack(pady=(0,8),padx=8)
  actions=tk.Frame(body,bg=WHITE);actions.pack(fill='x',padx=8,pady=(1,6))
  for name,action,bg,fg in (
      ('另存高清 SVG…',self.save_current_svg,'#155E75','white'),
      ('其他格式…',self.save_current_other,'#E0F2FE',ACCENT),
      ('放大查看',self.open_large_figure,'#D3EDF4',ACCENT)):
   tk.Button(actions,text=name,command=action,bg=bg,fg=fg,relief='flat',padx=5,pady=10,font=self._font(9,True)).pack(fill='x',padx=2,pady=3)
  actions2=tk.Frame(body,bg=WHITE);actions2.pack(fill='x',padx=5,pady=(0,16))
  tk.Button(actions2,text='打开图片文件夹',command=self.open_output,bg='#E0F2FE',fg=ACCENT,relief='flat',padx=8,pady=9,font=self._font(9)).pack(fill='x',padx=2,pady=3)
  tk.Button(actions2,text='使用结果重新绘图',command=self.redraw_from_result,bg='#E9F1F5',fg=TEXT,relief='flat',padx=8,pady=9,font=self._font(9)).pack(fill='x',padx=2,pady=3)

 def _selected_figure_sibling(self, extension):
  """Identify the exact vector/raster original of the currently selected preview."""
  if not self.figures:
   messagebox.showinfo('尚无图片','请先运行会输出图片的分析模块。')
   return None
  target=self.figures[self.figure_index].with_suffix('.'+extension.lower())
  if not target.is_file() or target.stat().st_size == 0:
   messagebox.showwarning('无对应格式','当前预览对应的文件未生成 '+extension.upper()+'；请检查分析日志。')
   return None
  return target

 def save_current_svg(self):
  """Copy the ORIGINAL SVG generated by the analysis to a chosen local path.
  Never convert the on-screen downsized PNG into a fake vector file.
  """
  self._save_current_format('svg')

 def save_current_other(self):
  if not self.figures:
   messagebox.showinfo('尚无图片','请先运行分析。')
   return
  win=tk.Toplevel(self);win.title('导出当前图 · 选择文件格式');win.geometry('390x185');win.configure(bg=WHITE)
  win.transient(self);win.grab_set()
  tk.Label(win,text='选择需要保存的原始图片格式',bg=WHITE,fg=TEXT,font=self._font(11,True)).pack(padx=16,pady=(15,8))
  var=tk.StringVar(value='pdf')
  ttk.Combobox(win,values=['pdf','svg','tiff','png'],textvariable=var,state='readonly',width=25).pack(pady=4)
  tk.Button(win,text='选择保存位置…',command=lambda:(win.destroy(),self._save_current_format(var.get())),
            bg=ACCENT,fg=WHITE,relief='flat',padx=15,pady=7).pack(pady=12)

 def _save_current_format(self,extension):
  source=self._selected_figure_sibling(extension)
  if source is None:return
  formats={'svg':('SVG 矢量图','*.svg'),'pdf':('PDF 矢量图','*.pdf'),
           'png':('PNG 高清位图','*.png'),'tiff':('TIFF 无损位图','*.tiff')}
  target=filedialog.asksaveasfilename(title='另存当前 '+extension.upper()+' 图片',
                      defaultextension='.'+extension,filetypes=[formats[extension]],
                      initialfile=source.name)
  if not target:return
  dest=Path(target)
  try:
   if source.resolve()!=dest.resolve():shutil.copy2(source,dest)
   messagebox.showinfo('保存成功',f'已保存 {extension.upper()} 原图：\n{dest}\n\nSVG/PDF 是矢量图；PNG/TIFF 的分辨率来自运行时所选 DPI。')
  except (OSError,PermissionError) as exc:
   messagebox.showerror('保存失败',str(exc))

 def redraw_from_result(self):
  if not self.last_output or not self.last_output.exists():
   messagebox.showinfo('尚无分析结果','请先运行分析后再尝试。');return
  from ui_outputs102 import result_files
  files=[p for p in result_files(self.last_output) if p.suffix.lower()=='.csv']
  if not files:
   messagebox.showinfo('没有 CSV 文件','当前结果未生成 CSV，可选择“论文绘图”并导入自己的数据表。');return
  path=filedialog.askopenfilename(title='选择需要重新绘图的结果 CSV',initialdir=str((self.last_output/'核心结果') if (self.last_output/'核心结果').is_dir() else self.last_output),
                                  filetypes=[('CSV 数据表','*.csv')])
  if not path:return
  self.switch('论文绘图')
  self.controls['file'].set(path);self.preview_file(path)
  from core.common import read_table
  data=read_table(path)
  cols=list(data.columns)
  numeric=[c for c in cols if __import__('pandas').api.types.is_numeric_dtype(data[c])]
  category=next((c for c in ('condition','group','category') if c in cols),None)
  sid=next((c for c in ('sample_id','specimen_id') if c in cols),None)
  self.controls['chart_x'].set(category or (numeric[0] if numeric else cols[0]))
  self.controls['chart_y'].set(next((c for c in numeric if c!=self.controls['chart_x'].get()),numeric[0] if numeric else ''))
  self.controls['chart_sample_id'].set(sid or '')
  self.controls['chart_type'].set('箱线散点图' if category and numeric else '散点图')
  self.view_tabs.select(self.preview)
  messagebox.showinfo('准备完成','已载入结果数据表。请先核对 X、Y、组别和独立样本编号，再选择图型和导出尺寸。')

 def _turn_figure(self,delta):
  if not self.figures:return
  self.figure_index=(self.figure_index+delta)%len(self.figures)
  self._show_figure()

 def _show_figure(self):
  if not self.figures:
   self.figure_title.configure(text='本次分析无图片输出')
   self.figure_canvas.configure(image='',text='可使用“论文绘图”制作自选图型。')
   self.figure_ref=None;return
  from PIL import Image,ImageTk
  p=self.figures[self.figure_index]
  with Image.open(p) as raw:
   image=raw.convert('RGB')
   available=self.figure_scroll.winfo_width()-30
   image.thumbnail((max(180,available),410))
  self.figure_ref=ImageTk.PhotoImage(image)
  self.figure_canvas.configure(image=self.figure_ref,text='')
  self.figure_title.configure(text=f' {self.figure_index+1}/{len(self.figures)}  ·  {p.stem}')
  self.figure_note.configure(text='预览为缩略图；点击『另存高清 SVG』保存原始矢量文件。')

 def open_large_figure(self):
  if not self.figures:return
  from PIL import Image,ImageTk
  file=self.figures[self.figure_index]
  win=tk.Toplevel(self);win.title('高清图放大查看 · '+file.name);win.geometry('1100x770');win.configure(bg=WHITE)
  self._result_popups.append(win)
  bar=tk.Frame(win,bg='#F1F7F9');bar.pack(fill='x')
  tk.Label(bar,text=file.name,bg='#F1F7F9',fg=TEXT,font=self._font(11,True)).pack(side='left',padx=14,pady=10)
  tk.Label(bar,text='按比例缩放 · 原始 PNG/矢量 PDF 位于结果文件夹',bg='#F1F7F9',fg=MUTED,font=self._font(10)).pack(side='right',padx=14)
  outer=tk.Frame(win,bg=WHITE);outer.pack(fill='both',expand=True,padx=9,pady=7)
  canvas=tk.Canvas(outer,bg=WHITE,highlightthickness=0)
  sy=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview);sx=ttk.Scrollbar(outer,orient='horizontal',command=canvas.xview)
  canvas.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
  canvas.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
  outer.grid_rowconfigure(0,weight=1);outer.grid_columnconfigure(0,weight=1)
  with Image.open(file) as f: original=f.convert('RGB')
  initial=min(1,980/original.width,650/original.height)
  zoom=tk.DoubleVar(value=round(initial*100))
  def draw(_=None):
   rate=max(.1,float(zoom.get())/100);w=max(1,int(original.width*rate));h=max(1,int(original.height*rate))
                                                                         
   if w*h>14000000:
    rate*=((14000000/(w*h))**.5);w=int(original.width*rate);h=int(original.height*rate)
   raster=original.resize((w,h),Image.Resampling.LANCZOS)
   image=ImageTk.PhotoImage(raster);canvas.delete('all');canvas.create_image(0,0,image=image,anchor='nw')
   canvas.image=image;canvas.configure(scrollregion=(0,0,w,h))
  actions=tk.Frame(win,bg=WHITE);actions.pack(fill='x',padx=12,pady=(2,13))
  tk.Label(actions,text='缩放比例',bg=WHITE,fg=TEXT).pack(side='left')
  tk.Scale(actions,from_=10,to=170,orient='horizontal',variable=zoom,command=draw,length=280,bg=WHITE,highlightthickness=0).pack(side='left',padx=8)
  tk.Button(actions,text='适合窗口',command=lambda:zoom.set(initial*100),bg='#E0F2FE',fg=ACCENT,relief='flat',padx=12,pady=7).pack(side='left')
  tk.Button(actions,text='关闭预览',command=win.destroy,bg='#F1F5F9',fg=TEXT,relief='flat',padx=12,pady=7).pack(side='right')
  zoom.trace_add('write',lambda *_:draw())
  draw()

 def open_run_reader(self):
  """Read the actual output table fields and axes in an independent scrollable dialog."""
  if not self.last_output:
   messagebox.showinfo('尚未生成','请先完成一次分析，再查看本次 CSV、Excel 与图片的实际解释。',parent=self);return
  from ui_outputs102 import find_output_file
  file=find_output_file(self.last_output,'本次结果怎么读_V10.1.md')
  if not file.is_file():
   messagebox.showinfo('本次暂无专用指南','该结果目录没有逐字段阅读文件。可在“本次输出文件”中查看现有文件，或重新运行生成专用说明。',parent=self);return
  dlg=tk.Toplevel(self);dlg.title('字段、图片与参数说明');dlg.geometry('940x700');dlg.minsize(540,400)
  panel=tk.Frame(dlg,bg=WHITE);panel.pack(fill='both',expand=True,padx=14,pady=12)
  tk.Label(panel,text='字段、图片与参数说明',font=self._font(14,True),bg=WHITE,fg=TEXT).pack(anchor='w',pady=(0,5))
  tk.Label(panel,text='查看输出文件的用途、常见列名与本次参数设置。',bg=WHITE,fg=MUTED,justify='left').pack(anchor='w',pady=(0,10))
  body=tk.Frame(panel,bg=WHITE);body.pack(fill='both',expand=True)
  text=tk.Text(body,wrap='word',font=self._font(10),bg=WHITE,fg=TEXT,relief='flat',padx=15,pady=12)
  vs=ttk.Scrollbar(body,orient='vertical',command=text.yview);text.configure(yscrollcommand=vs.set)
  text.pack(side='left',fill='both',expand=True);vs.pack(side='right',fill='y')
  import re
  text.tag_configure('title',font=self._font(13,True),foreground=TEXT,spacing1=12,spacing3=10)
  text.tag_configure('section',font=self._font(12,True),foreground=ACCENT,spacing1=16,spacing3=8)
  text.tag_configure('file',font=self._font(10,True),foreground=TEXT,spacing1=12,spacing3=5)
  text.tag_configure('item',lmargin1=15,lmargin2=24,spacing1=3,spacing3=3)
  text.tag_configure('field',font=self._font(10,True),foreground=TEXT)
  text.tag_configure('paragraph',spacing3=5)
  for raw in file.read_text(encoding='utf-8-sig').splitlines():
   line=raw.strip()
   if not line:continue
   if '未收录字段（' in line or '此列目前没有经过核实' in line:continue
   if line.startswith('|'):
    if line.startswith('|---') or '原始列名 |' in line:continue
    cells=[c.strip() for c in line.strip('|').split('|')]
    if len(cells)>=2:line='- '+cells[0]+'：'+cells[1]
    else:continue
   heading=re.match(r'^(#{1,3})\s+(.*)',line)
   if heading:
    depth=len(heading.group(1));content=heading.group(2)
    text.insert('end',content+'\n',('title' if depth==1 else 'section' if depth==2 else 'file',))
    continue
   is_item=line.startswith(('- ','• '))
   line=re.sub(r'`([^`]*)`',r'\1',line)
   line=line.replace('**','')
   if is_item:
    line='• '+line[2:]
   where=text.index('end-1c')
   text.insert('end',line+'\n',('item' if is_item else 'paragraph',))
   if is_item:
    colon=line.find('：')
    if colon>0:
     text.tag_add('field',where,f'{where}+{colon}c')
  text.configure(state='disabled')
  tk.Button(panel,text='关闭',command=dlg.destroy,bg='#E3EDF1',fg=TEXT,font=self._font(10),relief='flat',padx=18,pady=8).pack(anchor='e',pady=(10,0))

 def open_project_navigation(self):
  """Open a local offline HTML page linked to actual stage folders."""
  import webbrowser
  path=Path(self.last_output or '')/'项目结果导航.html'
  if not path.is_file():
   messagebox.showwarning('尚未生成','请先成功运行一次项目工作流。');return
  try:
   if sys.platform=='win32':os.startfile(str(path))
   else:webbrowser.open(path.resolve().as_uri())
  except OSError as exc:messagebox.showwarning('无法打开','请在结果文件夹中双击 项目结果导航.html。\n'+str(exc))

 def _done(self,out,result):
  self.busy=False;self._freeze_form_inputs(False);self.cancel_btn.configure(state='disabled',text='请求停止（安全检查点）');self.last_output=Path(out);
  if self.module!='分析结果整理':self.recent_completed_result=Path(out)
  elapsed=(time.monotonic()-self._start_monotonic) if self._start_monotonic else None
  self._start_monotonic=None
  self.last_duration_s=elapsed
  self.run_btn.configure(text='▶  开始分析',state='normal')
  self.status.configure(text='完成 · 用时 '+(f'{elapsed:.1f} 秒 · ' if elapsed is not None else '')+'文件保存在「分析结果」 / '+Path(out).name,fg=ACCENT)
                                                                                 
  txt='分析完成 · 核心结论\n\n'
  if self.module=='视频追踪' and '人工特征点' in str(result.get('tracking_mode','')):
   txt+='已使用【人工命名点 + LK 光流】追踪，不是旧版明暗轮廓模式。\n'
   txt+='主要运动点：'+str(result.get('main_motion_point','未确认'))+'\n'
   event=result.get('projected_movement_candidate_s')
   txt+=('持续二维移动候选：'+(f'{event:.2f} 秒' if isinstance(event,(int,float)) else '未能可靠确定')+'\n')
   txt+='标尺：'+('已按用户确认的比例换算' if result.get('real_scale_confirmed') else '未核实；先按 px/像素每秒理解')+'\n'
   txt+='\n请先阅读本次结果中的「先看这里_视频分析结果.txt」。\n'
   txt+='最重要：review_overlay.mp4 → motion_review_queue.csv → FIGURE_motion_multipanel.png。\n'
   txt+='离台/起飞时间需要逐帧核查；不能用运动阈值自动证明。\n'
   td=result.get('three_d_status','MONOCULAR_3D_NOT_OBSERVABLE')
   if td=='CALIBRATED_STEREO_RECONSTRUCTION':
    txt+='\n【已执行真实标定双目三维】\n'
    txt+=f'有效XYZ记录：{result.get("three_d_valid_points",0)} / {result.get("three_d_attempted_points",0)}。\n'
    txt+='先看 stereo_3d_points.csv 的 valid_3d/quality，再看 three_d_point_summary.csv 和 FIGURE_calibrated_3d_trajectory。\n'
    txt+='坐标属于左相机坐标系，需用独立已知长度和深度评估真实精度。\n'
   elif td=='CALIBRATED_RIGID_OBJECT_PNP':
    txt+='\n【已执行已知CAD刚体PnP】\n'
    txt+=f'有效刚体位姿：{result.get("three_d_pose_valid_frames",0)} / {result.get("three_d_pose_total_frames",0)}帧。\n'
    txt+='看 rigid_body_pose_3d.csv；这不是自由形变翅膀的三维运动。\n'
                     

  elif self.module=='视频追踪':
   txt+='警告：当前结果来自【旧版轮廓追踪】，不会使用人工 P1/P2 特征点！\n'
   txt+='如果你已经标点，请改为【人工点锚定 LK 光流】并重新运行。\n'
  if self.module=='实验数据优化':
   status=result.get('status','')
   labels={'CANDIDATE_REQUIRES_VALIDATION':'通过基础模型检查；候选仍需实测',
      'CANDIDATE_NEEDS_EXPERIMENTAL_VALIDATION':'通过基础模型检查；候选仍需实测',
      'LOW_MODEL_RELIABILITY':'模型预测能力不足：不发布正式推荐',
      'NO_CONFIDENT_FEASIBLE_CANDIDATE':'没有符合可信约束门槛的候选',
      'NO_NEARBY_SUPPORTED_CANDIDATE':'候选离已测区域太远：不发布正式推荐',
      'CANDIDATE_IN_SPARSE_REGION':'候选位于数据稀疏区域，需谨慎'}
   txt+='模型状态：'+labels.get(status,status)+'\n'
   rec=result.get('recommended_parameters')
   if rec:
    txt+='\n下一组候选参数（仍需实验验证）：\n'
    for k,v in rec.items():txt+='  '+str(k)+'：'+self._format_output(k,v)+'\n'
    if result.get('predicted_responses'):
     txt+='\n模型预测的测量结果：\n'
     for k,v in result['predicted_responses'].items():txt+='  '+str(k)+'（预测值）：约 '+self._format_output(k,v)+'\n'
   else:txt+='\n本次没有可用于直接推荐的可靠候选。请优先补充实验数据、重新检查参数或约束。\n'
   txt+='\n【模型对历史实验的预测表现】\n（留组交叉验证，只反映历史数据验证；不能保证未来实验误差相同。）\n'
   for m in result.get('validation_metrics',[]):
    txt+=('\n'+str(m.get('response','指标'))+'：留组 R²='+f'{m.get("cv_R2",float("nan")):.3f}'
       +'  |  MAE='+f'{m.get("cv_MAE",float("nan")):.4g}'
       +'  |  均值基线 MAE='+f'{m.get("baseline_MAE",float("nan")):.4g}'+'\n')
   txt+='\n【下一步怎样核对】\n① 先看 model_validation.csv：误差是否比均值基线小。\n② 再看 cv_predictions.csv：哪些历史实验预测偏差较大。\n③ 最后检查 predicted_candidates.csv：候选条件、限制与风险。\n④ 通过新实验验证之后，才能判断推荐是否有效。\n'
  elif self.module=='项目工作流':
   txt+='本项目共有 '+str(result.get('project_experiments','?'))+' 次实验记录，联合表包含 '+str(result.get('metrics_count','?'))+' 个指标字段。\n'
   txt+='成功 '+str(result.get('completed_steps','?'))+' 个处理阶段，被阻止 '+str(result.get('blocked_steps','?'))+' 个，失败 '+str(result.get('failed_steps','?'))+' 个。\n'
   txt+='主图展示：'+RESULT_NAMES.get(str(result.get('project_main_metric','用户指定指标')),str(result.get('project_main_metric','用户指定指标')))+'。请检查每条实验记录是否真正独立；主图是描述性汇总，不能替代独立试样统计。\n'
   txt+='阅读顺序：project_stage_audit.csv → project_metrics_by_experiment.csv → FIGURE_project_main。\n'
  elif self.module!='视频追踪':
   for k,v in list(result.items())[:8]:
    if k in ('quality_warnings','warnings','iteration_history'):continue
    value=self._format_output(k,v)
    if len(value)>160:continue
    txt+='· '+summary_field_detail(self.module,k)[0]+'（'+k+'）：'+value+'\n'
  warn=result.get('quality_warnings',[])
  if warn:
   txt+='\n需要核对：\n'+'\n'.join('· '+str(x) for x in warn[:4])+'\n'
   if len(warn)>4:txt+='（其余 '+str(len(warn)-4)+' 条见完整报告）\n'
  txt+='\n完整数值和原始字段仍保留在结果 CSV、Excel、JSON 中。\n'
  txt+='需要逐项核对时，点击「查看全部指标与计算结果」。'
  if self.module=='项目工作流':
   self.project_nav_button.pack(fill='x',padx=12,pady=(0,5))
  else:self.project_nav_button.pack_forget()
  self._complete_result=dict(result)
  self._render_result_metrics(result)
  self._refresh_detail_tables()
  self._set_result(txt)
  self.result_head.config(text=f'✓ {display_name(self.module)} · 已完成')
  labels={**RESULT_NAMES,'rows':'表格总行数','columns':'表格总列数','exact_duplicate_rows':'整行重复数','total_missing_cells':'空白格总数','independent_specimens':'独立试样数','tested_cycles':'实验循环数','mean_peak_force_N':'平均峰值 (N)',
    'mean_separation_work_mJ':'平均正向力—位移积分 (mJ)','frames_analyzed':'分析帧数',
    'detection_rate':'自动检出率','net_climb_mm':'净攀爬位移 (mm)',
    'total_independent_specimens':'独立样本数','groups':'条件组数','independent_units':'独立实验单位'}
  if self.module=='项目工作流' and 'project_experiments' in result:
   metrics=[('实验记录数',result.get('project_experiments',0)),
            ('完成阶段',result.get('completed_steps',0)),
            ('阻止/失败',str(result.get('blocked_steps',0))+' / '+str(result.get('failed_steps',0)))]
   self._metric_keys=['project_experiments','completed_steps','blocked_steps']
  elif self.module=='实验数据优化' and result.get('validation_metrics'):
   first=result['validation_metrics'][0]
   metrics=[('留组预测 R²',f'{first.get("cv_R2",float("nan")):.3f}'),
            ('留组预测 MAE',f'{first.get("cv_MAE",float("nan")):.3g}'),
            ('候选建议', '待实验验证' if result.get('recommended_parameters') else '暂不建议')]
   self._metric_keys=['cv_R2','cv_MAE','status']
  else:
   valid_keys=[k for k,v in result.items() if k in labels and isinstance(v,(float,int))][:3]
   metrics=[(labels[k],result[k]) for k in valid_keys]
   self._metric_keys=valid_keys
   if not metrics:
    metrics=[('运行模块',self.module),('质量提醒',len(result.get('quality_warnings',[])))]
    self._metric_keys=['module','quality_warnings']
  for i,(val,label) in enumerate(self.metric_cards):
   if i<len(metrics):
    name,value=metrics[i];val.config(text=(f'{value:.3g}' if isinstance(value,float) else str(value))[:19]);label.config(text=name[:14])
   else:val.config(text='—');label.config(text='—')
  from ui_outputs102 import result_files
  self.figures=sorted((p for p in result_files(out) if p.suffix.lower()=='.png'),key=lambda p:(0 if p.name.startswith('FIGURE_') else 1,p.name))
  self.figure_index=0
  self._show_figure()
  self.view_tabs.select(self.results)
  if result.get('status') in ('NO_FEASIBLE_SOLUTION','LOW_MODEL_RELIABILITY','PREDICTED_CONSTRAINT_NOT_MET'):
   messagebox.showwarning('结果需要特别注意','优化结果存在可行性或预测可靠性问题，请查看详细质量提示。')

 def _failed(self,error,detail):
  self.busy=False;self._freeze_form_inputs(False);self.cancel_btn.configure(state='disabled',text='请求停止（安全检查点）');self._start_monotonic=None;self._invalidate_current_results('当前分析未完成。')
  self.run_btn.configure(text='▶  开始分析',state='normal');self.status.configure(text='运行失败，请核对输入数据与参数',fg='#B91C1C')
  self.result_head.config(text='分析失败 · 不应使用本次输出')
  self._set_result('未生成有效分析结果。\n\n原因：\n'+error+'\n\n技术细节（需要时发给开发者）：\n'+detail)
  if '用户请求停止' in str(error):
   self.status.configure(text='任务已停止（不应使用未完成的结果）',fg=MUTED)
   messagebox.showinfo('已请求停止','计算在安全检查点退出。已生成但未完成的结果文件不能用于科研结论。')
  else:messagebox.showerror('分析未完成',error+'\n\n请先核对列名、单位、数值和输入格式。')

 def pick_roi(self):
  """Visual ROI selection on the first frame; dimensions map to original pixels."""
  if self.busy:return                                                    
  path=self.controls.get('file')
  if not path or not path.get().strip():messagebox.showinfo('先选择图片或视频','请先在上方选择图片 / 视频，再点击鼠标框选。');return
  p=Path(path.get())
  if p.is_dir():
   pics=sorted(x for x in p.iterdir() if x.suffix.lower() in ('.png','.jpg','.tif','.tiff','.bmp'))
   if not pics:messagebox.showwarning('无图片','选择的文件夹没有可识别的图片。');return
   p=pics[0]
  try:
   from PIL import Image,ImageTk
   if p.suffix.lower() in ('.avi','.mp4','.mov','.mkv'):
    import cv2
    cap=cv2.VideoCapture(str(p));ok,frame=cap.read();cap.release()
    if not ok:raise ValueError('无法读取视频首帧')
    im=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
   else:im=Image.open(p).convert('RGB')
  except Exception as exc:messagebox.showerror('图片读取失败',str(exc));return
  ow,oh=im.size;scale=min(760/ow,525/oh,1);dw,dh=round(ow*scale),round(oh*scale)
  win=tk.Toplevel(self);win.title('用鼠标拖拽选择分析区域 (ROI)');win.configure(bg=WHITE);win.grab_set()
  tk.Label(win,text='在下方图片中按住鼠标拖拽框选，点击「确认范围」保存；坐标自动换算为原始像素。',bg=WHITE,fg=TEXT).pack(padx=16,pady=12)
  im=im.resize((dw,dh));photo=ImageTk.PhotoImage(im)
  canvas=tk.Canvas(win,width=dw,height=dh,highlightthickness=1,highlightbackground=BORDER)
  canvas.pack(padx=16,pady=6);canvas.create_image(0,0,image=photo,anchor='nw');canvas.image_ref=photo
  pts={'start':None,'end':None,'rect':None}
  def down(e):
   pts['start']=(e.x,e.y);pts['end']=None
   if pts['rect']:canvas.delete(pts['rect'])
  def drag(e):
   if not pts['start']:return
   x=max(0,min(dw,e.x));y=max(0,min(dh,e.y));pts['end']=(x,y)
   if pts['rect']:canvas.delete(pts['rect'])
   pts['rect']=canvas.create_rectangle(*pts['start'],x,y,outline='#22C55E',width=3)
  def up(e):
   if pts['start'] is None:return
   drag(e)                                                 
  canvas.bind('<ButtonPress-1>',down)
  canvas.bind('<B1-Motion>',drag)
  canvas.bind('<ButtonRelease-1>',up)
  def commit():
   if not pts['start'] or not pts['end']:messagebox.showwarning('尚未选择','拖动鼠标框选一个矩形。',parent=win);return
   a,b=pts['start'],pts['end'];l=max(0,int(min(a[0],b[0])/scale));r=min(ow,int(max(a[0],b[0])/scale));t=max(0,int(min(a[1],b[1])/scale));bt=min(oh,int(max(a[1],b[1])/scale))
   if r-l<3 or bt-t<3:messagebox.showwarning('范围过小','所选区域宽和高应至少3个像素。',parent=win);return
   self.controls['roi'].set(f'{l},{t},{r},{bt}');win.destroy()
  tk.Button(win,text='确认范围',command=commit,bg=ACCENT,fg=WHITE,relief='flat',padx=22,pady=8).pack(pady=(8,16))

 def open_output(self):
  p=self.last_output or Path(self.output_var.get()).expanduser()
  if not p.exists():messagebox.showinfo('暂无结果','尚未运行分析，结果文件夹不存在。');return
  try:
   if sys.platform=='win32':os.startfile(str(p))
   elif sys.platform=='darwin':subprocess.Popen(['open',str(p)])
   else:subprocess.Popen(['xdg-open',str(p)])
  except Exception as exc:messagebox.showinfo('文件夹位置',str(p)+'\n'+str(exc))

if __name__=='__main__':Desktop().mainloop()
