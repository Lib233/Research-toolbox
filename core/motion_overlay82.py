"""Video-frame annotation without altering source video or inventing missing points."""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
import pandas as pd

_PALETTE=[(232,122,44),(35,183,192),(190,96,225),(87,178,87),(220,186,55),(143,144,230)]

def frame_overlay(frame,track,frame_number:int,history=25,scale=1.0,show_names=True):
    """Overlay positions on COPY of source frame. Explicitly skip missing frames."""
    canvas=frame.copy();h,w=canvas.shape[:2]
    if history<0:history=0
    for j,(name,g) in enumerate(track.groupby('point_id',sort=False)):
        color=_PALETTE[j%len(_PALETTE)]
        g=g[(g.frame<=frame_number)&(g.frame>=frame_number-history)].sort_values('frame')
        g=g[g.detected.astype(bool)]
        if g.empty:continue
        points=np.column_stack([g.x_px,g.y_px]).astype(float)
        for i in range(1,len(points)):
            prev_frame=int(g.frame.iloc[i-1]);cur_frame=int(g.frame.iloc[i]);
            if cur_frame-prev_frame>max(1,int(round(np.median(np.diff(track[track.point_id==name].frame.unique())))) if len(track[track.point_id==name].frame.unique())>1 else 1):continue
            p0=tuple(np.round(points[i-1]).astype(int));p1=tuple(np.round(points[i]).astype(int))
            cv2.line(canvas,p0,p1,color,1,cv2.LINE_AA)
        row=track[(track.frame==frame_number)&(track.point_id==name)]
        if row.empty or not bool(row.detected.iloc[0]):continue
        x,y=map(float,[row.x_px.iloc[0],row.y_px.iloc[0]])
        cx,cy=int(round(x)),int(round(y))
        if not(0<=cx<w and 0<=cy<h):continue
        manual=bool(row.position_validated.iloc[0]) if 'position_validated' in row else False
        cv2.circle(canvas,(cx,cy),5,color,2,cv2.LINE_AA)
        if manual:cv2.circle(canvas,(cx,cy),8,(255,255,255),1,cv2.LINE_AA)
        if show_names:
            cv2.putText(canvas,str(name)[:24],(min(w-5,cx+9),max(14,cy-7)),cv2.FONT_HERSHEY_SIMPLEX,.46,(15,15,15),3,cv2.LINE_AA)
            cv2.putText(canvas,str(name)[:24],(min(w-5,cx+9),max(14,cy-7)),cv2.FONT_HERSHEY_SIMPLEX,.46,color,1,cv2.LINE_AA)
    cv2.rectangle(canvas,(0,0),(min(w-1,310),30),(12,21,26),-1)
    cv2.putText(canvas,f'Frame {frame_number} | marked = manual', (8,21),cv2.FONT_HERSHEY_SIMPLEX,.45,(235,242,242),1,cv2.LINE_AA)
    return canvas


def export_overlay_video(video_path,track,output_path,max_frames=0):
    """Write aligned preview including every decoded frame up to explicit cap.
    Returns metadata; if codec unavailable, raises rather than pretending success.
    """
    cap=cv2.VideoCapture(str(video_path))
    if not cap.isOpened():raise ValueError('不能读取源视频。')
    fps=cap.get(cv2.CAP_PROP_FPS)
    if not np.isfinite(fps) or fps<=0:cap.release();raise ValueError('FPS无效，无法写入复核视频。')
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    limit=int(max_frames) if int(max_frames)>0 else float("inf");outpath=Path(output_path)
    outpath.parent.mkdir(parents=True,exist_ok=True)
    wr=cv2.VideoWriter(str(outpath),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height))
    if not wr.isOpened():
        cap.release();raise ValueError('本机没有可用的 MP4 视频编码器；CSV 与图表仍然保留。')
    n=0
    try:
        while n<limit:
            ok,frame=cap.read()
            if not ok:break
            wr.write(frame_overlay(frame,track,n));n+=1
    finally:cap.release();wr.release()
    if n==0:outpath.unlink(missing_ok=True);raise ValueError('源视频没有可解码的视频帧。')
                                                                                
    original_total=int(track.frame.max()+1) if not track.empty else 0
    return {'review_video_frames':n,'review_video_truncated':bool(np.isfinite(limit) and n>=limit and original_total>limit),'review_video_filename':outpath.name}
