"""Manual ground-truth worksheet and audited tracking errors; never fill blank labels."""
from __future__ import annotations
import numpy as np
import pandas as pd


def make_review_sheet(track:pd.DataFrame,n=24):
    if not len(track):raise ValueError('没有待审核的帧')
    sel=np.unique(np.linspace(0,len(track)-1,min(n,len(track)),dtype=int))
    columns=['frame','time_s','detected','x_px','y_px','tracking_confidence']
    sheet=track.iloc[sel][columns].copy()
    sheet['人工_x_px']=np.nan
    sheet['人工_y_px']=np.nan
    sheet['审核备注']=''
    return sheet


def evaluate_reference(track:pd.DataFrame,reference:pd.DataFrame,mm_per_pixel:float):
    required=['frame','人工_x_px','人工_y_px']
    if not set(required).issubset(reference):raise ValueError('人工复核表须含 frame、人工_x_px、人工_y_px')
    annotated=reference.copy()
    for col in ('人工_x_px','人工_y_px'):
        annotated[col]=pd.to_numeric(annotated[col],errors='coerce')
    annotated=annotated.dropna(subset=['人工_x_px','人工_y_px'])
    if annotated.empty:return {'status':'NOT_LABELED','labeled_frames':0,'notice':'尚未填写人工真值；不计算准确率'},pd.DataFrame()
    if annotated.frame.duplicated().any():raise ValueError('人工复核表 frame 不允许重复')
    comparison=annotated[['frame','人工_x_px','人工_y_px']].merge(track[['frame','detected','x_px','y_px']],on='frame',how='left',validate='one_to_one')
    if comparison.detected.isna().any():raise ValueError('人工复核表含不属于本视频的帧号')
    comparison['error_px']=np.hypot(comparison.x_px-comparison['人工_x_px'],comparison.y_px-comparison['人工_y_px'])
    comparison['error_mm']=comparison.error_px*mm_per_pixel
    measured=comparison[comparison.detected].dropna(subset=['error_mm'])
    if measured.empty:
        return {'status':'NO_MATCHES','labeled_frames':len(comparison),'evaluated_frames':0},comparison
    result={'status':'VALIDATION_SAMPLE_ONLY','labeled_frames':len(comparison),'evaluated_frames':len(measured),
            'manually_reviewed_detection_rate':float(len(measured)/len(comparison)),
            'MAE_position_mm':float(measured.error_mm.mean()),
            'RMSE_position_mm':float(np.sqrt(np.mean(measured.error_mm.to_numpy()**2))),
            'P95_position_error_mm':float(np.quantile(measured.error_mm,.95)),
            'notice':'指标仅限人工核对样本帧；人工标注本身也需做标注一致性验证。'}
    return result,comparison
