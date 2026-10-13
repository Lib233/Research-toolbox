"""Optional auditable  indicators, derived from actual CSV results.

Never replaces original calculations or turns absence of evidence into an inference.
Every entry states its provenance and preconditions. No unvalidated p values.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

SCHEMA=['指标','数值','单位','来源','科研含义','限制']

def generate_insights(folder,module):
    p=Path(folder); rows=[]
    def read(filename):
        q=p/filename
        try:return pd.read_csv(q,encoding='utf-8-sig') if q.is_file() and q.stat().st_size else None
        except (ValueError,UnicodeDecodeError,pd.errors.EmptyDataError):return None
    def add(name,value,unit,source,meaning,caveat):
        if value is None:return
        try:
            val=float(value)
            if not np.isfinite(val):return
            rows.append([name,round(val,8),unit,source,meaning,caveat])
        except (TypeError,ValueError):return
    if module=='数据质检':
        q=read('column_quality.csv')
        if q is not None and len(q):
            for c,label in [('missing','缺失单元格数'),('iqr_outlier_flags','按IQR标记的可疑数字数')]:
                if c in q:add(label,pd.to_numeric(q[c],errors='coerce').sum(),'个','column_quality.csv','定位优先核查的数据问题','统计规则提示不是实验失效证据；重复值可能完全合理。')
    if module in ('力学分析','批量力学'):
        cycle=read('cycle_metrics.csv') if module=='批量力学' else read('adhesion_metrics.csv')
        if cycle is not None and len(cycle) and 'peak_force_N' in cycle:
            f=pd.to_numeric(cycle.peak_force_N,errors='coerce');f=f[np.isfinite(f)]
            add('可计算峰值力的测试轮数',len(f),'轮','cycle_metrics/adhesion_metrics.csv','此次成功获得峰值力的测试次数','轮数不是独立试样 n。')
            if len(f)>1 and f.mean()!=0:add('逐轮峰值力离散系数',f.std(ddof=1)/abs(f.mean())*100,'%','cycle_metrics/adhesion_metrics.csv','观察该批曲线结果的离散程度','混合条件/独立试样时不能用此值替代组内重复性。')
            if {'cycle_id','sample_id','condition'}.issubset(cycle):
                                                                                                         
                cycle=cycle.copy();cycle['cycle_numeric']=pd.to_numeric(cycle.cycle_id,errors='coerce')
                groups=0;negative=0
                for _,g in cycle.groupby(['condition','sample_id'],dropna=False):
                    g=g[['cycle_numeric','peak_force_N']].apply(pd.to_numeric,errors='coerce').dropna()
                    if len(g)>=3 and g.cycle_numeric.nunique()>=3:
                        groups+=1
                        negative+=int(np.polyfit(g.cycle_numeric,g.peak_force_N,1)[0]<0)
                if groups:add('至少3轮试样中峰值力呈下降趋势的比例',negative/groups*100,'%','cycle_metrics/adhesion_metrics.csv','粗略观察重复使用过程中是否可能衰减','仅线性趋势方向；不说明显著性或失效原因，测试顺序必须真实。')
    if module in ('视频追踪','轨迹人工修正'):
        f=read('frame_trajectory.csv') if module=='视频追踪' else read('trajectory_corrected.csv')
        if f is not None and len(f) and {'point_id','detected'}.issubset(f):
            for name,g in f.groupby('point_id',sort=False):
                if len(rows)>=12:break
                ok=g.detected.map(lambda x:str(x).strip().lower() in ('true','1','yes'))
                add('追踪有效帧比例 · '+str(name),ok.mean()*100,'%','frame_trajectory/trajectory_corrected.csv','该点多少比例记录具有有效追踪标记','不等于与真实物理位置一致的概率。')
    if module=='运动关系分析':
        s=read('motion_relation_summary.csv')
        if s is not None:
            for r in s.head(8).itertuples(index=False):
                add('有效跟踪记录比例 · '+str(r.target_point),r.valid_record_fraction*100,'%','motion_relation_summary.csv','该点有多少记录能够参与运动关系分析','低速阈值候选不等于真实支撑/吸附/步态。')
    if module=='显微图像':
        t=read('image_metrics.csv')
        if t is not None and len(t):
            if 'area_fraction' in t:add('目标区域平均覆盖百分比',pd.to_numeric(t.area_fraction,errors='coerce').mean()*100,'%','image_metrics.csv','分析区域内被识别为目标的像素平均比例','仅图像分割面积；目标身份需要实验成像原理支持。')
            add('已处理图像数量',len(t),'张','image_metrics.csv','生成指标的图片数量','不能视为独立生物学样本数量。')
    if module=='信号处理':
        t=read('filtered_signal.csv')
        if t is not None and len(t)>=3 and {'raw_value','filtered_value','time_s'}.issubset(t):
            raw=pd.to_numeric(t.raw_value,errors='coerce'); filt=pd.to_numeric(t.filtered_value,errors='coerce')
            if np.isfinite(raw).all() and np.isfinite(filt).all():
                add('原始与滤波信号的RMS差异',np.sqrt(np.mean((raw-filt)**2)),'源数值单位','filtered_signal.csv','量化滤波修改了原信号多少','不是噪声真值，也不能证明滤波后更准确。')
                dt=np.diff(pd.to_numeric(t.time_s).to_numpy(float));
                if np.all(dt>0):add('采样间隔最大相对偏差',np.max(abs(dt-np.median(dt)))/np.median(dt)*100,'%','filtered_signal.csv','检查时间采样是否接近均匀','频谱是否有效还需检查信号采样率、带宽和混叠。')
    if module=='多源同步':
        t=read('aligned_signals.csv')
        if t is not None and {'signal_A','signal_B'}.issubset(t) and len(t):
            both=np.isfinite(pd.to_numeric(t.signal_A,errors='coerce')) & np.isfinite(pd.to_numeric(t.signal_B,errors='coerce'))
            add('双信号同一时间点的有效覆盖率',both.mean()*100,'%','aligned_signals.csv','对齐后可同时比较两路信号的时间点比例','不证明真实硬件时钟已同步，也不证明信号因果关系。')
    if module=='独立样本统计':
        t=read('group_summary.csv')
        if t is not None and {'condition','mean','sd','n_independent'}.issubset(t):
            for r in t.head(8).itertuples(index=False):
                if r.mean and np.isfinite(r.sd):add('组内独立样本变异系数 · '+str(r.condition),abs(r.sd/r.mean)*100,'%','group_summary.csv','比较同一组独立试样结果相对均值的离散程度','接近0的均值不应使用CV；不自动判定组间显著性。')
    if module=='曲线拟合':
        t=read('fit_predictions_residuals.csv')
        if t is not None and len(t)>2 and {'measured','predicted'}.issubset(t):
            y=pd.to_numeric(t.measured,errors='coerce'); yp=pd.to_numeric(t.predicted,errors='coerce');v=(y-yp).dropna()
            if len(v)>=3:
                add('拟合平均绝对残差',v.abs().mean(),'响应源单位','fit_predictions_residuals.csv','真实观测与拟合值平均相差多少','训练集残差不是新实验的预测误差。')
                add('最大绝对残差',v.abs().max(),'响应源单位','fit_predictions_residuals.csv','指出最偏离模型的观测程度','可能有真实机理或测量异常，不能擅自删除。')
    if module=='实验数据优化':
        t=read('model_validation.csv')
        if t is not None:
            for r in t.head(6).to_dict('records'):
                response=str(r.get('response','指标'))
                if 'cv_MAE' in r and 'baseline_MAE' in r and pd.notna(r.get('baseline_MAE')) and float(r['baseline_MAE'])>0:
                    add('留组MAE相对均值基线减少 · '+response,(1-float(r['cv_MAE'])/float(r['baseline_MAE']))*100,'%','model_validation.csv','大于0代表比均值预测的绝对误差小','仅历史交叉验证比较，不代表下一次实验提高多少。')
    if module=='轨迹人工修正':
        audit=read('manual_changes_audit.csv')
        if audit is not None:
            add('本次人工更正的点数',len(audit),'点·帧','manual_changes_audit.csv','统计真实人工干预了多少个坐标','不是更正后的全部轨迹点数，仍要用叠加视频复核。')
    if module=='高级统计':
        t=read('advanced_statistics_report.csv')
        if t is not None and len(t)==1:
            r=t.iloc[0]
            if 'n_pairs' in t:add('完整配对的独立试样对数',r.get('n_pairs'),'对','advanced_statistics_report.csv','真正具有两个条件完整结果的试样对','不是两个条件各自的总测量次数。')
            if 'expanded_uncertainty' in t:
                add('合成后展开不确定度',r.get('expanded_uncertainty'),'与测量值同单位','advanced_statistics_report.csv','基于输入标准不确定度和指定覆盖因子的结果','输入必须是经正确评估的标准不确定度分量，并考虑相关性假设。')
    if module=='公式优化':
        hist=read('优化过程.csv')
        if hist is not None and len(hist):
            add('已保存的优化迭代回调次数',len(hist),'次','优化过程.csv','用于查看数值目标值是否继续改进','每个回调不等于一次完整函数求值，也不证明全局最优。')
    if module=='分析结果整理':
        doc=p/'manuscript_draft.md'
        if doc.is_file():
            add('方法与结果草稿长度',len(doc.read_text(encoding='utf-8-sig')),'字符','manuscript_draft.md','整理成文字的内容长度','这不是论文质量评分，方法和结果仍须科研人员逐项核对。')
    if module=='论文绘图':
        mapping=p/'figure_data_mapping.json'
        if mapping.is_file():
            import json
            cfg=json.loads(mapping.read_text(encoding='utf-8-sig'))
            add('已明确指定的图形数据列数',sum(bool(cfg.get(k)) for k in ('x_column','y_column','group_column','sample_id_column')),'列','figure_data_mapping.json','帮助核对坐标轴、分组及独立试样来源','未填写独立试样列时，不应自动将技术重复当作独立样本。')
    if module=='项目工作流':
        t=read('project_stage_audit.csv')
        if t is not None and len(t):
            col='status' if 'status' in t else None
            if col:
                add('已完成处理阶段的占比',t[col].astype(str).str.lower().isin(['complete','completed','ok','success']).mean()*100,'%','project_stage_audit.csv','各来源处理阶段完成程度','只代表软件执行完成，不保证所有指标可信或独立。')
    return pd.DataFrame(rows,columns=SCHEMA)
