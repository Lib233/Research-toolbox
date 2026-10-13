"""Batch mechanics import, trace-preserving exports and specimen-level summaries."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
from .adhesion_protocol import analyze_adhesion_protocol,AdhesionProtocol
from .common import read_table,identify_column,infer_source_unit,UNIT_SCALE


def load_force_folder(path,condition_col='condition',sample_col='sample_id',cycles=None,
                      time_col='time_s',displacement_col='displacement_mm',force_col='force_N',
                      normalize_units=False,time_unit='s',displacement_unit='mm',force_unit='N'):
    p=Path(path)
    if not p.is_dir():raise ValueError('请选择存在的实验数据文件夹')
    files=sorted([x for x in p.iterdir() if x.suffix.lower() in ('.csv','.tsv','.xlsx','.xlsm') and not x.name.startswith('~$')])
    if not files:raise ValueError('文件夹内没有可读取的 CSV/Excel 表格')
    assembled=[];manifest=[];issues=[]
    for f in files:
        try:
            d=read_table(f,sheet='auto' if f.suffix.lower() in ('.xlsx','.xlsm') else 0)
            found={}
            for configured,canonical in ((time_col,'time_s'),(displacement_col,'displacement_mm'),(force_col,'force_N')):
                if configured in d.columns:actual=configured
                else:actual=identify_column(d.columns,canonical)
                if actual is not None:found[actual]=canonical
            mapping=found
            missing={k for k in ('time_s','displacement_mm','force_N') if k not in mapping.values()}
            if missing:raise ValueError('缺少列 '+', '.join(sorted(missing)))
            if len(mapping)!=3:raise ValueError('时间、位移、力列必须选不同的列；请检查各个文件表头')
                                                                                       
            d=d.rename(columns=mapping)
            effective_units={}
            if normalize_units:
                for canonical,quantity,default in (('time_s','time',time_unit),
                    ('displacement_mm','displacement',displacement_unit),('force_N','force',force_unit)):
                    source=next(header for header,kind in mapping.items() if kind==canonical)
                    unit=infer_source_unit(source,quantity,default)
                    effective_units[canonical]=unit
                                                                                         
                    d[canonical]=pd.to_numeric(d[canonical],errors='raise')*UNIT_SCALE[quantity][unit]
            condition_origin='input_column' if condition_col in d else 'unknown'
            sample_origin='input_column' if sample_col in d else 'unknown'
            if condition_col not in d:
                candidate=identify_column(d.columns,'condition')
                if candidate is not None:
                    d[condition_col]=d[candidate];condition_origin='recognized_alias'
                else:
                    d[condition_col]=f.parent.name;condition_origin='folder_name_fallback'
            if sample_col not in d:
                candidate=identify_column(d.columns,'sample_id')
                if candidate is not None:
                    d[sample_col]=d[candidate];sample_origin='recognized_alias'
                else:
                    d[sample_col]=f.stem;sample_origin='filename_fallback'
                                                                                
            d['source_filename']=f.name
            assembled.append(d)
            manifest.append({'filename':f.name,'rows':len(d),'condition_values':str(d[condition_col].unique().tolist()),'status':'OK','column_mapping':str(mapping),'detected_units':str(effective_units),
                             'condition_origin':condition_origin,'sample_origin':sample_origin})
        except Exception as exc:
            issues.append(f'{f.name}: {exc}')
            manifest.append({'filename':f.name,'rows':0,'condition_values':'','status':str(exc)})
    if not assembled:raise ValueError('没有成功导入的文件。详情：'+str(issues))
    result=pd.concat(assembled,ignore_index=True)
    if condition_col!='condition':
        if 'condition' in result.columns:result=result.drop(columns=['condition'])
        result=result.rename(columns={condition_col:'condition'})
    if sample_col!='sample_id':
        if 'sample_id' in result.columns:result=result.drop(columns=['sample_id'])
        result=result.rename(columns={sample_col:'sample_id'})
    return result,pd.DataFrame(manifest),issues


def specimen_force_summary(metrics:pd.DataFrame):
    if not {'condition','sample_id','peak_force_N','separation_work_mJ'}.issubset(metrics):
        raise ValueError('试样汇总缺少必要字段')
    rowkeys=['condition','sample_id']
    dimensions=['peak_force_N','separation_work_mJ']+[c for c in ('peak_nominal_stress_kPa','work_per_nominal_area_J_m2') if c in metrics]
    groups=metrics.groupby(rowkeys,sort=False,as_index=False)
    out=groups[dimensions].mean()
    out['n_cycles']=groups.size()['size'].to_numpy()
    countby=out.groupby('condition').size().rename('n_independent')
    summary=out.groupby('condition',sort=False)[dimensions].agg(['mean','std','count'])
    summary.columns=['_'.join(c) for c in summary.columns];summary=summary.reset_index()
    summary['n_independent']=summary['condition'].map(countby)
    return out,summary
