""" result-reading support. Descriptive only; never changes analysis values."""
from pathlib import Path
import re
import pandas as pd
from ui_guidance import describe_file, field_help
from ui_explanations_v6 import column_detail, FILE_COLUMNS, COLUMN_HELP
from ui_copy104 import display_name

PANELS={
 '力学分析': [('force_curves','横轴：位移 mm；纵轴：原始方向调整后的拉力 N。核对原始测力曲线是否包含预加载。'),('FIGURE_adhesion_multipanel','a 横轴校正后相对位移 mm、纵轴校正后正向拉力 N；b 各条件峰值 N；c 分离阶段积分功 mJ；d 每独立试样峰值 N 与功 mJ。独立试样 n 不能用循环次数代替。')],
 '批量力学':[('FIGURE_batch_mechanics','a 相对位移 mm 对校正拉力 N；b 按独立试样的峰值力 N；c 积分功 mJ；d 峰值与功的关系。先看导入清单、逐循环，再看试样汇总。')],
 '视频追踪':[('FIGURE_motion_multipanel','a 视频原帧及人工点位置（原像素）；b 主体特征点 X/Y 二维路径（按实际标尺或原像素）；c 时间 s 对相对初始位置的位移；d 时间 s 对采样间隔速度。红色/空白需回视频核对，非三维轨迹。'),('FIGURE_time_coded_multi_point','a 原图二维轨迹 X/Y（px），颜色代表时间；b 时间 s 对各特征点的投影位置 mm，未标定时禁止作为真实 mm 解释。'),('FIGURE_speed_and_tracking_quality','a 时间 s 对原始有限差分速度 mm/s，以及仅供阅读的趋势线；b 时间 s 对检测质量/失检/人工复核建议。速度尖峰可能来自错误定位。'),('FIGURE_relative_motion','a 时间 s 对指定点相对参考点的位移 mm；b 时间 s 对点对投影距离 mm。只有二维投影，不是三维肢体长度。'),('FIGURE_periodicity_screen','时间 s 对点对距离/变化，周期候选依赖视频帧率、可见性和信噪比；不能凭 30fps 视频断言高速扑翼频率。'),('FIGURE_calibrated_3d_trajectory','空间 X/Y/Z 由双相机标定或刚体模型确定；需查看 valid_3d、相机坐标系及空间误差，不能只看重投影误差。')],
 '轨迹人工修正':[('corrected_trajectory','横纵轴为校正后的二维坐标；比较原始与修正轨迹，确认仅修改人工核验的帧。'),('corrected_kinematics','横轴时间 s；纵轴为速度 mm/s 或点对投影角 deg，依具体面板。'),('FIGURE_motion_multipanel','a 实际视频与人工点；b 修正后二维路线；c 时间 s 对相对位置变化；d 时间 s 对速度/复核信息。修正一帧不等于自动重跑所有后续帧。')],
 '运动关系分析':[('FIGURE_spatial_3d_relations','已标定的双目三维关系图：上图横轴时间s、纵轴点对真实空间距离mm；下图横轴时间s、纵轴三点包含角度°。虚线/缺口不应被自动补造；不能用重投影误差证明空间精度。'),('FIGURE_motion_relation_overview','a 时间 s 对各点投影速度 px/s；b 时间 s 对低速候选区间（阈值定义，不等于接触或吸附）；c 时间 s 对点对投影距离 px，若提供外部信号则附同时间刻度的信号变化。'),('FIGURE_motion_editorial_88','强调速度、低速候选和点对距离；图中“阶段”仅是根据数值阈值划分的运动学候选。')],
 '显微图像':[('segmentation_mask','黑白分割掩膜，显示哪些像素被算入目标；必须看是否识别错区域。'),('overlay_','在原图叠加圈选区域，检查是否将反光、背景或标尺误识别为目标。')],
 '信号处理':[('signal','横轴时间 s；纵轴原测量单位的滤波后数值。必须对照 filtered_signal.csv 的 raw_value 与 filtered_value。')],
 '多源同步':[('synchronized_signals','横轴共同时间 s；纵轴 A/B 各自的原始数值单位。不同单位叠图不能直接比较幅值，需注意相机和传感器真正的物理延迟。')],
 '独立样本统计':[('sample_level_graph','横轴实验条件；纵轴源数据单位的每独立试样均值及组汇总。每个点代表试样，不是技术重复。'),('FIGURE_specimen_multipanel','独立试样点与均值置信区间、箱线分布、经验累积分布以及中位数与四分位范围；详看图轴单位和 n。')],
 '高级统计':[],
 '曲线拟合':[('fit_curve','横轴实验 X 变量；纵轴 Y 观测与模型预测，残差和拟合优度需另看数据表。')],
 '公式优化':[('优化过程','横轴求解器迭代回调次数；纵轴到当前为止最好的可行目标函数值。平台不代表全局最优。')],
 '实验数据优化':[('FIGURE_out_of_fold_validation','横轴真实测量值，纵轴留组预测值，虚线为理想一致线；越贴近线历史预测误差越小，不能代表新实验保证准确。'),('predicted_pareto','横轴与纵轴分别是两种响应的模型预测，实测点与预测非支配候选须区分。'),('surrogate_curve','横轴历史实验可控参数；纵轴模型预测响应、估计区间和真实测量点。模型外插尤其不可靠。')],
 '论文绘图':[('publication_figure','横纵轴由当前图形所选源数据列决定，请核对坐标轴标题、单位、组别、独立试样 ID 和误差棒含义。'),('FIGURE','科研图版通常包含多个子图；每幅图的坐标单位和统计层次可能不同，不能统一解释。')],
 '分析结果整理':[],
 '数据质检':[],
 '项目工作流':[('FIGURE_project_main','多源项目主图，坐标轴依用户在统一指标表中选择的响应变量与组别；图表仅作描述，不代表所有实验具有相同独立性或单位。')],
}

                                                                                  
                                                                               
