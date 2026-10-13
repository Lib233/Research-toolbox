"""Research results grouped for reading, not deleted or transformed."""
from pathlib import Path

VERY_IMPORTANT={
 '项目工作流':['project_metrics_by_experiment.csv','FIGURE_project_main','project_stats_ready.csv'],
 '数据质检':['column_quality.csv','quality_issues.csv'],
 '批量力学':['cycle_metrics.csv','independent_specimens.csv','group_summary.csv','FIGURE_'],
 '力学分析':['adhesion_metrics.csv','independent_specimens.csv','group_summary.csv','force_curves','FIGURE_'],
 '高级统计':['advanced_statistics_report.csv','mixed_model_coefficients.csv'],
 '视频追踪':['review_overlay.mp4','frame_trajectory.csv','FIGURE_motion_multipanel','FIGURE_calibrated_3d'],
 '轨迹人工修正':['trajectory_corrected.csv','corrected_trajectory','FIGURE_motion_multipanel'],
 '运动关系分析':['motion_relation_frames.csv','motion_relation_pairs.csv','FIGURE_motion_relation_overview','spatial_3d_summary.csv'],
 '显微图像':['image_metrics.csv','overlay_'],
 '信号处理':['filtered_signal.csv','detected_events.csv','fft_spectrum.csv','signal.png'],
 '多源同步':['aligned_signals.csv','synchronized_signals'],
 '独立样本统计':['specimen_means.csv','group_summary.csv','FIGURE_specimen_multipanel'],
 '曲线拟合':['fit_predictions_residuals.csv','fit_curve','candidate_model_comparison.csv'],
 '公式优化':['优化过程.png','优化过程.csv'],
 '实验数据优化':['model_validation.csv','recommended_experiments_top5.csv','FIGURE_out_of_fold_validation'],
 '分析结果整理':['manuscript_draft.md','manuscript_draft.docx'],
 '论文绘图':['publication_figure.svg','publication_figure.pdf','publication_figure.png'],
}
QA_HINTS=('diagnostic','audit','warning','quality','review_queue','import_manifest','normaliz','corrected_curves',
          'force_trace_corrected','source_index','stage_audit','metric_dictionary','cv_predictions','validation',
          '模型验证','误差','复核','参数使用审查','研究增强指标','spatial_3d_quality')
RUN_HINTS=('run_metadata','result_summary','READ_ME_FIRST','INCOMPLETE_RUN','analysis_tables','figure_data_mapping',
           'column_dictionary','阅读结果','本次结果','workflow_index','项目结果导航','测试','README')

def classify(module, path):
    name=Path(path).name
    if name.endswith(('_figure_settings.json','_plot_settings.json')):
        return '运行记录'
    if name=='analysis_tables.xlsx':return '核心结果'
    if name=='研究增强指标_V10.2.csv':return '辅助核验'
    if name.startswith('spatial_3d_') and name.endswith('.csv'):
        return '核心结果' if name not in ('spatial_3d_quality.csv',) else '辅助核验'
    if any(name.startswith(x) for x in VERY_IMPORTANT.get(module,[])):return '核心结果'
    if name in ('project_optimization_ready.csv','predicted_candidates.csv','motion_relation_bouts.csv','manual_changes_audit.csv'):
        return '辅助核验'
    if any(s.lower() in name.lower() for s in QA_HINTS):return '辅助核验'
    if any(s.lower() in name.lower() for s in RUN_HINTS):return '运行记录'
    if name.lower().endswith(('.json','.log','.html','.txt','.md')):return '运行记录'
    if name.lower().endswith(('.csv','.xlsx','.png','.svg','.pdf','.tiff','.tif','.mp4')):
        return '辅助核验'
    return '运行记录'

CATEGORIES=('核心结果','质量检查','运行记录')
NAVIGATION_NAMES={'00_结果导航.html','项目结果导航.html'}


def category_for(module,file):
    value=classify(module,file)
    return '质量检查' if value=='辅助核验' else value


