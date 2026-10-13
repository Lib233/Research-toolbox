"""Biomedical 8/16-bit single-channel microscopy; segmentation uses display-normalized image only."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from .imaging import analyze_image

def load_image(path):
    with Image.open(path) as im:
        a=np.array(im)
    if a.ndim==3 and a.shape[-1] in (3,4):
                                                                                          
        a=cv2.cvtColor(a[:,:,:3],cv2.COLOR_RGB2GRAY)
        return a,'converted_RGB_to_gray_not_usable_as_channel_intensity'
    if a.ndim!=2:raise ValueError('仅支持单页单通道或RGB图；多通道显微图请先在Fiji拆分通道。')
    if a.dtype not in (np.uint8,np.uint16):raise ValueError('仅支持8位或16位整型单通道图像。')
    return a,'native_single_channel'

def analyze_native_image(path,um_per_pixel,mode='bright',threshold=None,roi=None):
    original,provenance=load_image(path)
                                                                                
    if original.dtype==np.uint16:
        lower=float(np.percentile(original,1));upper=float(np.percentile(original,99))
        if upper<=lower: raise ValueError('输入图像缺少有效灰度对比度。')
        visual=(np.clip((original.astype(float)-lower)/(upper-lower),0,1)*255).astype(np.uint8)
        threshold_basis={'display_conversion':'16bit_to_8bit_percentile_1_99','low_raw':lower,'high_raw':upper}
    else:
        visual=original;threshold_basis={'display_conversion':'native_8bit'}
    result,mask,overlay=analyze_image(visual,um_per_pixel,mode,threshold,roi)
    if roi:
        l,t,r,b=roi
        small_original=original[t:b,l:r]; small_mask=mask[t:b,l:r]>0
    else:
        small_original=original;small_mask=mask>0
    fg=small_original[small_mask].astype(float);bg=small_original[~small_mask].astype(float)
                                                                                              
    if provenance!='native_single_channel':
        fg=np.array([]);bg=np.array([])
    result.update({'raw_foreground_mean':float(fg.mean()) if fg.size else float('nan'),
                   'raw_background_mean':float(bg.mean()) if bg.size else float('nan'),
                   'raw_background_corrected_mean':float(fg.mean()-bg.mean()) if fg.size and bg.size else float('nan'),
                   'raw_corrected_integrated_intensity':float((fg.mean()-bg.mean())*len(fg)) if fg.size and bg.size else float('nan'),
                   'bit_depth':int(original.dtype.itemsize*8),'image_channel_provenance':provenance,
                   'segmentation_threshold_basis':threshold_basis,
                   'warning':'阈值及面积对光照、分割方法和ROI敏感；荧光强度需保证曝光/增益一致，扣背景值不等于绝对浓度。'})
    return result,mask,overlay
