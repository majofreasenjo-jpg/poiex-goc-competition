from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import exposure, measure, morphology

PIXEL_UM = 1.923
PIXEL_AREA_UM2 = PIXEL_UM ** 2
PRIMARY_THRESHOLD_MULTIPLIER = 1.15
THRESHOLD_MULTIPLIERS = (1.10, 1.15, 1.20)
SURFACE_SHIFTS_PX = (-1, 0, 1)
MIN_OBJECT_AREA_PX = 100
BACKGROUND_FRAMES = tuple(range(1, 80))
DEVELOPMENT_FRAMES = tuple(range(80, 228))
DEPTH_BIN_EDGES_UM = (0, 25, 50, 75, 100, 125, 150, 200, 300)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def frame_from_name(name: str) -> int | None:
    m = re.search(r'(\d{3})(?=\.(?:tif|tiff)$)', name, flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def load_gray(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im, dtype=np.float32)


def robust_surface_line(bg: np.ndarray) -> dict:
    sm = ndi.gaussian_filter(bg.astype(float), sigma=1.25)
    gy = np.abs(np.gradient(sm, axis=0))
    h, w = bg.shape
    y0 = int(round(0.20 * h))
    y1 = int(round(0.62 * h))
    xs = np.arange(w, dtype=float)
    ys = np.argmax(gy[y0:y1, :], axis=0).astype(float) + y0
    # Robust two-pass line fit on per-column maximum vertical gradients.
    c = np.polyfit(xs, ys, 1)
    pred = c[0] * xs + c[1]
    resid = ys - pred
    med = float(np.median(resid))
    mad = float(np.median(np.abs(resid - med)))
    scale = 1.4826 * mad if mad > 0 else 1.0
    keep = np.abs(resid - med) <= 3.5 * scale
    c2 = np.polyfit(xs[keep], ys[keep], 1)
    pred2 = c2[0] * xs + c2[1]
    resid2 = ys - pred2
    return {
        'slope_y_per_x': float(c2[0]),
        'intercept_y_px': float(c2[1]),
        'candidate_y_median_px': float(np.median(ys)),
        'inlier_fraction': float(np.mean(keep)),
        'median_abs_residual_px': float(np.median(np.abs(resid2[keep]))),
        'max_abs_residual_inlier_px': float(np.max(np.abs(resid2[keep]))),
        'search_band_y_px': [y0, y1],
    }


def surface_y(line: dict, x: np.ndarray | float) -> np.ndarray | float:
    return line['slope_y_per_x'] * x + line['intercept_y_px']


def normalize_ratio_image(img: np.ndarray, bg: np.ndarray) -> np.ndarray:
    denom = np.where(bg > 1e-6, bg, np.nan)
    ratio = img / denom
    finite = np.isfinite(ratio)
    if not finite.any():
        return np.zeros_like(img, dtype=float)
    lo, hi = np.nanpercentile(ratio[finite], [0.1, 99.9])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(np.nanmin(ratio[finite])), float(np.nanmax(ratio[finite]))
    clipped = np.clip(ratio, lo, hi)
    stretched = exposure.rescale_intensity(clipped, in_range=(lo, hi), out_range=(0.0, 255.0))
    return np.nan_to_num(stretched, nan=0.0, posinf=255.0, neginf=0.0)


def segment_reference(stretched: np.ndarray, line: dict, threshold_mult: float, surface_shift_px: int) -> np.ndarray:
    # Literature-grounded structure: background division -> contrast stretch -> threshold at a multiplier
    # of image mean -> mask above original surface -> morphology -> area rejection -> select top qualifying object.
    # Published 2020 procedure gives 115% and 100 px^2; exact dilation/erosion element sizes are not fully
    # specified in the available description, so GSDE freezes a symmetric 3-pixel cross + disk(1) cleanup.
    threshold = threshold_mult * float(np.mean(stretched))
    binary = stretched > threshold
    h, w = binary.shape
    xx = np.arange(w)
    sy = surface_y(line, xx) + surface_shift_px
    yy = np.arange(h)[:, None]
    binary &= yy >= sy[None, :]

    cross = morphology.diamond(1)
    binary = morphology.binary_dilation(binary, cross)
    binary = ndi.binary_fill_holes(binary)
    binary = morphology.binary_erosion(binary, morphology.disk(1))
    binary = morphology.remove_small_objects(binary.astype(bool), min_size=MIN_OBJECT_AREA_PX)

    lab = measure.label(binary, connectivity=2)
    props = measure.regionprops(lab)
    if not props:
        return np.zeros_like(binary, dtype=bool)
    areas = np.array([p.area for p in props], dtype=float)
    mean_area = float(np.mean(areas))
    qualified = [p for p in props if p.area >= MIN_OBJECT_AREA_PX and p.area >= 0.5 * mean_area]
    if not qualified:
        return np.zeros_like(binary, dtype=bool)
    chosen = min(qualified, key=lambda p: (p.bbox[0], -p.area))
    return lab == chosen.label


def mask_geometry(mask: np.ndarray, line: dict) -> dict:
    area_px = int(mask.sum())
    if area_px == 0:
        return {
            'mask_present': False,
            'area_px': 0,
            'area_um2': 0.0,
            'amplitude_sqrt_um2': 0.0,
        }
    yy, xx = np.nonzero(mask)
    a = float(line['slope_y_per_x'])
    b = float(line['intercept_y_px'])
    norm = math.sqrt(1.0 + a * a)
    normal_px = (yy - a * xx - b) / norm
    tangent_px = (xx + a * yy) / norm
    prop = measure.regionprops(mask.astype(np.uint8))[0]
    perimeter_px = float(measure.perimeter(mask, neighborhood=8))
    area_um2 = area_px * PIXEL_AREA_UM2
    perimeter_um = perimeter_px * PIXEL_UM
    compactness = (4.0 * math.pi * area_um2 / (perimeter_um ** 2)) if perimeter_um > 0 else None
    depth_um = float(np.max(normal_px) * PIXEL_UM)
    width_um = float((np.max(tangent_px) - np.min(tangent_px) + 1.0) * PIXEL_UM)
    centroid_y, centroid_x = prop.centroid
    centroid_normal_um = float((centroid_y - a * centroid_x - b) / norm * PIXEL_UM)
    centroid_tangent_um = float((centroid_x + a * centroid_y) / norm * PIXEL_UM)
    hist, _ = np.histogram(np.clip(normal_px * PIXEL_UM, 0, None), bins=np.array(DEPTH_BIN_EDGES_UM, dtype=float))
    # last bin 200-300; material thickness is about 300 um, so values beyond are tracked separately.
    beyond_300 = int(np.sum(normal_px * PIXEL_UM >= 300.0))
    comp = hist.astype(float)
    if comp.sum() > 0:
        comp /= comp.sum()
    g = {
        'mask_present': True,
        'area_px': area_px,
        'area_um2': float(area_um2),
        'amplitude_sqrt_um2': float(math.sqrt(area_um2)),
        'equivalent_radius_um': float(math.sqrt(area_um2 / math.pi)),
        'max_normal_depth_um': depth_um,
        'tangent_width_um': width_um,
        'centroid_normal_um': centroid_normal_um,
        'centroid_tangent_um': centroid_tangent_um,
        'perimeter_um': perimeter_um,
        'compactness': compactness,
        'eccentricity': float(prop.eccentricity),
        'major_axis_um': float(prop.axis_major_length * PIXEL_UM),
        'minor_axis_um': float(prop.axis_minor_length * PIXEL_UM),
        'depth_to_width_ratio': float(depth_um / width_um) if width_um > 0 else None,
        'pixels_beyond_300um': beyond_300,
    }
    for i, v in enumerate(comp):
        g[f'depth_comp_bin_{i}'] = float(v)
    return g


def jaccard(a: np.ndarray, b: np.ndarray) -> float | None:
    u = np.logical_or(a, b).sum()
    if u == 0:
        return None
    return float(np.logical_and(a, b).sum() / u)


def projective_shape_speed(m1: np.ndarray, m2: np.ndarray, dt_s: float) -> float | None:
    n1 = int(m1.sum()); n2 = int(m2.sum())
    if n1 == 0 or n2 == 0 or dt_s <= 0:
        return None
    s1 = m1.astype(np.float32) / math.sqrt(n1)
    s2 = m2.astype(np.float32) / math.sqrt(n2)
    return float(np.linalg.norm(s2 - s1) / dt_s)


def save_overlay(img: np.ndarray, mask: np.ndarray, line: dict, path: Path) -> None:
    lo, hi = np.percentile(img, [0.5, 99.5])
    if hi <= lo:
        hi = lo + 1
    u8 = np.clip((img - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    rgb = Image.fromarray(u8, mode='L').convert('RGB')
    draw = ImageDraw.Draw(rgb)
    h, w = img.shape
    pts = [(x, float(surface_y(line, x))) for x in range(w)]
    draw.line(pts, fill=(255, 255, 255), width=1)
    # Mark boundary only, preserving underlying morphology.
    boundary = mask ^ morphology.binary_erosion(mask, morphology.disk(1))
    yy, xx = np.nonzero(boundary)
    for x, y in zip(xx.tolist(), yy.tolist()):
        if 0 <= x < w and 0 <= y < h:
            rgb.putpixel((x, y), (255, 0, 0))
    rgb.save(path)


def main(raw_dir: str, sync_map_csv: str, effective_domain_csv: str, out_dir: str) -> None:
    raw_root = Path(raw_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'qa_overlays').mkdir(exist_ok=True)

    raw_files = sorted(p for p in raw_root.rglob('*') if p.suffix.lower() in {'.tif', '.tiff'})
    by_frame: dict[int, Path] = {}
    duplicates = []
    unparsed = []
    for p in raw_files:
        n = frame_from_name(p.name)
        if n is None:
            unparsed.append(p.name); continue
        if n in by_frame:
            duplicates.append(n)
        by_frame[n] = p

    actual = set(by_frame)
    expected = set(range(1, 228))
    coverage_exact = actual == expected and not duplicates
    if not coverage_exact:
        raise SystemExit(f'RAW COVERAGE FAIL missing={sorted(expected-actual)} unexpected={sorted(actual-expected)} duplicates={duplicates}')

    first = load_gray(by_frame[1])
    shape = first.shape
    stack = []
    for n in BACKGROUND_FRAMES:
        arr = load_gray(by_frame[n])
        if arr.shape != shape:
            raise SystemExit(f'Raw shape mismatch frame={n} {arr.shape} != {shape}')
        stack.append(arr)
    bg = np.median(np.stack(stack, axis=0), axis=0).astype(np.float32)
    Image.fromarray(np.clip((bg-np.percentile(bg,0.5))/(np.percentile(bg,99.5)-np.percentile(bg,0.5)+1e-9)*255,0,255).astype(np.uint8)).save(out/'SPOT_RAW_BACKGROUND_MEDIAN_001_079.png')

    line = robust_surface_line(bg)
    line['pixel_scale_um_per_px'] = PIXEL_UM
    line['background_frames'] = list(BACKGROUND_FRAMES)
    (out / 'SPOT_SURFACE_REFERENCE_V0_1.json').write_text(json.dumps(line, indent=2), encoding='utf-8')

    sync = pd.read_csv(sync_map_csv)
    eff = pd.read_csv(effective_domain_csv)
    sync_by_frame = sync.set_index('frame')
    eff_by_frame = eff.set_index('frame')

    variants = [(tm, ss) for tm in THRESHOLD_MULTIPLIERS for ss in SURFACE_SHIFTS_PX]
    masks_by_variant: dict[tuple[float,int], dict[int,np.ndarray]] = {v:{} for v in variants}
    geometry_rows = []
    qa_frames = {80, 82, 83, 90, 100, 117, 140, 154, 170, 181, 191, 227}

    for n in DEVELOPMENT_FRAMES:
        img = load_gray(by_frame[n])
        stretched = normalize_ratio_image(img, bg)
        nominal_mask = None
        variant_geoms = []
        for tm, ss in variants:
            mask = segment_reference(stretched, line, tm, ss)
            masks_by_variant[(tm,ss)][n] = mask
            g = mask_geometry(mask, line)
            g.update({'frame': n, 'threshold_multiplier': tm, 'surface_shift_px': ss})
            variant_geoms.append(g)
            if tm == PRIMARY_THRESHOLD_MULTIPLIER and ss == 0:
                nominal_mask = mask
        if nominal_mask is None:
            raise RuntimeError('Nominal mask missing')
        nominal = [g for g in variant_geoms if g['threshold_multiplier']==PRIMARY_THRESHOLD_MULTIPLIER and g['surface_shift_px']==0][0]
        others = [masks_by_variant[v][n] for v in variants]
        jac = [jaccard(nominal_mask, m) for m in others]
        jac_f = [x for x in jac if x is not None]
        areas = np.array([g.get('area_um2',0.0) for g in variant_geoms], dtype=float)
        depths = np.array([g.get('max_normal_depth_um',np.nan) for g in variant_geoms], dtype=float)
        row = dict(nominal)
        row['representation_variant_count'] = len(variants)
        row['representation_present_count'] = int(sum(bool(g.get('mask_present')) for g in variant_geoms))
        row['jaccard_median_vs_nominal'] = float(np.median(jac_f)) if jac_f else None
        row['jaccard_min_vs_nominal'] = float(np.min(jac_f)) if jac_f else None
        row['area_um2_min'] = float(np.nanmin(areas))
        row['area_um2_max'] = float(np.nanmax(areas))
        row['area_um2_cv'] = float(np.nanstd(areas)/np.nanmean(areas)) if np.nanmean(areas)>0 else None
        row['depth_um_min'] = float(np.nanmin(depths)) if np.isfinite(depths).any() else None
        row['depth_um_max'] = float(np.nanmax(depths)) if np.isfinite(depths).any() else None
        if n in sync_by_frame.index:
            for c in ['start_time_s','start_time_us','interframe_period_us','relative_absorption_at_frame_start_pct','absolute_absorption_at_frame_start_W','absolute_absorption_uncertainty_at_frame_start_W','input_laser_at_frame_start_W']:
                row[c] = sync_by_frame.loc[n,c]
        if n in eff_by_frame.index:
            for c in ['calibrated_start_admissible','effective_domain_H20','effective_domain_H40','effective_domain_H100']:
                if c in eff_by_frame.columns:
                    row[c] = eff_by_frame.loc[n,c]
        geometry_rows.append(row)
        if n in qa_frames:
            save_overlay(img, nominal_mask, line, out/'qa_overlays'/f'frame_{n:03d}_raw_nominal_overlay.png')

    geom = pd.DataFrame(geometry_rows).sort_values('frame')
    geom.to_csv(out / 'SPOT_RAW_GEOMETRY_NOMINAL_AND_UNCERTAINTY.csv', index=False)

    # Projective amplitude-shape kinematics for nominal and representation identified set.
    kin_rows = []
    frames = list(DEVELOPMENT_FRAMES)
    for i, n in enumerate(frames):
        r = {'frame': n}
        if i == len(frames)-1:
            r['next_frame'] = None
            r['dt_s'] = None
            r['V_shape_nominal_s_inv'] = None
            r['V_amp_nominal_um_per_s'] = None
            kin_rows.append(r)
            continue
        n2 = frames[i+1]
        t1 = float(sync_by_frame.loc[n,'start_time_s']); t2 = float(sync_by_frame.loc[n2,'start_time_s'])
        dt = t2-t1
        nominal1 = masks_by_variant[(PRIMARY_THRESHOLD_MULTIPLIER,0)][n]
        nominal2 = masks_by_variant[(PRIMARY_THRESHOLD_MULTIPLIER,0)][n2]
        g1 = mask_geometry(nominal1,line); g2=mask_geometry(nominal2,line)
        vs_nom = projective_shape_speed(nominal1, nominal2, dt)
        amp1 = float(g1.get('amplitude_sqrt_um2',0.0)); amp2=float(g2.get('amplitude_sqrt_um2',0.0))
        va_nom = abs(amp2-amp1)/dt if dt>0 else None
        vs_all=[]; va_all=[]
        for v in variants:
            m1=masks_by_variant[v][n]; m2=masks_by_variant[v][n2]
            vs=projective_shape_speed(m1,m2,dt)
            if vs is not None: vs_all.append(vs)
            gg1=mask_geometry(m1,line); gg2=mask_geometry(m2,line)
            aa1=float(gg1.get('amplitude_sqrt_um2',0.0)); aa2=float(gg2.get('amplitude_sqrt_um2',0.0))
            va_all.append(abs(aa2-aa1)/dt)
        r.update({
            'next_frame':n2,'dt_s':dt,
            'V_shape_nominal_s_inv':vs_nom,
            'V_shape_identified_min_s_inv':float(np.min(vs_all)) if vs_all else None,
            'V_shape_identified_max_s_inv':float(np.max(vs_all)) if vs_all else None,
            'V_shape_variant_support_count':len(vs_all),
            'V_amp_nominal_um_per_s':va_nom,
            'V_amp_identified_min_um_per_s':float(np.min(va_all)) if va_all else None,
            'V_amp_identified_max_um_per_s':float(np.max(va_all)) if va_all else None,
            'pair_effective_H20': bool(eff_by_frame.loc[n,'effective_domain_H20']) if n in eff_by_frame.index else False,
        })
        kin_rows.append(r)
    kin = pd.DataFrame(kin_rows)
    kin.to_csv(out/'RI002_PROJECTIVE_AMPLITUDE_SHAPE_KINEMATICS_SPOT.csv', index=False)

    # Compressed nominal masks: receiver-native source for later equal-information baselines/RI002.
    nominal_stack = np.stack([masks_by_variant[(PRIMARY_THRESHOLD_MULTIPLIER,0)][n] for n in DEVELOPMENT_FRAMES], axis=0)
    np.savez_compressed(out/'SPOT_NOMINAL_MASKS_080_227.npz', frames=np.array(DEVELOPMENT_FRAMES,dtype=np.int16), masks=nominal_stack.astype(np.uint8))

    pre_laser_frames = [n for n in DEVELOPMENT_FRAMES if float(sync_by_frame.loc[n,'input_laser_at_frame_start_W']) < 1.0]
    pre_rows = geom[geom.frame.isin(pre_laser_frames)]
    active_rows = geom[~geom.frame.isin(pre_laser_frames)]
    summary = {
        'raw_file_count': len(raw_files),
        'raw_frame_coverage_exact_001_227': coverage_exact,
        'raw_shape': list(shape),
        'raw_dtype_frame1': str(first.dtype),
        'background_frames': list(BACKGROUND_FRAMES),
        'development_frames': [80,227],
        'published_pixel_scale_um_per_px': PIXEL_UM,
        'surface_reference': line,
        'segmentation_reference': {
            'published_structure': 'background division; contrast stretching; threshold above 115% of image mean; mask above metal surface; morphology; reject regions <100 px^2; select qualifying object nearest top',
            'gsde_frozen_morphology': 'diamond(1) dilation; fill holes; disk(1) erosion',
            'nominal_threshold_multiplier': PRIMARY_THRESHOLD_MULTIPLIER,
            'representation_threshold_multipliers': list(THRESHOLD_MULTIPLIERS),
            'representation_surface_shifts_px': list(SURFACE_SHIFTS_PX),
            'representation_variant_count': len(variants),
            'claim': 'independent GSDE implementation inspired by published NIST procedure; not claimed byte/code identical to NIST implementation',
        },
        'nominal_mask_present_frames': int(geom.mask_present.fillna(False).sum()),
        'pre_laser_frame_count_in_080_227': len(pre_laser_frames),
        'pre_laser_nominal_false_object_count': int(pre_rows.mask_present.fillna(False).sum()),
        'active_nominal_mask_present_count': int(active_rows.mask_present.fillna(False).sum()),
        'median_jaccard_vs_nominal_when_defined': float(geom.jaccard_median_vs_nominal.dropna().median()) if geom.jaccard_median_vs_nominal.notna().any() else None,
        'min_jaccard_vs_nominal_when_defined': float(geom.jaccard_min_vs_nominal.dropna().min()) if geom.jaccard_min_vs_nominal.notna().any() else None,
        'H20_kinematic_pairs_with_shape_support': int(kin.loc[kin.pair_effective_H20.fillna(False),'V_shape_nominal_s_inv'].notna().sum()) if 'pair_effective_H20' in kin else 0,
        'scan_holdout_downloaded': False,
        'scan_holdout_inspected': False,
        'empirical_benchmark_executed': False,
    }
    (out/'G49C_RAW_GEOMETRY_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

    adjudication = [
        'G4_9C_SPOT_RAW_CUSTODY=PASS',
        f'SPOT_RAW_FRAME_COVERAGE_001_227_EXACT={str(coverage_exact).upper()}',
        'BACKGROUND_REFERENCE=RAW_FRAMES_001_079_MEDIAN',
        'SEGMENTATION_OUTPUT != PHYSICAL_GROUND_TRUTH',
        'NIST_PUBLISHED_METHOD != NIST_CODE_COPY',
        'REPRESENTATION_IDENTIFIED_SET=THRESHOLD_X_SURFACE_PERTURBATION_9_VARIANTS',
        'RI002_PROJECTIVE_KINEMATICS=IMPLEMENTED_SPOT_ONLY',
        'RI002_DISTINCT_CREDIT=NOT_YET_TESTED',
        'RI006_DISTINCT_CREDIT=HOLD',
        'SCAN_HOLDOUT_DOWNLOADED=FALSE',
        'SCAN_HOLDOUT_INSPECTED=FALSE',
        'EMPIRICAL_BENCHMARK_EXECUTED=FALSE',
    ]
    (out/'G49C_ADJUDICATION.txt').write_text('\n'.join(adjudication)+'\n',encoding='utf-8')

    provenance = {
        'external_method_reference': 'Simonds et al., Procedia CIRP 94 (2020), simultaneous X-ray/absorptance; published image-analysis description.',
        'later_scientific_reference': 'Simonds et al., Applied Materials Today 23 (2021) 101049.',
        'nist_dataset': 'A-AMB2022-01 / mds2-2525',
        'commercial_training_restriction': 'No external non-commercial segmentation dataset or weights used.',
        'source_code_origin': 'independent GSDE implementation authored for this replay.',
    }
    (out/'G49C_PROVENANCE.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')

    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