def result_files(folder):
    root=Path(folder)
    if not root.is_dir():return []
    files=[p for p in root.iterdir() if p.is_file() and p.name not in NAVIGATION_NAMES]
    for name in CATEGORIES:
        loc=root/name
        if loc.is_dir():files.extend(p for p in loc.iterdir() if p.is_file())
    return sorted(files,key=lambda p:(p.name.casefold(),str(p.parent)))


def find_output_file(folder,name):
    root=Path(folder)
    name=Path(name).name
    direct=root/name
    if direct.is_file():return direct
    for category in CATEGORIES:
        path=root/category/name
        if path.is_file():return path
    return direct


def group_files(folder,module):
    d={name:[] for name in CATEGORIES}
    for f in result_files(folder):
        d[category_for(module,f)].append(f)
    for key,items in d.items():
        grouped={}
        for f in items:
            identity=f.stem if f.suffix.lower() in ('.png','.svg','.pdf','.tiff','.tif') else f.name
            grouped.setdefault(identity,[]).append(f)
        d[key]=list(grouped.values())
    return d


def write_index(folder,module):
    root=Path(folder)
    groups=group_files(root,module)
    lines=['# 本次文件索引','','按核心结果、质量检查、运行记录分类；每个文件仅保存一份。','']
    for category,items in groups.items():
        lines.extend(['## '+category,''])
        for family in items:
            lines.append('- '+', '.join(f.name for f in family))
        if not items:lines.append('- （本次无）')
        lines.append('')
    target=find_output_file(root,'本次文件分级索引_V10.2.md')
    target.write_text('\n'.join(lines),encoding='utf-8-sig')
    return groups


def build_reading_folders(folder,module):
    from html import escape
    from urllib.parse import quote
    root=Path(folder)
    for category in CATEGORIES:(root/category).mkdir(exist_ok=True)
    for source in list(root.iterdir()):
        if not source.is_file() or source.name in NAVIGATION_NAMES:continue
        category=category_for(module,source)
        target=root/category/source.name
        if target.exists():
            if target.read_bytes()!=source.read_bytes():
                raise FileExistsError('分类文件与原文件内容不同，停止移动：'+source.name)
            source.unlink()
        else:
            source.rename(target)
    grouped=group_files(root,module)
    overview=['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
       '<title>本次分析结果</title><style>body{font-family:Microsoft YaHei,Arial,sans-serif;max-width:960px;margin:32px auto;padding:0 24px;color:#1c3544}h1{color:#115875}h2{margin-top:28px}li{padding:5px}a{color:#176b95;text-decoration:none}a:hover{text-decoration:underline}p{color:#586d78}</style></head><body>',
       '<h1>本次分析结果</h1>',
       '<p>先查看核心结果；如需排查异常，打开质量检查；需要追溯参数和来源时，打开运行记录。</p>']
    if (root/'项目结果导航.html').is_file():
        overview.append('<p><a href="'+quote('项目结果导航.html')+'">打开项目阶段导航</a></p>')
    for category,families in grouped.items():
        overview.append('<h2>'+escape(category)+'</h2><ul>')
        for family in families:
            for source in family:
                href=quote(category)+'/'+quote(source.name)
                overview.append('<li><a href="'+href+'">'+escape(source.name)+'</a></li>')
        overview.append('</ul>')
    project_nav=root/'项目结果导航.html'
    if project_nav.is_file():
        import re
        from urllib.parse import unquote
        original=project_nav.read_text(encoding='utf-8')
        def fix_link(match):
            raw=match.group(2)
            if raw.startswith(('https:','http:','mailto:','#','data:')):return match.group(0)
            path=root/unquote(raw)
            if path.exists():return match.group(0)
            resolved=find_output_file(path.parent,path.name)
            if not resolved.is_file():return match.group(0)
            return 'href='+match.group(1)+quote(resolved.relative_to(root).as_posix(),safe='/')+match.group(1)
        revised=re.sub(r'href=([\"\'])(.*?)\1',fix_link,original)
        if revised!=original:project_nav.write_text(revised,encoding='utf-8')
    overview.append('</body></html>')
    (root/'00_结果导航.html').write_text('\n'.join(overview),encoding='utf-8')
    return grouped
