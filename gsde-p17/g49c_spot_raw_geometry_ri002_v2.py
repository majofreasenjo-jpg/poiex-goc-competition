from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import threshold_otsu

# Reuse the exact G4.9C segmentation, geometry, uncertainty, and RI002 pipeline.
# Only the demonstrably defective surface-reference estimator is replaced.
import g49c_spot_raw_geometry_ri002 as core


def radiographic_surface_line(bg: np.ndarray) -> dict:
    """Fit the air/metal interface from the pre-laser radiographic intensity transition.

    The background image contains a bright air region over a dark Ti64 region.  We freeze a
    global Otsu threshold on the pre-laser median background, find the first bright->dark
    crossing in each column within a broad physically plausible top band, and robustly fit a line.
    No absorptance target, RI002 outcome, or Scan information is used.
    """
    sm = ndi.gaussian_filter(bg.astype(float), sigma=1.25)
    h, w = sm.shape
    y0 = int(round(0.03 * h))
    y1 = int(round(0.45 * h))
    threshold = float(threshold_otsu(sm))

    xs, ys = [], []
    for x in range(w):
        col = sm[:, x]
        idx = np.flatnonzero(col[y0:y1] < threshold)
        if idx.size:
            xs.append(float(x))
            ys.append(float(idx[0] + y0))
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    if xs.size < 0.8 * w:
        raise RuntimeError(f'Insufficient surface crossings: {xs.size}/{w}')

    keep = np.ones(xs.shape, dtype=bool)
    coeff = None
    residual = None
    for _ in range(5):
        coeff = np.polyfit(xs[keep], ys[keep], 1)
        residual = ys - (coeff[0] * xs + coeff[1])
        med = float(np.median(residual[keep]))
        mad = float(np.median(np.abs(residual[keep] - med)))
        scale = 1.4826 * mad if mad > 0 else 1.0
        new_keep = np.abs(residual - med) <= 3.5 * scale
        if np.array_equal(new_keep, keep):
            break
        keep = new_keep

    coeff = np.polyfit(xs[keep], ys[keep], 1)
    residual = ys - (coeff[0] * xs + coeff[1])
    result = {
        'method': 'PRELASER_MEDIAN_GLOBAL_OTSU_FIRST_BRIGHT_TO_DARK_CROSSING_ROBUST_LINE_V2',
        'otsu_threshold_raw_units': threshold,
        'slope_y_per_x': float(coeff[0]),
        'intercept_y_px': float(coeff[1]),
        'candidate_y_median_px': float(np.median(ys)),
        'crossing_column_fraction': float(xs.size / w),
        'inlier_fraction': float(np.mean(keep)),
        'median_abs_residual_px': float(np.median(np.abs(residual[keep]))),
        'max_abs_residual_inlier_px': float(np.max(np.abs(residual[keep]))),
        'search_band_y_px': [y0, y1],
        'uses_absorptance_outcomes': False,
        'uses_scan_holdout': False,
    }
    if result['median_abs_residual_px'] > 2.0:
        raise RuntimeError(f"Surface QA fail: median residual {result['median_abs_residual_px']:.3f} px")
    if result['crossing_column_fraction'] < 0.95:
        raise RuntimeError(f"Surface QA fail: crossing fraction {result['crossing_column_fraction']:.3f}")
    return result


def main() -> None:
    core.robust_surface_line = radiographic_surface_line
    core.main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])

    out = Path(sys.argv[4])
    summary_path = out / 'G49C_RAW_GEOMETRY_SUMMARY.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    summary['surface_estimator_revision'] = 'V2_RADIographic_OTSU_CROSSING'
    summary['surface_v1_rejected'] = True
    summary['surface_v1_rejection_reason'] = 'Median residual ~54.5 px and visually crossed metal interior.'
    summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')

    with (out / 'G49C_ADJUDICATION.txt').open('a', encoding='utf-8') as f:
        f.write('SURFACE_ESTIMATOR_V1=REJECTED_QA\n')
        f.write('SURFACE_ESTIMATOR_V2=PRELASER_RADIographic_OTSU_CROSSING\n')
        f.write('SURFACE_ESTIMATOR_V2_USES_ABSORPTANCE_OUTCOMES=FALSE\n')
        f.write('SURFACE_ESTIMATOR_V2_USES_SCAN=FALSE\n')


if __name__ == '__main__':
    main()
