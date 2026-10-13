"""Single-target, contrast-based 2-D image tracking. Not suitable for occluded/multi-robot videos."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
import pandas as pd

@dataclass
class TrackConfig:
    mm_per_pixel: float
    mode: str = 'dark'                                                                        
    threshold: int = 105
    min_area_px: float = 60
    max_area_px: float = 1e7
    step: int = 1
    max_processed_frames: int = 3000
    roi: tuple[int, int, int, int] | None = None                            
    climb_axis: str = 'up'                             
    segmentation: str = 'fixed'                              
    clahe: bool = False                                                                  
    max_jump_px: float = 0.0                                                          
    min_confidence: float = 0.0                                         

def _validate(c: TrackConfig):
    if not np.isfinite(c.mm_per_pixel) or c.mm_per_pixel <= 0:
        raise ValueError('mm_per_pixel must be a positive finite calibration.')
    if c.mode not in ('dark', 'bright') or c.climb_axis not in ('up', 'down', 'left', 'right'):
        raise ValueError('Bad segmentation mode or climb axis.')
    if not 0 <= c.threshold <= 255 or c.step < 1 or c.max_processed_frames < 1:
        raise ValueError('Invalid threshold, step, or max_processed_frames.')
    if c.segmentation not in ('fixed','otsu','adaptive') or c.max_jump_px < 0 or not 0<=c.min_confidence<=1:
        raise ValueError('Invalid segmentation strategy, maximum jump or confidence threshold.')
    if c.min_area_px <= 0 or c.max_area_px < c.min_area_px:
        raise ValueError('Check min/max contour area.')

def _detect(frame: np.ndarray, c: TrackConfig, last_point):
    height, width = frame.shape[:2]
    l, t, r, b = c.roi if c.roi is not None else (0, 0, width, height)
    if not (0 <= l < r <= width and 0 <= t < b <= height):
        raise ValueError(f'ROI outside frame bounds ({width}x{height}).')
    gray = cv2.cvtColor(frame[t:b, l:r], cv2.COLOR_BGR2GRAY)
    flag = cv2.THRESH_BINARY_INV if c.mode == 'dark' else cv2.THRESH_BINARY
    if c.clahe:
        gray = cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(gray)
    if c.segmentation=='fixed':
        _, mask = cv2.threshold(gray, c.threshold, 255, flag)
    elif c.segmentation=='otsu':
        _, mask = cv2.threshold(gray,0,255,flag | cv2.THRESH_OTSU)
    else:
        binary = cv2.THRESH_BINARY_INV if c.mode=='dark' else cv2.THRESH_BINARY
        mask = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,binary,31,3)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not c.min_area_px <= area <= c.max_area_px:
            continue
        mom = cv2.moments(contour)
        if mom['m00'] == 0:
            continue
        x = l + mom['m10'] / mom['m00']; y = t + mom['m01'] / mom['m00']
        rect = cv2.minAreaRect(contour)
        long_side = max(rect[1]); short_side = min(rect[1])
        aspect = float(long_side / short_side) if short_side > 0 else np.nan
        cx,cy=int(round(x-l)),int(round(y-t))
                                                                                  
        rx=max(0,cx-9);rx2=min(gray.shape[1],cx+10);ry=max(0,cy-9);ry2=min(gray.shape[0],cy+10)
        patch=gray[ry:ry2,rx:rx2]
        contrast=float(np.std(patch))/45 if patch.size else 0.
        confidence=float(np.clip(contrast,0,1))
        detections.append((x, y, area, aspect, contour, confidence))
    detections=[q for q in detections if q[5]>=c.min_confidence]
    if not detections:
        return None
                                                                               
    if last_point is None:
        return max(detections, key=lambda z: z[2])
    nearest=min(detections, key=lambda z: (z[0]-last_point[0])**2 + (z[1]-last_point[1])**2)
    if c.max_jump_px>0 and np.hypot(nearest[0]-last_point[0],nearest[1]-last_point[1])>c.max_jump_px:
        return None                                                            
    return nearest

def track_video(path: str | Path, c: TrackConfig) -> tuple[pd.DataFrame, np.ndarray]:
    _validate(c)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError('Cannot open video. Try AVI (MJPG) or an MP4 with supported codecs.')
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if not np.isfinite(fps) or fps <= 0:
        cap.release()
        raise ValueError('Video has no valid FPS; re-encode with frame-rate metadata.')
    rows = []; last = None; preview = None; frame_id = -1; processed = 0
    try:
        while processed < c.max_processed_frames:
            ok, frame = cap.read()
            if not ok:
                break
            frame_id += 1
            if frame_id % c.step:
                continue
            h = frame.shape[0]
            candidate = _detect(frame, c, last)
            row = dict(frame=frame_id, time_s=frame_id/fps, detected=False,
                       x_px=np.nan, y_px=np.nan, x_mm=np.nan, y_up_mm=np.nan,
                       area_px2=np.nan, aspect_ratio=np.nan, tracking_confidence=np.nan, tracking_source='未检出')
            if candidate is not None:
                x, y, area, aspect, _, confidence = candidate
                row.update(detected=True, x_px=x, y_px=y, x_mm=x*c.mm_per_pixel,
                           y_up_mm=(h-y)*c.mm_per_pixel, area_px2=area, aspect_ratio=aspect,
                           tracking_confidence=confidence, tracking_source=c.segmentation)
                last = (x, y)
                if preview is None:
                    preview = frame.copy()
                    cv2.circle(preview, (int(x), int(y)), 7, (0, 0, 255), 2)
            rows.append(row); processed += 1
    finally:
        cap.release()
    if not rows:
        raise ValueError('No readable frames found.')
    df = pd.DataFrame(rows)
    df['speed_mm_s'] = np.nan; df['climb_speed_mm_s'] = np.nan
                                                                                
    contiguous = df.detected & df.detected.shift(1, fill_value=False)
    dx = df.x_mm.diff(); dy = df.y_up_mm.diff(); dt = df.time_s.diff()
    speed = np.hypot(dx, dy)/dt
    axis = {'up':dy, 'down':-dy, 'right':dx, 'left':-dx}[c.climb_axis]
    df.loc[contiguous,'speed_mm_s'] = speed[contiguous]
    df.loc[contiguous,'climb_speed_mm_s'] = (axis/dt)[contiguous]
    df['position_validated'] = False                                                             
    return df, preview

def motion_summary(df: pd.DataFrame, axis='up') -> dict:
    found = df[df['detected']]
    summary = dict(frames_analyzed=len(df), detected_frames=len(found),
                   detection_rate=float(len(found)/len(df)), net_climb_mm=np.nan,
                   path_length_mm=np.nan, duration_s=np.nan,
                   mean_speed_mm_s=np.nan, mean_climb_speed_mm_s=np.nan,
                   longest_detection_gap_frames=0, reviewed_by_human=False)
    misses=(~df.detected).astype(int).to_numpy()
    gaps=[];k=0
    for q in misses:
        if q:k+=1
        else:gaps.append(k);k=0
    gaps.append(k)
    summary['longest_detection_gap_frames']=max(gaps,default=0)
    if found.empty:
        return summary
    duration = float(found.time_s.iloc[-1] - found.time_s.iloc[0])
    dx = float(found.x_mm.iloc[-1] - found.x_mm.iloc[0]); dy = float(found.y_up_mm.iloc[-1] - found.y_up_mm.iloc[0])
    net = {'up':dy,'down':-dy,'right':dx,'left':-dx}[axis]
                                                                
    valid_speeds = df['speed_mm_s'].dropna()
    summary.update(net_climb_mm=net, duration_s=duration,
       path_length_mm=float((df.speed_mm_s * df.time_s.diff()).sum()),
       mean_speed_mm_s=float(valid_speeds.mean()) if len(valid_speeds) else np.nan,
       mean_climb_speed_mm_s=float(df.climb_speed_mm_s.mean()) if df.climb_speed_mm_s.notna().any() else np.nan)
    return summary