def input_effects(module,cfg):
    out=[]
    mode=cfg.get('tracking_mode','point_lk')
    three_d=cfg.get('enable_3d','no')=='yes'
    behavior=cfg.get('behavior_enable','no')=='yes'
    method=cfg.get('stat_method','paired')
    pipeline=cfg.get('pipeline_kind','integrated')
    for key,value in cfg.items():
        value=str(value).strip()
        status='当前分析路径可使用'
        why='根据此模块分析流程及选项使用；请核对输出的计算参数与结果。'
        if key.startswith(('plot_','chart_')) or key.startswith('figure_'):
            status='仅绘图或文件输出设置';why='可能影响图尺寸、文字或配色，不改变测量数据和力学公式；部分专用图保留固定轴。'
        if not value:
            status='未填写/未启用';why='空值的可选字段不参与本次分析，或触发有记录的默认规则。'
        if module in ('视频追踪','轨迹人工修正'):
            if key in ('enable_3d','reconstruction_3d','stereo_calibration_file','stereo_right_track_file','stereo_time_offset_s','stereo_match_tolerance_s','stereo_max_reprojection_px','stereo_min_ray_angle_deg','rigid_geometry_file') and not three_d:
                status='本次未启用';why='未勾选三维，三维标定、另一相机和 CAD 信息不参与二维分析。'
            if key.startswith('behavior_') and not behavior:
                status='本次未启用';why='未开启附加运动关系分析；传感器文件和相应时间平移参数不会生成联合结果。'
            if module=='视频追踪' and mode=='point_lk' and key in ('mode','threshold','min_area_px','segmentation','clahe','max_jump_px','min_confidence'):
                status='本次未使用';why='这些参数属于旧版明暗轮廓追踪，人工 LK 特征点模式不调用。'
            if module=='视频追踪' and mode=='contour' and key in ('seed_file','lk_window_px','lk_pyramid','lk_fb_limit_px','stationary_threshold_mm_s'):
                status='本次未使用';why='旧轮廓模式不使用 LK 特征点锚点/窗口配置。'
        if module=='运动关系分析' and key.startswith('spatial_3d_') and not cfg.get('spatial_3d_track_file','').strip():
            status='本次未使用';why='没有三维标定轨迹文件，空间点对与三点夹角不计算；二维运动关系仍正常运行。'
        if module=='运动关系分析' and key.startswith('behavior_force_') and not cfg.get('behavior_force_file','').strip():
            status='本次未使用';why='没有选择外部信号文件；不计算外部传感器时间对齐。'
        if module=='高级统计':
            if method=='uncertainty' and key in ('file','col_condition','col_sample_id','col_value','batch_col','bootstrap_seed'):
                status='本次未使用';why='不确定度合成直接使用测量值与标准不确定度分量，不读取统计表。'
            if method!='uncertainty' and key in ('measurement','uncertainties'):
                status='本次未使用';why='本次是组间统计而不是不确定度合成。'
            if method!='mixed' and key=='batch_col':status='本次未使用';why='批次列仅混合效应模型需要。'
        if module=='信号处理':
            if key=='window' and cfg.get('filter')!='savgol':status='本次不影响当前滤波';why='Savitzky–Golay 窗口只对该平滑方法有效。'
            if key=='cutoff_hz' and cfg.get('filter')!='lowpass':status='本次不影响当前滤波';why='低通截止频率只对低通方法有效。'
        if module=='实验数据优化' and key=='candidate_count' and cfg.get('surrogate')!='GaussianProcess':
            status='本次未使用';why='候选点采样数量选项仅用于 GP 优化模式。'
        if module=='项目工作流':
                                                                                     
                                                                                 
            categories={'table':('pipeline_table_','pipeline_confirm_id'),
                        'motion':('behavior_','mm_per_pixel','motion_scale_confirmed','climb_axis'),
                        'force':('time_col','displacement_col','force_col','tension_sign','force_baseline','pull_start_s','pull_end_s','pipeline_protocol_confirm','pipeline_confirm_id','pipeline_metric')}
            if pipeline!='integrated' and key.startswith('pipeline_integrated_'):
                status='本次未使用';why='本次选择的是快捷模式，并未运行完整多源项目。'
            if pipeline=='integrated' and key.startswith('pipeline_table_'):
                status='本次未使用';why='多源项目从实验清单按来源运行，不使用普通单表快捷绘图参数。'
            if pipeline=='table' and key.startswith('behavior_'):
                status='本次未使用';why='普通测量表快捷模式不调用视频轨迹关系计算。'
        if key in ('file','seed_file','corrections_file','file_b') and value:
            why='这是计算数据来源；需确保文件与本次实验对应。'
        out.append({'参数字段':key,'当前填写值':value[:200], '生效判断':status,'依据与作用':why})
    return pd.DataFrame(out)


