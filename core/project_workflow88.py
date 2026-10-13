"""Opt-in project orchestration; reuses standalone modules, never modifies source.

No implicit sample identity or physical meaning. Every stage is independently auditable.
"""
from __future__ import annotations
import json,html,shutil
from pathlib import Path
import numpy as np
import pandas as pd
from .common import read_table,save_csv,save_json
from .editorial_figures88 import specimen_figure,motion_figure
from ui_outputs102 import find_output_file

def execute_workflow(config,folder,run_module,save_plot):
    kind=config.get('pipeline_kind','force')
    stages=[];warnings=[];output=Path(folder)
    def stage(name,path,status,note):
        stages.append({'stage':name,'status':status,'folder':str(path) if path else '', 'note':note})
    if kind=='integrated':
        from .project_integrated93 import run_integrated
        summary,stages=run_integrated(config,output,run_module,save_plot)
        warnings.extend(summary.get('quality_warnings',[]))
    elif kind=='table':
        source=Path(config['file'])
        if not source.is_file():
            raise ValueError('通用表格模式需要 CSV / Excel 文件。多个仪器文件请先分别检查，勿将不同单位的数据直接混合。')
        d=read_table(source,sheet='auto' if source.suffix.lower() in ('.xlsx','.xlsm') else 0)
        x=config.get('pipeline_table_x','').strip()
        y=config.get('pipeline_table_y','').strip()
        g=config.get('pipeline_table_group','').strip()
        sid=config.get('pipeline_table_sample','').strip()
        typ=config.get('pipeline_table_chart','散点图')
        if not y:raise ValueError('请指定一个测量响应 Y 列名（填写原表表头，不是某个数值）。')
        if typ not in ('直方图','累积分布图') and not x:
            raise ValueError('所选图类型需要指定横轴 X 列名。')
        required={y} | ({x} if typ not in ('直方图','累积分布图') else set()) | ({g} if g else set())
        absent=sorted(required-set(d.columns))
        if absent:raise ValueError('通用表格缺少所选列 '+str(absent)+'；可用表头：'+str(list(d.columns)))
        qc_dir,qc_result=run_module('数据质检',{'file':str(source)},output)
        stage('数据质检',qc_dir,'complete','检查原始表的格式、缺失、重复和疑似离群值；不删除源数据')
        warnings.extend(qc_result.get('quality_warnings',[]))
        if config.get('pipeline_table_stats','no')=='yes':
            if not g or not sid or g not in d or sid not in d:
                raise ValueError('独立试样统计需要填写真实的实验分组列和独立试样编号列。')
            if config.get('pipeline_confirm_id','no')!='yes':
                raise ValueError('请先核实物理独立试样 ID 后再启用推断统计；也可以先关闭组间统计，只完成质检和绘图。')
            if d[[g,sid,y]].isna().any().any():
                raise ValueError('独立样本统计所用分组、试样 ID 或测量列存在缺失值；请先核对原表。')
            counts=d.groupby(sid,dropna=False)[g].nunique()
            if (counts>1).any():
                raise ValueError('同一独立试样 ID 出现在不同条件组；可能是配对/重复测量，请用高级统计选择合适模型。')
            if d[g].nunique()<2:
                raise ValueError('独立样本组间统计需要至少两个有意义的实验条件。')
            statready=d[[g,sid,y]].rename(columns={g:'condition',sid:'sample_id',y:'value'}).copy()
            save_csv(statready,output/'analysis_ready_measurements.csv')
            statcfg={'file':str(output/'analysis_ready_measurements.csv'),
                     'col_condition':'condition','col_sample_id':'sample_id','col_value':'value',
                     'bootstrap_seed':'42','bootstrap_rounds':'3000'}
            stat_dir,stat_result=run_module('独立样本统计',statcfg,output)
            stage('独立样本统计',stat_dir,'complete',
                  '只有人工核对真实样本身份后才按每件独立试样汇总；配对与复杂批次设计不能套用此模式')
            warnings.extend(stat_result.get('quality_warnings',[]))
        chartcfg={'file':str(source),'chart_type':typ,'chart_x':x,'chart_y':y,
                  'chart_group':g,'chart_sample_id':sid if config.get('pipeline_table_stats')=='yes' else '',
                  'chart_xlabel':str(config.get('pipeline_chart_xlabel','')).strip(),
                  'chart_ylabel':str(config.get('pipeline_chart_ylabel','')).strip(),
                  'plot_palette':config.get('plot_palette','论文经典'),
                  'plot_style':config.get('plot_style','期刊简洁'),
                  'plot_size':config.get('plot_size','双栏 183 mm'),
                  'plot_dpi':config.get('plot_dpi','450'),
                  'plot_title':'否','chart_error':'95% CI'}
        fig_dir,figure_res=run_module('论文绘图',chartcfg,output)
        stage('科研绘图',fig_dir,'complete',
              '绘制选定 X/Y 列；该图为观测值展示，不在未确认独立性时自动报告显著性')
        warnings.extend(figure_res.get('quality_warnings',[]))
        for suffix in ('.png','.tiff','.pdf','.svg'):
            src=find_output_file(fig_dir,'publication_figure'+suffix)
            if src.exists():shutil.copy2(src,output/('FIGURE_project_main'+suffix))
        save_csv(pd.DataFrame({'column':list(d.columns),'dtype':[str(t) for t in d.dtypes]}),
                 output/'original_column_index.csv')
        summary={'pipeline_type':'generic_table_qc_figure','input_rows':len(d),
                 'input_columns':len(d.columns),'observed_x':x,'observed_y':y,
                 'chart_type':typ,'statistics_requested':config.get('pipeline_table_stats')=='yes',
                 'independent_sample_inference':config.get('pipeline_table_stats')=='yes',
                 'figure_data_not_imputed':True,
                 'data_scope':'CSV/Excel tabular data with explicit measurement columns'}
    elif kind=='force':
        if config.get('pipeline_protocol_confirm')!='yes':
            raise ValueError('批量力学工作流必须先确认力方向、零点和拉离过程分析时间窗符合实验规程；这不是默认可猜的参数。')
        fc={k:v for k,v in config.items() if k not in ('pipeline_kind','pipeline_metric','pipeline_confirm_id','pipeline_protocol_confirm')}
        fc['file']=config['file'];fc.setdefault('time_col','time_s');fc.setdefault('displacement_col','displacement_mm');fc.setdefault('force_col','force_N')
        fc.setdefault('tension_sign','positive');fc.setdefault('force_unit','N');fc.setdefault('time_unit','s');fc.setdefault('displacement_unit','mm')
        fc.setdefault('force_baseline','first_fraction');fc.setdefault('baseline_fraction','0.05')
        result_dir,res=run_module('批量力学',fc,output)
        stage('批量力学',result_dir,'complete','保留逐循环数据、原始校正曲线、导入清单和按试样汇总表')
        specimen=read_table(find_output_file(result_dir,'independent_specimens.csv'))
        manifest=read_table(find_output_file(result_dir,'import_manifest.csv'))
        metric=config.get('pipeline_metric','peak_force_N')
        if metric not in specimen:raise ValueError('本次试样表中没有所选指标：'+metric)
        ready=specimen[['condition','sample_id',metric]].rename(columns={metric:'value'}).copy()
        save_csv(ready,output/'analysis_ready_independent.csv')
        stage('统一分析表',output,'complete','一行代表一件试样的循环均值；保留原单位与来源')
        weak=bool('sample_origin' in manifest and manifest.sample_origin.eq('filename_fallback').any())
        if weak and config.get('pipeline_confirm_id')!='yes':
            warnings.append('某些试样编号由文件名临时代替，未确认物理试样身份；自动组间统计已跳过。')
            stage('独立样本统计',None,'blocked','缺乏经确认的独立试样身份；允许查看单试样原始指标，但不可自动解释组间显著性')
        else:
            statcfg={'file':str(output/'analysis_ready_independent.csv'),'col_condition':'condition','col_sample_id':'sample_id','col_value':'value','bootstrap_seed':'42','bootstrap_rounds':'3000'}
            stat_dir,statres=run_module('独立样本统计',statcfg,output)
            stage('独立样本统计',stat_dir,'complete','复用独立样本统计，记录每组 n、均值、CI、统计条件与质量警告')
            warnings.extend(statres.get('quality_warnings',[]))
        fig=specimen_figure(specimen,metric)
        save_plot(fig,output/'FIGURE_project_main')
        stage('主题图版',output,'complete','展示每块独立试样的原始汇总点、每组均值；PDF/SVG保留可编辑图层')
        summary={'pipeline_type':'mechanics_stats_figure','metric':metric,'independent_specimens':len(specimen),
                 'groups':int(specimen.condition.nunique()),'identity_fallback':weak,
                 'statistics_blocked':bool(weak and config.get('pipeline_confirm_id')!='yes')}
    elif kind=='motion':
        input_file=Path(config['file'])
        mapping={'file':str(input_file),'behavior_track_format':config.get('behavior_track_format','auto'),
                 'behavior_time_col':config.get('behavior_time_col','time_s'),
                 'behavior_point_col':config.get('behavior_point_col','point_id'),
                 'behavior_x_col':config.get('behavior_x_col','x_px'),
                 'behavior_y_col':config.get('behavior_y_col','y_px'),
                 'behavior_source_unit':config.get('behavior_source_unit','px'),
                 'motion_scale_confirmed':config.get('motion_scale_confirmed','no'),
                 'mm_per_pixel':config.get('mm_per_pixel','0.05'),
                 'behavior_mode':'generic','behavior_body':config.get('behavior_body',''),
                 'behavior_feet':config.get('behavior_feet',''),
                 'behavior_speed_threshold_px_s':config.get('behavior_speed_threshold_px_s','12'),
                 'behavior_min_dwell_s':config.get('behavior_min_dwell_s','0.25'),
                 'climb_axis':config.get('climb_axis','right'), 'behavior_substrate':config.get('behavior_substrate','')}
        track_dir,res=run_module('运动关系分析',mapping,output)
        stage('轨迹关系分析',track_dir,'complete','直接复用多品牌轨迹 CSV，保留逐帧、点对距离、低速候选和质量提示')
        frame=read_table(find_output_file(track_dir,'motion_relation_frames.csv'));bouts=read_table(find_output_file(track_dir,'motion_relation_bouts.csv'));pairs=read_table(find_output_file(track_dir,'motion_relation_pairs.csv'))
        fig=motion_figure(frame,bouts,pairs)
        save_plot(fig,output/'FIGURE_project_main')
        stage('运动图版',output,'complete','用连续测量线段和小型时间轴表达主要指标；仅描述二维投影')
        warnings.extend(res.get('quality_warnings',[]))
        summary={'pipeline_type':'landmark_relations_figure','records':len(frame),'point_names':sorted(frame.target_point.unique().tolist()),
                 'candidate_bouts':len(bouts),'metric_3d':'not inferred'}
    else:raise ValueError('请选择通用科研表格、运动轨迹或专项力学三种工作流之一。')
    saved=pd.DataFrame(stages)
    save_csv(saved,output/'workflow_index.csv')
    summary['completed_steps']=int(saved.status.eq('complete').sum())
    summary['blocked_steps']=int(saved.status.eq('blocked').sum())
    summary['quality_warnings']=list(dict.fromkeys(warnings))
    lines=['# 项目工作流 · 本次分析索引','','每一步都有独立计算目录和原始记录；项目工作流并未改变任何既有算法或原始输入。','','## 阶段状态']
    for st in stages:
        lines.append(f"- **{st['stage']}** — {st['status']}：{st['note']}；路径：`{st['folder'] or '(未执行)'}`")
    lines+=['','## 阅读顺序','1. 核对每个阶段的 input 来源、样本 ID 与标定。','2. 逐条查看质量警告。','3. 查看 `FIGURE_project_main.pdf` 或 `.svg`。','4. 用独立参考计算或实测数据复核后再用于论文。','','## 提醒']
    lines.extend('- '+str(w) for w in warnings)
    (output/'项目工作流_先读结果.md').write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
                                                                     
    links=[]
                                                                                               
    root_files=[('project_metrics_by_experiment.csv','跨来源统一指标表'),
                ('project_metric_dictionary.csv','指标逐列中文说明'),
                ('project_stage_audit.csv','各实验各阶段状态与失败原因'),
                ('project_source_index.csv','输入来源与实验对应关系'),
                ('project_stats_ready.csv','统计准备表'),
                ('project_optimization_ready.csv','实验优化准备表')]
    root_links=' · '.join(f'<a href="{html.escape(fn,quote=True)}">{html.escape(title)}</a>'
        for fn,title in root_files if (output/fn).is_file())
    for st in stages:
        if st['folder']:
            rel=Path(st['folder']).relative_to(output)
            available=[]
            for fn,title in [('阅读结果_从这里开始.txt','阅读指南'),('analysis_tables.xlsx','Excel结果'),
                             ('motion_relation_frames.csv','运动明细'),('adhesion_metrics.csv','力学指标')]:
                if (Path(st['folder'])/fn).is_file():
                    available.append(f'<a href="{html.escape(str(rel / fn),quote=True)}">{title}</a>')
            links.append(f'<li><strong>{html.escape(st["experiment_id"]+" / " if "experiment_id" in st else "")}{html.escape(st["stage"])}</strong> '
                         f'({html.escape(st["status"])}) — {html.escape(st["note"])} '
                         f'<code>{html.escape(str(rel))}</code> '+(' · '.join(available))+'</li>')
    html_doc='''<!DOCTYPE html><html lang="zh"><meta charset="utf-8"><title>Research Toolbox | Project</title><style>body{font-family:"Microsoft YaHei",Arial,sans-serif;max-width:920px;margin:45px auto;color:#203044;background:#f6f8fa;padding:24px;line-height:1.8}main{background:white;border:1px solid #e0e6ed;border-radius:14px;padding:28px}h1{color:#154d66}li{margin:10px 0}a{color:#126d83}code{font-size:12px;color:#526277}small{color:#657385}</style><main><h1>项目分析 · 结果导航</h1><p>这份报告由本地运行生成。原始输入未被更改，阶段文件夹可独立复核。</p><h2>阶段</h2><ol>'''+''.join(links)+'''</ol><h2>项目联合结果</h2><p>'''+root_links+'''</p><h2>阅读</h2><p><a href="FIGURE_project_main.pdf">主图 PDF</a> · <a href="FIGURE_project_main.svg">主图 SVG</a> · <a href="workflow_index.csv">阶段索引 CSV</a> · <a href="项目工作流_先读结果.md">结果说明</a></p><small>注意：图仅描述测量或模型筛选，不能替代实验和统计审核。</small></main></html>'''
    (output/'项目结果导航.html').write_text(html_doc,encoding='utf-8')
    return summary
