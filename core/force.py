"""Force-displacement analyses for adhesion/peel/shear tests."""
import numpy as np
import pandas as pd
from scipy.integrate import trapezoid

def analyze_force(df: pd.DataFrame, contact_area_mm2: float | None = None) -> pd.DataFrame:
    """Input cols: condition,sample_id,time_s,displacement_mm,force_N.

    Positive *tensile/separation* force assumed. First 5% points define baseline.
    Monotonic displacement required to compute work; negative displacements / cycles unsupported.
    sample_id should represent independent specimens, not successive video frames.
    """
    required = ['condition','sample_id','time_s','displacement_mm','force_N']
    missing = [x for x in required if x not in df]
    if missing:
        raise ValueError(f'Missing columns: {missing}')
    if contact_area_mm2 is not None and (not np.isfinite(contact_area_mm2) or contact_area_mm2 <= 0):
        raise ValueError('contact_area_mm2 must be positive.')
    raw = df.copy()
    for name in ('time_s','displacement_mm','force_N'):
        raw[name] = pd.to_numeric(raw[name], errors='raise')
    if raw[required].isna().any().any() or not np.isfinite(raw[['time_s','displacement_mm','force_N']].to_numpy()).all():
        raise ValueError('Missing/non-finite values found in required fields.')
    rows = []
    for (condition, sid), sub in raw.groupby(['condition','sample_id'], sort=True):
        sub = sub.sort_values('time_s')
        if len(sub) < 3 or np.any(np.diff(sub.time_s) <= 0):
            raise ValueError(f'{condition}/{sid}: need >=3 strictly increasing time points.')
        displ = sub.displacement_mm.to_numpy(dtype=float)
        if np.any(np.diff(displ) < -1e-9):
            raise ValueError(f'{condition}/{sid}: displacement must increase monotonically; split load/unload cycles.')
        f = sub.force_N.to_numpy(dtype=float)
        n0 = max(1, int(np.ceil(len(f)*0.05)))
        baseline = float(np.median(f[:n0]))
        positive = np.maximum(f-baseline, 0.)
        peak_idx = int(np.argmax(positive))
        work_mj = float(trapezoid(positive, displ))                
        row = {'condition':condition, 'sample_id':sid, 'n_points':len(sub),
               'baseline_N':baseline, 'peak_force_N':float(positive[peak_idx]),
               'displacement_at_peak_mm':float(displ[peak_idx]),
               'separation_work_mJ':work_mj}
        if contact_area_mm2 is not None:
            row['peak_nominal_stress_kPa'] = 1000. * row['peak_force_N']/contact_area_mm2
            row['work_per_nominal_area_J_m2'] = 1000. * work_mj/contact_area_mm2
        rows.append(row)
    return pd.DataFrame(rows)
