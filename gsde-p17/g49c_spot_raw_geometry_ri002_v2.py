from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from skimage import measure, morphology
from skimage.filters import threshold_otsu

import g49c_spot_raw_geometry_ri002 as core

MAX_PHYSICAL_DEPTH_UM = 300.0
SURFACE_ATTACHMENT_TOLERANCE_PX = 5.0


def radiographic_surface_line(bg: np.ndarray) -> dict:
    sm = ndi.gaussian_filter(bg.astype(float), sigma=1.25)
    h, w = sm.shape
    y0 = int(round(0.03 * h)); y1 = int(round(0.45 * h))
    threshold = float(threshold_otsu(sm))
    xs, ys = [], []
    for x in range(w):
        idx = np.flatnonzero(sm[y0:y1, x] < threshold)
        if idx.size:
            xs.append(float(x)); ys.append(float(idx[0] + y0))
    xs = np.asarray(xs); ys = np.asarray(ys)
    if xs.size < 0.8 * w:
        raise RuntimeError(f'Insufficient surface crossings: {xs.size}/{w}')
    keep = np.ones(xs.shape, dtype=bool)
    for _ in range(5):
        c = np.polyfit(xs[keep], ys[keep], 1)
        resid = ys - (c[0] * xs + c[1])
        med = float(np.median(resid[keep])); mad = float(np.median(np.abs(resid[keep] - med)))
        scale = 1.4826 * mad if mad > 0 else 1.0
        new_keep = np.abs(resid - med) <= 3.5 * scale
        if np.array_equal(new_keep, keep): break
        keep = new_keep
    c = np.polyfit(xs[keep], ys[keep], 1); resid = ys - (c[0] * xs + c[1])
    r = {'method':'PRELASER_MEDIAN_GLOBAL_OTSU_FIRST_BRIGHT_TO_DARK_CROSSING_ROBUST_LINE_V2','otsu_threshold_raw_units':threshold,'slope_y_per_x':float(c[0]),'intercept_y_px':float(c[1]),'candidate_y_median_px':float(np.median(ys)),'crossing_column_fraction':float(xs.size/w),'inlier_fraction':float(np.mean(keep)),'median_abs_residual_px':float(np.median(np.abs(resid[keep]))),'max_abs_residual_inlier_px':float(np.max(np.abs(resid[keep]))),'search_band_y_px':[y0,y1],'uses_absorptance_outcomes':False,'uses_scan_holdout':False}
    if r['median_abs_residual_px'] > 2.0 or r['crossing_column_fraction'] < 0.95:
        raise RuntimeError(f'Surface QA fail: {r}')
    return r


def segment_surface_attached(stretched: np.ndarray, line: dict, threshold_mult: float, surface_shift_px: int) -> np.ndarray:
    threshold = threshold_mult * float(np.mean(stretched))
    binary = stretched > threshold
    h, w = binary.shape
    xx = np.arange(w, dtype=float); yy = np.arange(h, dtype=float)[:, None]
    slope = float(line['slope_y_per_x']); intercept = float(line['intercept_y_px']) + float(surface_shift_px)
    norm = math.sqrt(1.0 + slope*slope)
    depth_px = (yy - slope * xx[None,:] - intercept) / norm
    binary &= depth_px >= 0.0
    binary &= depth_px <= MAX_PHYSICAL_DEPTH_UM / core.PIXEL_UM
    binary = morphology.binary_dilation(binary, morphology.diamond(1))
    binary = ndi.binary_fill_holes(binary)
    binary = morphology.binary_erosion(binary, morphology.disk(1))
    binary = morphology.remove_small_objects(binary.astype(bool), min_size=core.MIN_OBJECT_AREA_PX)
    lab = measure.label(binary, connectivity=2)
    attached = []
    for p in measure.regionprops(lab):
        if p.area < core.MIN_OBJECT_AREA_PX: continue
        py = p.coords[:,0].astype(float); px = p.coords[:,1].astype(float)
        d = (py - slope*px - intercept)/norm
        gap = float(np.nanmin(d))
        if gap <= SURFACE_ATTACHMENT_TOLERANCE_PX:
            attached.append((p, gap))
    if not attached:
        return np.zeros_like(binary, dtype=bool)
    chosen = min(attached, key=lambda z:(z[1], -z[0].area))[0]
    return lab == chosen.label


def main() -> None:
    core.robust_surface_line = radiographic_surface_line
    core.segment_reference = segment_surface_attached
    core.main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    out = Path(sys.argv[4])
    sp = out/'G49C_RAW_GEOMETRY_SUMMARY.json'; summary=json.loads(sp.read_text())
    summary.update({'surface_estimator_revision':'V2_RADIOGRAPHIC_OTSU_CROSSING','surface_v1_rejected':True,'surface_v1_rejection_reason':'Median residual ~54.5 px and visually crossed metal interior.','segmentation_revision':'V3_SURFACE_ATTACHED_PHYSICAL_SUPPORT','segmentation_v2_rejected':True,'segmentation_v2_rejection_reason':'43/43 pre-laser nominal false objects; disconnected bulk-metal regions were admitted.','surface_attachment_tolerance_px':SURFACE_ATTACHMENT_TOLERANCE_PX,'max_physical_depth_um':MAX_PHYSICAL_DEPTH_UM})
    sp.write_text(json.dumps(summary,indent=2),encoding='utf-8')
    with (out/'G49C_ADJUDICATION.txt').open('a',encoding='utf-8') as f:
        f.write('SURFACE_ESTIMATOR_V1=REJECTED_QA\nSURFACE_ESTIMATOR_V2=PRELASER_RADIographic_OTSU_CROSSING\nSURFACE_ESTIMATOR_V2_USES_ABSORPTANCE_OUTCOMES=FALSE\nSURFACE_ESTIMATOR_V2_USES_SCAN=FALSE\n')
        f.write('SEGMENTATION_V2=REJECTED_PRELASER_FALSE_OBJECT_43_OF_43\nSEGMENTATION_V3=SURFACE_ATTACHED_PHYSICAL_SUPPORT_GATE\nSEGMENTATION_V3_USES_FUTURE_ABSORPTANCE=FALSE\nSEGMENTATION_V3_USES_SCAN=FALSE\n')

if __name__ == '__main__': main()
