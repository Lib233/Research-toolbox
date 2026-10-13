""" physically conditional 3-D geometry (stereo and rigid calibrated PnP).

No monocular single-point depth guesses. Outputs are in camera-1 coordinates
(X right, Y down, Z forward), physical millimeters only from measured calibration.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import cv2
from scipy.spatial.transform import Rotation


def load_calibration(src):
    d=json.loads(Path(src).read_text(encoding='utf-8-sig')) if not isinstance(src,dict) else src
    k={}
    for c in ('K1','D1','K2','D2','R','T_mm'):
        if c in d:k[c]=np.asarray(d[c],dtype=np.float64)
    if 'K1' not in k:raise ValueError('标定 JSON 缺少 K1 内参矩阵；不能猜测焦距。')
    if k['K1'].shape!=(3,3) or k['K1'][0,0]<=0 or k['K1'][1,1]<=0:raise ValueError('K1 无效。')
    if 'D1' not in k:k['D1']=np.zeros(5)
    if not all(np.isfinite(a).all() for a in k.values()):raise ValueError('标定矩阵包含非有限数字。')
    k['image_width']=int(d.get('image_width',0));k['image_height']=int(d.get('image_height',0))
    if k['image_width']<=0 or k['image_height']<=0:raise ValueError('标定文件必须包含原图 image_width、image_height。')
    if 'R' in k or 'T_mm' in k:
        if not all(x in k for x in ('K2','D2','R','T_mm')):raise ValueError('双目标定缺少 K2/D2/R/T_mm。')
        if k['K2'].shape!=(3,3) or k['R'].shape!=(3,3) or k['T_mm'].size!=3:raise ValueError('双目标定矩阵维度不正确。')
        if not np.allclose(k['R'].T@k['R'],np.eye(3),atol=.02) or abs(np.linalg.det(k['R'])-1)>.02:raise ValueError('R 不是有效的旋转矩阵。')
        if np.linalg.norm(k['T_mm'])<=1e-5:raise ValueError('左右相机基线为零，无法三角测量。')
        if k['K2'][0,0]<=0 or k['K2'][1,1]<=0:raise ValueError('K2 无效。')
    return k


def _corners(gray,shape):
    if hasattr(cv2,'findChessboardCornersSB'):
        ok,c=cv2.findChessboardCornersSB(gray,shape,flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
    else:
        ok,c=cv2.findChessboardCorners(gray,shape)
    if not ok:return None
                                                                          
    return cv2.cornerSubPix(gray,np.float32(c),(5,5),(-1,-1),
               (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,35,0.01)).reshape(-1,2).astype(np.float32)


def calibrate_stereo_chessboard(left_folder,right_folder,cols,rows,square_mm,min_pairs=10):
    """Image pairs MUST share filenames; checkerboard cols/rows are INNER corners.

    Reject too few patterns; camera poses require different angles/distances.
    """
    left,right=Path(left_folder),Path(right_folder)
    cols,rows=int(cols),int(rows);square_mm=float(square_mm)
    if cols<4 or rows<3 or not (np.isfinite(square_mm) and square_mm>0):raise ValueError('棋盘格内角点和每格边长必须合理。')
    ext={'.jpg','.jpeg','.png','.bmp','.tif','.tiff'}
    la={p.name:p for p in left.iterdir() if p.suffix.lower() in ext}
    ra={p.name:p for p in right.iterdir() if p.suffix.lower() in ext}
    common=sorted(set(la)&set(ra))
    if len(common)<min_pairs:raise ValueError(f'只有 {len(common)} 对同名标定图，至少需要 {min_pairs} 对不同姿态。')
    ob=np.zeros((rows*cols,3),dtype=np.float32)
    ob[:,:2]=np.mgrid[0:cols,0:rows].T.reshape(-1,2)*square_mm
    obs=[];p1=[];p2=[];size=None;used=[]
    for name in common:
        a=cv2.imread(str(la[name]),cv2.IMREAD_GRAYSCALE);b=cv2.imread(str(ra[name]),cv2.IMREAD_GRAYSCALE)
        if a is None or b is None:continue
        if a.shape!=b.shape:raise ValueError(f'标定图 {name} 左右分辨率不同。')
        if size is None:size=(a.shape[1],a.shape[0])
        if (a.shape[1],a.shape[0])!=size:raise ValueError('标定图分辨率不一致；禁止混用缩放过的照片。')
        c1=_corners(a,(cols,rows));c2=_corners(b,(cols,rows))
        if c1 is not None and c2 is not None:
            obs.append(ob.copy());p1.append(c1.reshape(-1,1,2));p2.append(c2.reshape(-1,1,2));used.append(name)
    if len(used)<min_pairs:raise ValueError(f'成功识别 {len(used)} 对棋盘格，少于 {min_pairs} 对；请改善角度/对焦后重拍。')
    term=(cv2.TERM_CRITERIA_MAX_ITER+cv2.TERM_CRITERIA_EPS,150,1e-8)
    r1,K1,D1,_,_=cv2.calibrateCamera(obs,p1,size,None,None,criteria=term)
    r2,K2,D2,_,_=cv2.calibrateCamera(obs,p2,size,None,None,criteria=term)
    rms,K1,D1,K2,D2,R,T,E,F=cv2.stereoCalibrate(obs,p1,p2,K1,D1,K2,D2,size,
                        flags=cv2.CALIB_FIX_INTRINSIC,criteria=term)
    t=np.ravel(T)
    if np.linalg.norm(t)<1e-4:raise ValueError('估计的双相机间距近乎为零，标定不可信。')
    result=dict(schema='research_toolbox_stereo84',image_width=size[0],image_height=size[1],
            K1=K1.tolist(),D1=D1.reshape(-1).tolist(),K2=K2.tolist(),D2=D2.reshape(-1).tolist(),
            R=R.tolist(),T_mm=t.tolist(),calibration_pairs=len(used),pair_files=used,
            chessboard_inner_corners=[cols,rows],square_mm=square_mm,
            rms_left_px=float(r1),rms_right_px=float(r2),rms_stereo_px=float(rms),
            note='相机1坐标系；X右、Y下、Z前，单位毫米。标定质量仍须独立验证。')
    load_calibration(result)
    return result


def _size_check(data,k,tag):
    if {'frame_width_px','frame_height_px'}.issubset(data.columns):
        size=data[['frame_width_px','frame_height_px']].dropna().drop_duplicates()
        if len(size)>1 or (len(size) and (int(size.iloc[0,0])!=k['image_width'] or int(size.iloc[0,1])!=k['image_height'])):
            raise ValueError(f'{tag} 视频分辨率与标定分辨率不同；禁止自动缩放相机内参。')


def _validated_track(d,name):
    cols={'frame','time_s','point_id','detected','x_px','y_px'}
    if not cols.issubset(d):raise ValueError(f'{name} 轨迹 CSV 缺少列：{sorted(cols-set(d.columns))}')
    if d.duplicated(['frame','point_id']).any():raise ValueError(f'{name} 同帧同点有重复记录。')
    v=d.copy();v['point_id']=v.point_id.astype(str)
    for c in ('frame','time_s','x_px','y_px'):v[c]=pd.to_numeric(v[c],errors='coerce')
    v['detected']=v.detected.map(lambda x:str(x).strip().lower() in ('true','1','yes'))
    return v


def stereo_triangulate(left,right,calibration,offset_right_s=0.,tolerance_s=.012,
                       max_reprojection_px=2.,min_ray_angle_deg=.5):
    """Match at time after verified clock shift, triangulate rectified normalized rays.

    Reprojection error checked with ORIGINAL distorted pixels; reject negative depth,
    low ray angle, temporal mismatch; do not fill missing coordinates.
    """
    k=load_calibration(calibration)
    if not all(p in k for p in ('K2','R','T_mm')):raise ValueError('需要已标定的两个相机：K1/K2/D1/D2/R/T_mm。')
    lo=_validated_track(left,'相机1');ri=_validated_track(right,'相机2')
    _size_check(lo,k,'相机1');_size_check(ri,k,'相机2')
    if not all(np.isfinite(float(x)) for x in (offset_right_s,tolerance_s,max_reprojection_px,min_ray_angle_deg)) or tolerance_s<=0 or max_reprojection_px<=0 or min_ray_angle_deg<0:
        raise ValueError('时间差、容差和重投影阈值不正确。')
    ri['time_right_original_s']=ri.time_s
    ri['time_match_s']=ri.time_s+float(offset_right_s)
    output=[]
    P1=np.hstack([np.eye(3),np.zeros((3,1))]);P2=np.hstack([k['R'],k['T_mm'].reshape(3,1)])
    center2=-k['R'].T@k['T_mm'].reshape(3)
    for point,g in lo.groupby('point_id',sort=False):
        h=ri[ri.point_id==point].copy()
        gg=g.sort_values('time_s').reset_index(drop=True)
        if h.empty:
            for z in gg.to_dict('records'):output.append(dict(frame=int(z['frame']),time_s=float(z['time_s']),point_id=point,valid_3d=False,quality='NO_MATCHED_POINT',x_mm=np.nan,y_mm=np.nan,z_mm=np.nan))
            continue
        h=h.sort_values('time_match_s')
        match=pd.merge_asof(gg,h,left_on='time_s',right_on='time_match_s',direction='nearest',tolerance=tolerance_s,suffixes=('_left','_right'))
                                                                              
                                                                                  
        repeated=match.frame_right.notna() & match.frame_right.duplicated(keep=False)
        if repeated.any():
            for rf,ids in match.loc[repeated].groupby('frame_right').groups.items():
                candidates=match.loc[list(ids)]
                delta=(candidates.time_s_left-candidates.time_match_s).abs()
                keep=delta.idxmin()
                for ix in ids:
                    if ix!=keep:match.loc[ix,'frame_right']=np.nan
        for r in match.itertuples(index=False):
            d=r._asdict();frame=int(d['frame_left']);time=float(d['time_s_left'])
            row=dict(frame=frame,time_s=time,point_id=point,valid_3d=False,quality='UNAVAILABLE',x_mm=np.nan,y_mm=np.nan,z_mm=np.nan,
                     reprojection_error_left_px=np.nan,reprojection_error_right_px=np.nan,ray_angle_deg=np.nan,depth_sensitivity_mm_per_px=np.nan,
                     time_difference_s=np.nan,frame_right=np.nan,speed_3d_mm_s=np.nan)
            if not np.isfinite(d.get('frame_right',np.nan)):row['quality']='NO_SYNCHRONIZED_FRAME';output.append(row);continue
            row['frame_right']=int(d['frame_right']);row['time_difference_s']=abs(time-float(d['time_match_s']))
            if not (d.get('detected_left') and d.get('detected_right')):
                row['quality']='TRACK_LOST';output.append(row);continue
            uv1=np.array([d.get('x_px_left'),d.get('y_px_left')],dtype=float)
            uv2=np.array([d.get('x_px_right'),d.get('y_px_right')],dtype=float)
            if not (np.isfinite(uv1).all() and np.isfinite(uv2).all()):row['quality']='INVALID_PIXEL';output.append(row);continue
            a=cv2.undistortPoints(uv1.reshape(1,1,2),k['K1'],k['D1']).reshape(2,1)
            b=cv2.undistortPoints(uv2.reshape(1,1,2),k['K2'],k['D2']).reshape(2,1)
            homog=cv2.triangulatePoints(P1,P2,a,b)[:,0]
            if abs(homog[3])<1e-12:row['quality']='ILL_CONDITIONED';output.append(row);continue
            xyz=homog[:3]/homog[3];xyz2=k['R']@xyz+k['T_mm'].reshape(3)
            if not (np.isfinite(xyz).all() and xyz[2]>0 and xyz2[2]>0):row['quality']='NEGATIVE_OR_INVALID_DEPTH';output.append(row);continue
            ray1=xyz/np.linalg.norm(xyz);ray2=(xyz-center2)/np.linalg.norm(xyz-center2)
            angle=float(np.degrees(np.arccos(np.clip(np.dot(ray1,ray2),-1,1))))
            row['ray_angle_deg']=angle
            if angle<min_ray_angle_deg:row['quality']='WEAK_STEREO_GEOMETRY';output.append(row);continue
            pleft,_=cv2.projectPoints(xyz.reshape(1,3),np.zeros(3),np.zeros(3),k['K1'],k['D1'])
            pright,_=cv2.projectPoints(xyz.reshape(1,3),cv2.Rodrigues(k['R'])[0],k['T_mm'].reshape(3),k['K2'],k['D2'])
            er1=float(np.linalg.norm(pleft.reshape(2)-uv1));er2=float(np.linalg.norm(pright.reshape(2)-uv2))
            row.update(reprojection_error_left_px=er1,reprojection_error_right_px=er2)
            if max(er1,er2)>max_reprojection_px:row['quality']='HIGH_REPROJECTION_ERROR';output.append(row);continue
                                                                                      
                                                                            
            perturbed=cv2.undistortPoints((uv1+np.array([1.,0.])).reshape(1,1,2),k['K1'],k['D1']).reshape(2,1)
            displaced=cv2.triangulatePoints(P1,P2,perturbed,b)[:,0]
            if abs(displaced[3])>1e-12:
                trial=displaced[:3]/displaced[3]
                if np.isfinite(trial[2]):row['depth_sensitivity_mm_per_px']=float(abs(trial[2]-xyz[2]))
            row.update(valid_3d=True,quality='VALID',x_mm=float(xyz[0]),y_mm=float(xyz[1]),z_mm=float(xyz[2]))
            output.append(row)
    df=pd.DataFrame(output).sort_values(['point_id','time_s']).reset_index(drop=True)
    for _,group in df.groupby('point_id',sort=False):
        ordered=group.sort_values('time_s')
        good=ordered.valid_3d & ordered.valid_3d.shift(1,fill_value=False)
        dt=ordered.time_s.diff()
        if len(dt.dropna())>0:
            normal=float(np.median(dt[dt>0]));good=good&(dt<=1.6*normal)&(dt>0)
        else:good=good & False
        ds=np.sqrt(sum(ordered[c].diff()**2 for c in ('x_mm','y_mm','z_mm')))
        df.loc[ordered.index[good],'speed_3d_mm_s']=(ds[good]/dt[good]).to_numpy()
    return df


def pnp_rigid_pose(track,geometry,calibration,max_reprojection_px=2.0):
    """Known rigid CAD geometry ONLY; pose per frame (NOT deformable insect wings)."""
    k=load_calibration(calibration);tr=_validated_track(track,'刚体');_size_check(tr,k,'刚体')
    if not {'point_id','X_mm','Y_mm','Z_mm'}.issubset(geometry):raise ValueError('刚体几何表须包含 point_id,X_mm,Y_mm,Z_mm。')
    g=geometry.copy();g.point_id=g.point_id.astype(str)
    if g.point_id.duplicated().any():raise ValueError('刚体点名不能重复。')
    if not np.isfinite(g[['X_mm','Y_mm','Z_mm']].to_numpy(float)).all():raise ValueError('刚体尺寸必须是有限数值。')
    if len(g)<4:raise ValueError('已知刚体模型至少4个对应特征点。')
    pts3=g[['X_mm','Y_mm','Z_mm']].to_numpy(float)
    if np.linalg.matrix_rank(pts3-pts3.mean(axis=0))<2:raise ValueError('已知点不能全共线。')
    outputs=[]
    for frame,d in tr.groupby('frame'):
        selected=d[d.detected].merge(g,on='point_id',validate='one_to_one')
        row=dict(frame=int(frame),time_s=float(d.time_s.iloc[0]),valid_pose=False,quality='INSUFFICIENT_VISIBLE_RIGID_POINTS',
                 n_correspondences=len(selected),n_inliers=0,reprojection_rmse_px=np.nan,
                 tx_mm=np.nan,ty_mm=np.nan,tz_mm=np.nan,roll_deg=np.nan,pitch_deg=np.nan,yaw_deg=np.nan)
        if len(selected)<4:outputs.append(row);continue
        xyz=np.ascontiguousarray(selected[['X_mm','Y_mm','Z_mm']].to_numpy(float));uv=np.ascontiguousarray(selected[['x_px','y_px']].to_numpy(float))
        if not np.isfinite(uv).all():outputs.append(row);continue
        try:
            success,rvec,tvec,inliers=cv2.solvePnPRansac(xyz,uv,k['K1'],k['D1'],iterationsCount=180,reprojectionError=max_reprojection_px,confidence=.995,flags=cv2.SOLVEPNP_EPNP)
        except cv2.error:success=False
        if not success or inliers is None or len(inliers)<4:row['quality']='PNP_NO_CONSENSUS';outputs.append(row);continue
        idx=inliers.ravel()
        if hasattr(cv2,'solvePnPRefineLM'):
            rvec,tvec=cv2.solvePnPRefineLM(xyz[idx],uv[idx],k['K1'],k['D1'],rvec,tvec)
        reproject,_=cv2.projectPoints(xyz[idx],rvec,tvec,k['K1'],k['D1'])
        rmse=float(np.sqrt(np.mean(np.sum((reproject.reshape(-1,2)-uv[idx])**2,axis=1))))
        world= (cv2.Rodrigues(rvec)[0]@xyz[idx].T).T+tvec.reshape(1,3)
        if np.any(world[:,2]<=0) or rmse>max_reprojection_px:
            row['quality']='PNP_REPROJECTION_OR_DEPTH_FAILED';outputs.append(row);continue
        angles=Rotation.from_matrix(cv2.Rodrigues(rvec)[0]).as_euler('xyz',degrees=True)
        row.update(valid_pose=True,quality='VALID',n_inliers=len(idx),reprojection_rmse_px=rmse,
                   tx_mm=float(tvec[0,0]),ty_mm=float(tvec[1,0]),tz_mm=float(tvec[2,0]),
                   roll_deg=float(angles[0]),pitch_deg=float(angles[1]),yaw_deg=float(angles[2]))
        outputs.append(row)
    return pd.DataFrame(outputs)


def stereo_pair_distances(track):
    good=track[track.valid_3d].copy()
    out=[]
    for frame,g in good.groupby('frame'):
        pts=g[['point_id','x_mm','y_mm','z_mm']].to_records(index=False)
        for i in range(len(pts)):
            for j in range(i+1,len(pts)):
                if len(out)>500000:break
                p,q=pts[i],pts[j]
                dist=float(np.linalg.norm(np.array([p[1],p[2],p[3]])-np.array([q[1],q[2],q[3]])))
                out.append(dict(frame=int(frame),point_a=p[0],point_b=q[0],distance_3d_mm=dist))
    return pd.DataFrame(out,columns=['frame','point_a','point_b','distance_3d_mm'])


def summarize_3d(df):
    '''Per physical landmark, 3-D data coverage and contiguous-only travelled distance.'''
    output=[]
    for name,g in df.groupby('point_id',sort=False):
        g=g.sort_values('time_s');v=g[g.valid_3d].copy()
        distance=0.
                                                                
        if not v.empty:
            for x in range(1,len(g)):
                a,b=g.iloc[x-1],g.iloc[x]
                if bool(a.valid_3d) and bool(b.valid_3d) and np.isfinite(b.speed_3d_mm_s):
                    distance+=float(b.speed_3d_mm_s*(b.time_s-a.time_s))
        net=float(np.linalg.norm(v[['x_mm','y_mm','z_mm']].iloc[-1].to_numpy(float)-v[['x_mm','y_mm','z_mm']].iloc[0].to_numpy(float))) if len(v)>1 else np.nan
        output.append(dict(point_id=name,attempted=int(len(g)),valid_3d=int(len(v)),valid_ratio=len(v)/max(1,len(g)),
            first_valid_s=float(v.time_s.iloc[0]) if len(v) else np.nan,
            last_valid_s=float(v.time_s.iloc[-1]) if len(v) else np.nan,
            depth_range_mm=float(v.z_mm.max()-v.z_mm.min()) if len(v) else np.nan,
            net_3d_displacement_mm=net,contiguous_path_lower_bound_mm=distance,
            median_depth_sensitivity_mm_per_px=float(v.depth_sensitivity_mm_per_px.median()) if len(v) else np.nan,
            note='累计路径仅含相邻有效片段，缺帧可能低估真实路程；深度敏感度不是误差认证。'))
    return pd.DataFrame(output)


def plot_3d_result(df,title='标定三维运动（相机一坐标系）',highlight='body'):
    """Legible overview. RAW 3D dots remain visible; an optional temporal median is
    DISPLAY-ONLY, never used in data exports or speed calculations."""
    import matplotlib.pyplot as plt
    fig=plt.figure(figsize=(11,5.4))
    ax=fig.add_axes([.055,.15,.42,.74],projection='3d')
    bx=fig.add_axes([.60,.15,.35,.73])
    if 'valid_3d' in df:
        good=df[df.valid_3d].copy()
        groups={n:g.sort_values('time_s') for n,g in good.groupby('point_id',sort=False)}
        if groups:
            chosen=highlight if highlight in groups else next(iter(groups))
                                                                                        
            for name,g in groups.items():
                if name==chosen:continue
                ax.scatter(g.x_mm,g.y_mm,g.z_mm,s=6,alpha=.17,color='#7891A2',label=str(name),depthshade=False)
            focus=groups[chosen]
            ax.scatter(focus.x_mm,focus.y_mm,focus.z_mm,c=focus.time_s,cmap='viridis',
                       s=17,alpha=.9,depthshade=False,label=chosen)
            bx.scatter(focus.time_s,focus.z_mm,s=12,color='#4B91A4',alpha=.42,
                       label='三维重建深度（未额外平滑）',zorder=2)
            if len(focus)>=9:
                                                                                            
                med=focus.z_mm.rolling(9,center=True,min_periods=5).median()
                bx.plot(focus.time_s,med,color='#C56E45',lw=2.,
                        label='9-sample median · visual only')
            bx.legend(fontsize=8,loc='best',frameon=False)
            bx.set_title(f'Depth of {chosen} · show RAW dots',fontsize=11,weight='bold')
            if len(groups)>1:ax.legend(fontsize=8,loc='upper left',frameon=False)
            coords=good[['x_mm','y_mm','z_mm']].to_numpy(float)
            span=np.maximum(np.ptp(coords,axis=0),1.)
            ax.set_box_aspect(span/np.max(span),zoom=.85)
        else:
            bx.text(.5,.55,'No accepted stereo 3D landmarks',ha='center',va='center',transform=bx.transAxes)
        ax.set(xlabel='X (mm)',ylabel='Y（毫米，向下为正）',zlabel='Z（毫米，深度）')
        bx.set(xlabel='时间（秒）',ylabel='深度 Z（毫米）')
    else:
        good=df[df.valid_pose].copy()
        if not good.empty:
            ax.scatter(good.tx_mm,good.ty_mm,good.tz_mm,c=good.time_s,cmap='viridis',s=15)
            bx.scatter(good.time_s,good.tz_mm,s=13,color='#4B91A4',alpha=.75)
        else:bx.text(.5,.55,'No accepted rigid-body pose',ha='center',va='center',transform=bx.transAxes)
        ax.set(xlabel='Tx (mm)',ylabel='Ty (mm)',zlabel='Tz (mm)')
        bx.set(xlabel='时间（秒）',ylabel='刚体原点深度（毫米）')
        bx.set_title('刚体位姿估计｜有效帧',fontsize=11,weight='bold')
    ax.set_title(title,fontsize=11,weight='bold',pad=13)
    bx.grid(alpha=.18)
    fig.text(.5,.025,'Camera coordinates. Reprojection consistency is not certified 3D accuracy. Missing 3D is never filled.',
            ha='center',fontsize=8,color='#596B74')
    return fig
