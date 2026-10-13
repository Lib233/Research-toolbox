"""Shared I/O, validation and reproducible output folders. No spreadsheet is silently modified."""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

VERSION='10.2.0'

                                                                                              
ALIASES={
 'time_s':('time_s','time (s)','time[s]','time/s','time(ms)','time [ms]','time (ms)','time','时间(ms)','时间(毫秒)','时间(s)','时间（秒）','时间/秒','时间'),
 'displacement_mm':('displacement_mm','displacement (mm)','displacement(mm)','extension (mm)','position (mm)','position (um)','displacement (um)','displacement (µm)','displacement (μm)','位移(μm)','位移(um)','位移(mm)','位移（毫米）','位移'),
 'force_N':('force_N','force (n)','force(n)','force(mn)','force (mn)','force (un)','force(un)','load (n)','load (mn)','force','load','载荷(n)','载荷(mn)','力(n)','力(mn)','拉力(n)','载荷','力'),
 'condition':('condition','group','condition_name','surface','组别','实验组','条件','分组'),
 'sample_id':('sample_id','specimen_id','sample','specimen','试样编号','样品编号','样本编号','样品id'),
 'cycle_id':('cycle_id','cycle','循环编号','循环次数'),
 'value':('value','measurement','reading','测量值','测量结果','读数'),
 'x':('x','x_value','自变量'), 'y':('y','y_value','因变量'),
 'batch':('batch','batch_id','批次','实验批次'),
 'experiment_id':('experiment_id','experiment','实验编号'),
}
def _header_normalize(value):
    return re.sub(r'[\s_\-：:]+','',str(value).casefold().strip())

def identify_column(cols,canonical):
    names=list(map(str,cols))
    if canonical in names:return canonical
    allowed={_header_normalize(v) for v in ALIASES.get(canonical,())}
    hits=[n for n in names if _header_normalize(n) in allowed]
    return hits[0] if len(hits)==1 else None

def guess_mapping(cols,keys):
    return {key:identify_column(cols,key) for key in keys}


def infer_source_unit(header,quantity,default):
    """Extract only explicitly recognizable instrument units, never infer from values."""
    h=str(header).strip().casefold().replace('μ','µ').replace('（','(').replace('）',')')
    token=None
    bracket=re.search(r'[\(\[]\s*([^\)\]]+)\s*[\)\]]',h)
    if bracket:token=bracket.group(1).strip()
    if token is None:
        for ending in ('_mn','_un','_n','_ms','_sec','_s','_um','_µm','_mm','_m'):
            if h.endswith(ending):token=ending[1:];break
    if token is None:return default
    if quantity=='force':
        return {'n':'N','mn':'mN','un':'uN','µn':'uN','gf':'gf','kgf':'kgf'}.get(token,default)
    if quantity=='time':return {'s':'s','sec':'s','秒':'s','ms':'ms','毫秒':'ms'}.get(token,default)
    if quantity=='displacement':return {'mm':'mm','um':'um','µm':'um','m':'m','毫米':'mm','微米':'um'}.get(token,default)
    return default

UNIT_SCALE={'force':{'N':1.0,'mN':.001,'uN':1e-6,'gf':.00980665,'kgf':9.80665},
            'time':{'s':1.0,'ms':.001},'displacement':{'mm':1.0,'um':.001,'m':1000.0}}

def _read_csv_with_headers(p,encoding):
                                                                                          
    sample=p.read_text(encoding=encoding)[:16000].splitlines()[:25]
    delimiter_scores={c:sum(max(0,line.count(c)-1) for line in sample) for c in (',','\t',';')}
    sep='\t' if p.suffix.lower()=='.tsv' else (max(delimiter_scores,key=delimiter_scores.get) if max(delimiter_scores.values())>0 else ',')
    best=None;bestscore=-1
                                                                                         
    for headerrow in range(11):
        try:
            trial=pd.read_csv(p,sep=sep,engine='python',encoding=encoding,header=headerrow,nrows=60)
        except (pd.errors.ParserError,ValueError,IndexError,StopIteration):continue
        if trial.empty:continue
        names=list(trial.columns.astype(str))
        match=sum(identify_column(names,k) is not None for k in ('time_s','force_N','displacement_mm','condition','sample_id','value','x','y'))
        unnamed=sum(n.lower().startswith('unnamed:') for n in names)
        score=match*5-unnamed*3-headerrow*.4
        if headerrow==0:score+=1
        if score>bestscore:best=headerrow;bestscore=score
        if headerrow==0 and match>=2 and unnamed==0:break
    if best is None:raise ValueError('无法找到有数据的表头；请检查原始文件。')
    return pd.read_csv(p,sep=sep,engine='python',encoding=encoding,header=best)

