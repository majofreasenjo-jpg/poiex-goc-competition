from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

XRAY_FRAME_RATE_HZ = 50_000.0
XRAY_FRAME_PERIOD_S = 1.0 / XRAY_FRAME_RATE_HZ
XRAY_EXPOSURE_S = 2.5e-6
PRIMARY_HORIZONS_S = (20e-6, 40e-6, 100e-6)


def rising_edges(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    finite = x[np.isfinite(x)]
    if finite.size == 0:
        return np.array([], dtype=int)
    threshold = (float(np.nanmin(finite)) + float(np.nanmax(finite))) / 2.0
    hi = x >= threshold
    return np.flatnonzero(hi[1:] & ~hi[:-1]) + 1


def interp_at(t: np.ndarray, y: np.ndarray, q: float) -> float | None:
    finite = np.isfinite(t) & np.isfinite(y)
    if finite.sum() < 2:
        return None
    tf = t[finite]
    yf = y[finite]
    if q < tf[0] or q > tf[-1]:
        return None
    return float(np.interp(q, tf, yf))


def extract_frame_number(name: str) -> int | None:
    m = re.search(r'(\d{3})(?=\.tif$)', name, re.IGNORECASE)
    return int(m.group(1)) if m else None


def main(source_dir: str, image_dir: str, out_dir: str) -> None:
    src = Path(source_dir)
    imgs = Path(image_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    csv_path = src / 'Spot on Bare Metal_Calibrated Absorption Data.csv'
    readme_path = src / '2525_README_v200.txt'
    sync_nb_path = src / 'Data Synchronization Example.ipynb'

    df = pd.read_csv(csv_path)
    t = pd.to_numeric(df['Time'], errors='coerce').to_numpy(dtype=float)
    frame_no_raw = pd.to_numeric(df['FrameNumber'], errors='coerce').to_numpy(dtype=float)
    frame_trigger = pd.to_numeric(df['FrameTrigger'], errors='coerce').to_numpy(dtype=float)
    camera_trigger = pd.to_numeric(df['CameraTrigger'], errors='coerce').to_numpy(dtype=float)
    rel_abs = pd.to_numeric(df['RelativeAbsorption'], errors='coerce').to_numpy(dtype=float)
    abs_abs = pd.to_numeric(df['AbsoluteAbsorption'], errors='coerce').to_numpy(dtype=float)
    abs_unc = pd.to_numeric(df['AbsAbsorptionUncertainty'], errors='coerce').to_numpy(dtype=float)
    input_laser = pd.to_numeric(df['InputLaser'], errors='coerce').to_numpy(dtype=float)

    finite_t = t[np.isfinite(t)]
    dt = np.diff(finite_t)
    median_dt = float(np.nanmedian(dt))
    expected_samples_per_frame = XRAY_FRAME_PERIOD_S / median_dt

    image_files = sorted(p for p in imgs.rglob('*.tif') if p.is_file())
    image_by_frame: dict[int, str] = {}
    duplicate_image_frames: list[int] = []
    unparsed_images: list[str] = []
    for p in image_files:
        n = extract_frame_number(p.name)
        if n is None:
            unparsed_images.append(p.name)
            continue
        if n in image_by_frame:
            duplicate_image_frames.append(n)
        image_by_frame[n] = p.name

    frame_edges = set(map(int, rising_edges(frame_trigger)))
    max_frame = int(np.nanmax(frame_no_raw))

    rows = []
    mapping_failures = []
    for n in range(1, max_frame + 1):
        idx = np.flatnonzero(frame_no_raw == n)
        if idx.size == 0:
            mapping_failures.append(f'frame_{n}:no_csv_block')
            continue
        start = int(idx[0])
        end = int(idx[-1])
        contiguous = bool(np.array_equal(idx, np.arange(start, end + 1)))
        start_t = float(t[start])
        end_t = float(t[end])
        next_start_t = None
        if n < max_frame:
            idx_next = np.flatnonzero(frame_no_raw == (n + 1))
            if idx_next.size:
                next_start_t = float(t[int(idx_next[0])])
        period_s = (next_start_t - start_t) if next_start_t is not None else None
        rising_at_start = start in frame_edges
        image_present = n in image_by_frame

        status = 'PASS'
        if not contiguous or not rising_at_start:
            status = 'MAPPING_FAIL'
            mapping_failures.append(f'frame_{n}:contiguous={contiguous}:rising={rising_at_start}')
        elif not image_present:
            status = 'NO_IMAGE'

        r = {
            'frame': n,
            'image_present': image_present,
            'image_file': image_by_frame.get(n, ''),
            'observation_status': status,
            'csv_start_row_zero_based': start,
            'csv_end_row_zero_based': end,
            'samples_in_frame_block': int(idx.size),
            'frame_block_contiguous': contiguous,
            'frame_trigger_rising_at_start': rising_at_start,
            'start_time_s': start_t,
            'start_time_us': start_t * 1e6,
            'exposure_mid_time_s': start_t + XRAY_EXPOSURE_S / 2.0,
            'exposure_end_time_s': start_t + XRAY_EXPOSURE_S,
            'csv_block_last_time_s': end_t,
            'next_frame_start_time_s': next_start_t,
            'interframe_period_us': (period_s * 1e6 if period_s is not None else None),
            'relative_absorption_at_frame_start_pct': float(rel_abs[start]) if np.isfinite(rel_abs[start]) else None,
            'absolute_absorption_at_frame_start_W': float(abs_abs[start]) if np.isfinite(abs_abs[start]) else None,
            'absolute_absorption_uncertainty_at_frame_start_W': float(abs_unc[start]) if np.isfinite(abs_unc[start]) else None,
            'input_laser_at_frame_start_W': float(input_laser[start]) if np.isfinite(input_laser[start]) else None,
            'camera_trigger_at_frame_start': float(camera_trigger[start]) if np.isfinite(camera_trigger[start]) else None,
            'frame_trigger_at_frame_start': float(frame_trigger[start]) if np.isfinite(frame_trigger[start]) else None,
        }
        for h in PRIMARY_HORIZONS_S:
            key = int(round(h * 1e6))
            future = interp_at(t, rel_abs, start_t + h)
            r[f'rel_abs_future_{key}us_pct'] = future
            r[f'delta_rel_abs_{key}us_pctpt'] = (future - r['relative_absorption_at_frame_start_pct']) if (future is not None and r['relative_absorption_at_frame_start_pct'] is not None) else None
            r[f'target_available_{key}us'] = future is not None
        rows.append(r)

    frame_map = pd.DataFrame(rows)
    frame_map.to_csv(out / 'SPOT_FRAME_TIME_MAP_1_227.csv', index=False)
    dev = frame_map[frame_map['image_present']].copy()
    dev.to_csv(out / 'SPOT_DEVELOPMENT_FRAME_MAP_080_227.csv', index=False)

    expected_image_frames = set(range(80, 228))
    actual_image_frames = set(image_by_frame)
    image_exact_080_227 = actual_image_frames == expected_image_frames

    dev_period = pd.to_numeric(dev['interframe_period_us'], errors='coerce').dropna().to_numpy(dtype=float)
    period_max_abs_error_us = float(np.max(np.abs(dev_period - 20.0))) if dev_period.size else None
    dev_pass = bool((dev['observation_status'] == 'PASS').all())

    summary = {
        'dataset': 'NIST A-AMB2022-01 / mds2-2525 / Spot on Bare Metal Ti-6Al-4V',
        'csv_rows': int(len(df)),
        'csv_time_start_s': float(np.nanmin(t)),
        'csv_time_end_s': float(np.nanmax(t)),
        'csv_median_dt_s': median_dt,
        'csv_sample_rate_hz': 1.0 / median_dt,
        'nist_xray_frame_rate_hz': XRAY_FRAME_RATE_HZ,
        'nist_xray_frame_period_s': XRAY_FRAME_PERIOD_S,
        'nist_xray_exposure_s': XRAY_EXPOSURE_S,
        'expected_csv_samples_per_xray_period': expected_samples_per_frame,
        'frame_number_min': int(np.nanmin(frame_no_raw)),
        'frame_number_max': max_frame,
        'frame_trigger_rising_edges': len(frame_edges),
        'processed_image_count': len(image_files),
        'processed_image_frame_min': min(actual_image_frames) if actual_image_frames else None,
        'processed_image_frame_max': max(actual_image_frames) if actual_image_frames else None,
        'processed_image_exact_set_080_227': image_exact_080_227,
        'missing_processed_frames': sorted(expected_image_frames - actual_image_frames),
        'unexpected_processed_frames': sorted(actual_image_frames - expected_image_frames),
        'duplicate_image_frames': sorted(set(duplicate_image_frames)),
        'unparsed_image_count': len(unparsed_images),
        'mapping_failure_count': len(mapping_failures),
        'mapping_failures': mapping_failures,
        'development_frame_count': int(len(dev)),
        'development_frames_all_pass_mapping': dev_pass,
        'development_interframe_max_abs_error_us_vs_20us': period_max_abs_error_us,
        'primary_sync_rule': 'Use first CSV row where FrameNumber == n; this matches the official NIST Data Synchronization Example notebook.',
        'primary_timestamp_semantics': 'FrameTrigger leading edge / exposure start.',
        'xray_measurement_support': 'Each X-ray frame integrates over a 2.5 us exposure; primary timestamp is exposure start, with midpoint (+1.25 us) reserved as preregistered timing sensitivity.',
        'scan_holdout_downloaded': False,
        'scan_holdout_inspected': False,
    }
    (out / 'G49A_SPOT_SYNC_SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    gate = {
        'gate_name': 'P17_SPOT_OBSERVATION_ADMISSIBILITY_V0_1',
        'scope': 'Spot development only; Scan sealed.',
        'primary_timestamp': 'frame exposure start from first row FrameNumber==n',
        'timing_sensitivity': 'exposure midpoint = start + 1.25 us',
        'frame_period_primary': '20 us engineering frame step, not causal age',
        'statuses': {
            'PASS': 'unique contiguous CSV frame block + FrameTrigger rising edge at block start + matching X-ray image',
            'NO_IMAGE': 'valid CSV frame block but no released processed image; unusable for image-derived RI002',
            'MAPPING_FAIL': 'frame block non-contiguous or trigger alignment failed',
            'TARGET_HORIZON_UNAVAILABLE': 'future absorptance lies outside CSV support for requested horizon',
            'SEGMENTATION_HOLD': 'reserved for later image-segmentation ambiguity/uncertainty',
            'NONIDENTIFIABLE': 'reserved for representation-equivalent masks/ontologies not distinguishable by current observations',
        },
        'preregistered_horizons': ['20 us', '40 us', '100 us'],
        'causal_clock_claim': False,
        'scan_access_before_freeze': False,
        'point_estimate_if_timing_or_segmentation_can_reverse_conclusion': False,
    }
    (out / 'P17_OBSERVATION_GATE_V0_1.json').write_text(json.dumps(gate, indent=2), encoding='utf-8')

    # Minimal source-grounded excerpts for auditing without copying large source text.
    readme_lines = readme_path.read_text(encoding='utf-8', errors='replace').splitlines()
    keys = ('frame', 'synchron', 'xray', '50,000', '50000', '2.5', 'processed', 'raw image')
    selected = []
    for i, line in enumerate(readme_lines, start=1):
        if any(k.lower() in line.lower() for k in keys):
            selected.append(f'{i}: {line}')
    (out / 'README_SYNC_RELEVANT_LINES.txt').write_text('\n'.join(selected[:80]) + '\n', encoding='utf-8')

    nb = json.loads(sync_nb_path.read_text(encoding='utf-8'))
    code = '\n'.join(''.join(c.get('source', [])) for c in nb.get('cells', []) if c.get('cell_type') == 'code')
    official_logic = {
        'uses_FrameNumber': 'FrameNumber' in code,
        'uses_first_matching_row': "row.index[0]" in code,
        'image_lookup_zero_padded_frame': 'zfill(3)' in code,
        'plots_absorptance_at_frame_start_index': 'frameIndex[Frame-1]' in code,
    }
    (out / 'OFFICIAL_SYNC_NOTEBOOK_LOGIC.json').write_text(json.dumps(official_logic, indent=2), encoding='utf-8')

    status_lines = [
        'G4_9A_SPOT_FRAME_TIME_MAPPING=CLOSED_MATERIAL' if dev_pass and image_exact_080_227 else 'G4_9A_SPOT_FRAME_TIME_MAPPING=HOLD',
        f'SPOT_PROCESSED_IMAGE_SET_080_227_EXACT={str(image_exact_080_227).upper()}',
        f'SPOT_DEVELOPMENT_MAPPING_080_227_ALL_PASS={str(dev_pass).upper()}',
        'PRIMARY_SYNC_CONVENTION=NIST_FIRST_ROW_FRAMENUMBER_EQ_N',
        'PRIMARY_TIMESTAMP=XRAY_EXPOSURE_START',
        'TIMING_SENSITIVITY=EXPOSURE_MIDPOINT_PLUS_1_25US',
        'FRAME_HORIZON_20_40_100US=ENGINEERING_ONLY_NOT_CAUSAL_CLOCK',
        'SCAN_HOLDOUT_DOWNLOADED=FALSE',
        'SCAN_HOLDOUT_INSPECTED=FALSE',
        'EMPIRICAL_BENCHMARK_EXECUTED=FALSE',
    ]
    (out / 'G49A_ADJUDICATION.txt').write_text('\n'.join(status_lines) + '\n', encoding='utf-8')

    # Human-readable landmarks for immediate scientific review.
    landmark_frames = [80, 81, 90, 100, 120, 154, 191, 227]
    lm = dev[dev['frame'].isin(landmark_frames)].copy()
    lm.to_csv(out / 'SPOT_SYNC_LANDMARKS.csv', index=False)

    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