def _short_explanation(value):
    """Keep the concrete definition, without general warnings or qualifications."""
    value = re.sub(r'\s+', ' ', str(value)).strip()
    if not value:
        return ''
    sentences = re.split(r'(?<=。)|(?<=！)|(?<=？)', value)
    useful = []
    for item in sentences:
        item = item.strip()
        if not item:
            continue
        if item.startswith(('不是', '不代表', '不等于', '不能', '不可', '不得',
                            '注意', '应当', '建议', '请先', '请核对', '必须核对',
                            '需要确认', '仅凭', '不自动', '无法自动')):
            continue
        for word in ('；不是', '；不代表', '；不能', '；不可', '；不等于',
                     '；是否', '；应当', '；请', '；还需',
                     '，不是', '，不代表', '，不能', '，不可', '，不等于'):
            item = item.split(word, 1)[0]
        if item:
            useful.append(item)
            break
    return ' '.join(useful).strip()[:160]


def _defined_column(file_name, name):
    """Only show column meanings explicitly covered by the explanatory glossary."""
    name = str(name)
    if name in FILE_COLUMNS.get(file_name, {}) or name in COLUMN_HELP:
        return True
    for suffix in ('_mean', '_std'):
        if name.endswith(suffix) and name[:-len(suffix)] in COLUMN_HELP:
            return True
    return False


def _defined_file_description(name):
    description = describe_file(name)
    if description.startswith(('尚未核实', '这张表尚无', '该位图缺少')):
        return ''
    return _short_explanation(description)


def write_run_reader(folder, module, cfg, results):
    """Generate only the definitions of files, chart content and active settings."""
    folder = Path(folder)
    lines = [f'# {display_name(module)} · 文件与参数说明', '',
             '介绍本次生成的文件、常见列名、图表内容和使用的参数。', '',
             '## 输出文件', '']
    file_count = 0
    for p in sorted(folder.iterdir()):
        if not p.is_file() or p.name in ('本次结果怎么读_V10.1.md',):
            continue
        if p.suffix.lower() in ('.svg', '.pdf', '.tiff', '.tif'):
            continue
        description = _defined_file_description(p.name)
        if not description:
            continue
        file_count += 1
        lines += ['### ' + p.name, '', description, '']
        if p.suffix.lower() == '.csv':
            try:
                columns = pd.read_csv(p, encoding='utf-8-sig', nrows=0).columns
                descriptions = []
                for col in columns:
                    if not _defined_column(p.name, col):
                        continue
                    zh, detail = column_detail(p.name, col)
                    if zh.startswith('未收录字段（'):
                        continue
                    meaning = _short_explanation(detail)
                    if meaning:
                        descriptions.append(f'- **{zh}（{col}）**：{meaning}')
                if descriptions:
                    lines += descriptions + ['']
            except (ValueError, pd.errors.EmptyDataError, UnicodeDecodeError):
                pass
        if p.suffix.lower() == '.png':
            panel = next((desc for pattern, desc in PANELS.get(module, [])
                          if pattern in p.name), None)
            if panel:
                lines += ['**图中内容**：' + _short_explanation(panel), '']
    if not file_count:
        lines += ['本次没有需要单独说明的文件。', '']

    df = input_effects(module, cfg)
    df.to_csv(folder / '参数使用审查_V10.1.csv', index=False, encoding='utf-8-sig')
    lines += ['## 本次参数', '']
    count = 0
    for row in df.itertuples(index=False):
        key, current, status = str(row[0]), str(row[1]), str(row[2])
        if status in ('未填写/未启用', '本次未启用', '本次未使用', '本次不影响当前滤波'):
            continue
        detail = field_help(module, key)
        if not detail:
            continue
        meaning = _short_explanation(detail[0])
        if not meaning:
            continue
        count += 1
        if key in ('file', 'file_b', 'seed_file', 'corrections_file', 'video_file') or key.endswith('_file'):
            current = Path(current).name
        if len(current) > 65 or '\n' in current:
            current = current[:62].replace('\n', '；') + '…'
        lines += [f'- **{key}**：{meaning}' + (f'（当前值：`{current}`）' if current else '')]
    if not count:
        lines += ['本次没有需要单独说明的参数。']
    lines += ['']
    (folder / '本次结果怎么读_V10.1.md').write_text('\n'.join(lines), encoding='utf-8-sig')