def read_table(path,sheet=0):
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(f'找不到文件：{p}')
    if p.suffix.lower() in ('.xlsx','.xlsm'):
        try:
            if sheet!='auto': d=pd.read_excel(p,sheet_name=sheet)
            else:
                book=pd.ExcelFile(p);options=[]
                for sheetname in book.sheet_names[:12]:
                    trial=pd.read_excel(book,sheet_name=sheetname,nrows=60)
                    if trial.empty:continue
                    score=sum(identify_column(trial.columns,k) is not None for k in ('time_s','force_N','displacement_mm','value','condition','sample_id','x','y'))
                    options.append((score,sheetname))
                if not options:raise ValueError('Excel 的前12个工作表均没有数据')
                chosen=max(options,key=lambda item:item[0])[1]
                d=pd.read_excel(book,sheet_name=chosen)
        except ImportError as e:raise ValueError('读取 Excel 需要 openpyxl；请检查依赖安装。') from e
    elif p.suffix.lower() in ('.csv','.txt','.tsv'):
        try:d=_read_csv_with_headers(p,'utf-8-sig')
        except UnicodeDecodeError:d=_read_csv_with_headers(p,'gb18030')
    else: raise ValueError('表格请选择 .csv / .tsv / .xlsx / .xlsm 文件')
    d.columns=d.columns.astype(str).str.strip()
    if d.empty:raise ValueError('输入表没有数据行。')
    if d.columns.duplicated().any():raise ValueError('列名不能重复。')
    return d

def columns(df, mapping, optional=()):
    """Map user-selected source headers to canonical names, no implicit guesses."""
    out=df.copy()
    for canonical,header in mapping.items():
        if header in (None,''): continue
        if header not in out: raise ValueError(f'找不到列“{header}”，可用列：{list(df.columns)}')
        if header != canonical and canonical in out and canonical not in mapping.values():
            raise ValueError(f'列映射冲突：{canonical}')
    ren={v:k for k,v in mapping.items() if v and k != v}
    if len(ren)!=len([v for k,v in mapping.items() if v and k != v]): raise ValueError('一列不能映射成两个字段。')
    return out.rename(columns=ren)

def safe_numeric(s,name):
    a=pd.to_numeric(s, errors='coerce')
    if a.isna().any() or not np.isfinite(a.to_numpy(float)).all():
        raise ValueError(f'“{name}”含空白/文字/非有限数字，请先修正后再运行。')
    return a.astype(float)

def save_csv(df,path):
                                                                       
    df.to_csv(path,index=False,encoding='utf-8-sig',float_format='%.10g')

def save_json(data,path):
    def clean(o):
        if isinstance(o,dict):return {str(k):clean(v) for k,v in o.items()}
        if isinstance(o,(list,tuple)):return [clean(v) for v in o]
        if isinstance(o,(np.integer,)):return int(o)
        if isinstance(o,(np.floating,float)):
            x=float(o);return x if np.isfinite(x) else None
        if isinstance(o,(np.bool_,)):return bool(o)
        return o
    Path(path).write_text(json.dumps(clean(data),ensure_ascii=False,indent=2),encoding='utf-8')

def create_run(output_parent, module, inputs, parameters):
    output=Path(output_parent).expanduser();output.mkdir(parents=True,exist_ok=True)
    slug={'数据质检':'quality','力学分析':'force','视频追踪':'video','显微图像':'imaging','信号处理':'signal','独立样本统计':'stats','曲线拟合':'fitting','公式优化':'formula_opt','实验数据优化':'surrogate_opt','写作辅助':'writing','分析结果整理':'writing','多源同步':'sync','论文绘图':'figures','批量力学':'batch_force','高级统计':'advanced_stats','轨迹人工修正':'track_review','项目工作流':'project'}.get(module,'analysis')
    folder=output/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+slug)
    folder.mkdir(parents=True,exist_ok=False)
    hashes={}
    expanded_inputs=[]
    for item in inputs:
        if item and Path(item).is_dir():
            expanded_inputs.extend(sorted(f for f in Path(item).iterdir() if f.is_file()))
        elif item:expanded_inputs.append(Path(item))
    for p in expanded_inputs:
        if p and Path(p).is_file():
            dig=hashlib.sha256()
            with open(p,'rb') as f:
                for b in iter(lambda:f.read(1048576),b''):dig.update(b)
            hashes[str(Path(p).resolve())]=dig.hexdigest()
    save_json({'version':VERSION,'module':module,'created':datetime.now().isoformat(timespec='seconds'),
               'source_sha256':hashes,'parameters':parameters,
               'notice':'研究辅助计算。必须人工审核原始数据、标定、统计独立性与实验假设。'},folder/'run_metadata.json')
    return folder

