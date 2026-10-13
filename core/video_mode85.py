""": explicit opt-in 3D; 2D is entirely independent of stereo/PnP inputs.

The UI always passes enable_3d yes/no. Old programmatic clients which supplied
an explicit non-none reconstruction_3d but no enable_3d remain supported.
"""

def effective_3d_mode(config):
    enabled=config.get('enable_3d', None)
    if enabled is not None:
        if str(enabled).strip().lower() not in ('yes','true','1','on'):
            return 'none'
    mode=str(config.get('reconstruction_3d','none') or 'none').strip()
    if mode not in ('none','stereo','rigid_pnp'):
        raise ValueError('三维模式无效。请选“仅二维”“双目”或“刚体PnP”。')
    if enabled is not None and mode=='none':
        raise ValueError('已勾选启用三维，但尚未选择双目或刚体PnP方法。取消勾选即可运行二维。')
    return mode

def normalized_video_config(config):
    d=dict(config)
    mode=effective_3d_mode(d)
    d['reconstruction_3d']=mode
    d['enable_3d']='yes' if mode!='none' else 'no'
    if mode=='none':
                                                                              
        for key in ('stereo_calibration_file','stereo_right_track_file','rigid_geometry_file'):
            d[key]=''
    return d
