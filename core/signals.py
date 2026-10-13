"""Time-series filtering, event peaks and spectral analysis, with explicit sampling QA."""
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter, butter, sosfiltfilt, find_peaks
from .common import safe_numeric

def analyze_signal(df,time_col='time_s',value_col='value',method='savgol',window=11,cutoff_hz=2.0,prominence=0.0):
    t=safe_numeric(df[time_col],time_col).to_numpy()
    y=safe_numeric(df[value_col],value_col).to_numpy()
    if len(t)<7: raise ValueError('时间序列需要至少 7 个采样点。')
    dt=np.diff(t)
    if np.any(dt<=0): raise ValueError('时间戳必须严格递增，不可重复或倒序。')
    fs=1.0/float(np.median(dt))
    jitter=float(np.max(np.abs(dt-np.median(dt)))/np.median(dt))
    notes=[]
    if jitter>.02: notes.append('采样间隔偏差超过2%；FFT不输出以避免无效频谱。')
    if method=='savgol':
        w=int(window)
        if w%2==0 or w<5 or w>len(y): raise ValueError('Savitzky-Golay窗口必须为奇数、至少5且不超过数据长度。')
        smooth=savgol_filter(y,w,polyorder=2)
    elif method=='lowpass':
        if not 0<cutoff_hz<fs/2: raise ValueError(f'截止频率必须介于0与奈奎斯特频率 {fs/2:.3g} Hz之间。')
        if len(y)<16: raise ValueError('低通滤波至少需要16个点以保证双向滤波条件。')
        smooth=sosfiltfilt(butter(3,cutoff_hz,fs=fs,output='sos'),y)
    elif method=='none': smooth=y.copy()
    else:raise ValueError('未知平滑方法')
    peaks,_=find_peaks(smooth,prominence=float(prominence))
    series=pd.DataFrame({'time_s':t,'raw_value':y,'filtered_value':smooth})
    events=pd.DataFrame({'index':peaks,'time_s':t[peaks],'peak_value':smooth[peaks]})
    spectrum=pd.DataFrame(columns=['frequency_Hz','amplitude'])
    if jitter<=.02:
        yf=np.fft.rfft(smooth-np.mean(smooth));freq=np.fft.rfftfreq(len(smooth),d=np.median(dt))
        amp=np.abs(yf)/len(smooth)
                                
        if len(smooth)%2==0:amp[1:-1]*=2
        else:amp[1:]*=2
        if len(amp)>0:amp[0]=0
        spectrum=pd.DataFrame({'frequency_Hz':freq,'amplitude':amp})
    meta={'sampling_frequency_hz':fs,'sampling_jitter_max_fraction':jitter,
          'peak_count':int(len(peaks)),'duration_s':float(t[-1]-t[0]),'filter':method,
          'notes':notes,'spectral_method':'one-sided FFT, approximate uniform sampling only'}
    return series,events,spectrum,meta