def save_plot(fig,prefix,cfg=None):
    from .figure_engine import FigureOptions, export_figure
    return export_figure(fig,prefix,FigureOptions.from_config(cfg or {}))

def clean_report(df):
    rows=[]
    for name in df.columns:
        s=df[name]; n=int(s.isna().sum()); numeric=pd.to_numeric(s,errors='coerce')
        valid=numeric.notna() & np.isfinite(numeric)
        q1,q3=(float(numeric[valid].quantile(.25)),float(numeric[valid].quantile(.75))) if valid.sum()>=4 else (np.nan,np.nan)
        iqr=q3-q1
        out=int(((numeric[valid]<q1-1.5*iqr)|(numeric[valid]>q3+1.5*iqr)).sum()) if np.isfinite(iqr) and iqr>0 else 0
        rows.append(dict(column=name,dtype=str(s.dtype),rows=len(s),missing=n,numeric_valid=int(valid.sum()),
                         duplicates_in_column=int(s.dropna().duplicated().sum()),iqr_outlier_flags=out))
    return pd.DataFrame(rows)

def export_result_workbook(folder):
    """Collect only table outputs into an optional Excel workbook for Origin/Excel users.

    Does not modify data; preserves each CSV verbatim in parallel.
    """
    p=Path(folder)
    tabfiles=sorted(f for f in p.glob('*.csv') if f.stat().st_size<15_000_000)
    if not tabfiles:return None
    workbook=p/'analysis_tables.xlsx'
    with pd.ExcelWriter(workbook,engine='openpyxl') as writer:
        used=set()
        for i,f in enumerate(tabfiles):
            label=re.sub(r'[\\/*?:\[\]]','_',f.stem)[:31] or f'table_{i+1}'
            if label in used:label=(label[:26]+f'_{i+1}')[:31]
            used.add(label)
            try:
                d=read_table(f)
            except ValueError:
                                                                                   
                                                                          
                try:d=pd.read_csv(f,encoding='utf-8-sig')
                except (ValueError,pd.errors.EmptyDataError):continue
            if d.shape[0]>1_048_000:continue
            d.to_excel(writer,sheet_name=label,index=False)
    return workbook


def locate_quality_issues(df):
    """Locate missing, numeric-format and IQR flags without deleting any row.

    The row number counts data records starting at 1, not physical CSV/Excel
    line numbers, since instrument preambles and spreadsheet headings vary.
    Categorical labels are never flagged merely for being nonnumeric or repeated.
    """
    findings=[]
    numeric_aliases={'time_s','displacement_mm','force_N','value','x','y'}
    for col in df.columns:
        raw=df[col]
        numeric=pd.to_numeric(raw,errors='coerce')
        valid=numeric.notna() & np.isfinite(numeric)
        numeric_expected=(any(identify_column([col],key)==col for key in numeric_aliases)
                          or (int(raw.notna().sum())>0 and float(valid.sum())/raw.notna().sum()>=.8))
        for i in np.flatnonzero(raw.isna().to_numpy()):
            findings.append({'数据行序号(从1开始)':int(i+1),'原始列名':col,'原始内容':'',
                             '问题类型':'空白或已识别缺失','建议怎么核对':'检查仪器记录；不要擅自把缺失填成0'})
        if numeric_expected:
            bad=(raw.notna() & ~valid).to_numpy()
            for i in np.flatnonzero(bad):
                findings.append({'数据行序号(从1开始)':int(i+1),'原始列名':col,'原始内容':str(raw.iloc[i]),
                                 '问题类型':'预期数值列中不能读成有限数字','建议怎么核对':'核对原始字符、缺失编码及单位；可能不是数值列，先确认列用途'})
        if int(valid.sum())>=4:
            values=numeric[valid]
            q1,q3=values.quantile([.25,.75]);span=q3-q1
            if np.isfinite(span) and span>0:
                unusual=(valid & ((numeric<q1-1.5*span)|(numeric>q3+1.5*span))).to_numpy()
                for i in np.flatnonzero(unusual):
                    findings.append({'数据行序号(从1开始)':int(i+1),'原始列名':col,'原始内容':str(raw.iloc[i]),
                                     '问题类型':'IQR 离群值提醒','建议怎么核对':'可能是真实极端测量；结合实验背景判断，不自动删除'})
    for i in np.flatnonzero(df.duplicated().to_numpy()):
        findings.append({'数据行序号(从1开始)':int(i+1),'原始列名':'(整行)','原始内容':'（与之前某行所有字段相同）',
                         '问题类型':'整行重复提醒','建议怎么核对':'确认是否重复导入或本来就存在相同记录；不能直接删除'})
    return pd.DataFrame(findings,columns=['数据行序号(从1开始)','原始列名','原始内容','问题类型','建议怎么核对'])
