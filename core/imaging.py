"""Threshold-based contact-area and fluorescence image analyses."""
import cv2
import numpy as np

def analyze_image(image: np.ndarray, um_per_pixel: float, mode='bright',
                  threshold: int | None = None, roi=None) -> tuple[dict, np.ndarray, np.ndarray]:
    """image is uint8 grayscale or BGR/RGB (RGB/BGR both converted to gray; color science not supported).
    For fluorescence, input should be *single channel* 8-bit frame at matching acquisition settings.
    Returns metrics, binary mask, BGR overlay. Results are 2D and threshold-sensitive.
    """
    if not np.isfinite(um_per_pixel) or um_per_pixel <= 0:
        raise ValueError('um_per_pixel must be > 0.')
    if mode not in ('bright','dark'):
        raise ValueError('mode must be bright or dark.')
    if image.dtype != np.uint8:
        raise ValueError('Please supply 8-bit uint8 image (for 16-bit, normalize *consistently* before analysis).')
    if image.ndim == 3 and image.shape[2] in (3, 4):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        base = image[:, :, :3].copy()
    elif image.ndim == 2:
        gray = image
        base = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    else:
        raise ValueError('Expected grayscale or 3-channel image.')
    h,w = gray.shape
    l,t,r,b = roi if roi is not None else (0,0,w,h)
    if not (0<=l<r<=w and 0<=t<b<=h):
        raise ValueError(f'ROI must fit {w}x{h} image.')
    crop = gray[t:b,l:r]
    polarity = cv2.THRESH_BINARY if mode=='bright' else cv2.THRESH_BINARY_INV
    if threshold is None:
        th, smallmask = cv2.threshold(crop, 0, 255, polarity | cv2.THRESH_OTSU)
    else:
        if not 0 <= threshold <= 255: raise ValueError('Threshold must be 0...255.')
        th, smallmask = cv2.threshold(crop, threshold, 255, polarity)
    mask = np.zeros_like(gray)
    mask[t:b,l:r] = smallmask
    fg = crop[smallmask>0]; bg = crop[smallmask==0]
    pix = int(np.count_nonzero(smallmask)); num = smallmask.size
    overlay = base.copy()
    green = np.zeros_like(base); green[:,:,1] = 255
    sel = mask>0
    overlay[sel] = cv2.addWeighted(base[sel], 0.55, green[sel], 0.45, 0)
    cv2.rectangle(overlay, (l,t), (r-1,b-1), (0,0,255), 1)
    stats = {'threshold':float(th), 'roi_pixels':int(num), 'foreground_pixels':pix,
             'area_mm2':float(pix*(um_per_pixel/1000)**2),
             'area_um2':float(pix*um_per_pixel**2),
             'area_fraction':float(pix/num),
             'foreground_mean_gray':float(fg.mean()) if len(fg) else np.nan,
             'background_mean_gray':float(bg.mean()) if len(bg) else np.nan,
             'background_corrected_mean_au':float(fg.mean()-bg.mean()) if len(fg) and len(bg) else np.nan,
             'corrected_integrated_signal_au_px':float((fg.mean()-bg.mean())*pix) if len(fg) and len(bg) else np.nan}
    return stats, mask, overlay
