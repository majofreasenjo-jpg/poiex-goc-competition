from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

XRAY_FRAME_RATE_HZ = 50_000.0
XRAY_FRAME_PERIOD_S = 1.0 / XRAY_FRAME_RATE_HZ
XRAY_EXPOSURE_S = 2.5e-6
PRIMARY_HORIZONS_S = (20e-6, 40e-6, 100e-6)
G48_VERIFIED_IMAGE_FRAMES = set(range(80, 228))
G48_RECEIPT = {
    'run_id': 33707424594,
    'artifact_id': 9875719207,
    'artifact_digest': 'sha256:be22c40db70940988b3831fa5c2506f6875dd74baafbce39fd7c1196d44555d4',
    'processed_image_count': 148,
    'processed_frame_set': '080..227 inclusive',
}


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


def main(source_dir: str, out_dir: str) -> None:
    src = Path(source_dir)
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
        image_present = n in G48_VERIFIED_IMAGE_FRAMES

        status = 'PASS'
        if not contiguous or not rising_at_start:
            status = 'MAPPING_FAIL'
            mapping_failures.append(f'frame_{n}:contiguous={contiguous}:rising={rising_at_start}')
        elif not image_present:
            status = 'NO_IMAGE'

        r = {
            'frame': n,
            'image_present_by_g48_receipt': image_present,
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
    dev = frame_map[frame_map['image_present_by_g48_receipt']].copy()
    dev.to_csv(out / 'SPOT_DEVELOPMENT_FRAME_MAP_080_227.csv', index=False)

    dev_period = pd.to_numeric(dev['interframe_period_us'], errors='coerce').dropna().to_numpy(dtype=float)
    period_max_abs_error_us = float(np.max(np.abs(dev_period - 20.0))) if dev_period.size else None
    dev_pass = bool((dev['observation_status'] == 'PASS').all())

    target_availability = {}
    for h in (20, 40, 100):
        col = f'target_available_{h}us'
        target_availability[f'{h}us_available_count'] = int(dev[col].sum())
        target_availability[f'{h}us_unavailable_count'] = int((~dev[col]).sum())

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
        'processed_image_set_source': 'Reused immutable G4.8 receipt; not redownloaded in G4.9A',
        'g48_receipt': G48_RECEIPT,
        'development_frame_count': int(len(dev)),
        'development_frames_all_pass_mapping': dev_pass,
        'development_interframe_max_abs_error_us_vs_20us': period_max_abs_error_us,
        'mapping_failure_count_all_csv_frames': len(mapping_failures),
        'mapping_failures_all_csv_frames': mapping_failures,
        'primary_sync_rule': 'Use first CSV row where FrameNumber == n; this matches the official NIST Data Synchronization Example notebook.',
        'primary_timestamp_semantics': 'FrameTrigger leading edge / exposure start.',
        'xray_measurement_support': 'Each X-ray frame integrates over a 2.5 us exposure; primary timestamp is exposure start, with midpoint (+1.25 us) reserved as preregistered timing sensitivity.',
        'target_availability_in_observed_domain': target_availability,
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
            'PASS': 'unique contiguous CSV frame block + FrameTrigger rising edge at block start + G4.8 verified matching X-ray image',
            'NO_IMAGE': 'valid CSV frame block but outside the G4.8 verified released processed-image set; unusable for image-derived RI002',
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
        'G4_9A_SPOT_FRAME_TIME_MAPPING=CLOSED_MATERIAL' if dev_pass else 'G4_9A_SPOT_FRAME_TIME_MAPPING=HOLD',
        'SPOT_PROCESSED_IMAGE_SET_080_227_EXACT=TRUE_G48_RECEIPT_REUSED',
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

    landmark_frames = [80, 81, 90, 100, 120, 154, 191, 227]
    dev[dev['frame'].isin(landmark_frames)].to_csv(out / 'SPOT_SYNC_LANDMARKS.csv', index=False)

    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
