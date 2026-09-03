from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def rising_edges(x: np.ndarray, threshold: float | None = None) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    finite = x[np.isfinite(x)]
    if finite.size == 0:
        return np.array([], dtype=int)
    if threshold is None:
        threshold = (np.nanmin(finite) + np.nanmax(finite)) / 2.0
    hi = x >= threshold
    return np.flatnonzero(hi[1:] & ~hi[:-1]) + 1


def main(source_dir: str, image_dir: str, out_dir: str) -> None:
    src = Path(source_dir)
    imgs = Path(image_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    absorption_path = src / 'Spot on Bare Metal_Calibrated Absorption Data.csv'
    readme_path = src / '2525_README_v200.txt'
    sync_path = src / 'Data Synchronization Example.ipynb'
    captioned_zip = src / 'Spot on Bare Metal_XrayImages_processed_captioned.zip'

    df = pd.read_csv(absorption_path)
    cols = list(df.columns)
    t = pd.to_numeric(df['Time'], errors='coerce').to_numpy(dtype=float)
    dt = np.diff(t[np.isfinite(t)])
    med_dt = float(np.nanmedian(dt)) if dt.size else None

    laser = pd.to_numeric(df['InputLaser'], errors='coerce').to_numpy(dtype=float)
    laser_threshold = 0.05 * float(np.nanmax(laser)) if np.isfinite(laser).any() else np.nan
    active = np.flatnonzero(laser >= laser_threshold) if np.isfinite(laser_threshold) else np.array([], dtype=int)

    frame_trig = pd.to_numeric(df['FrameTrigger'], errors='coerce').to_numpy(dtype=float)
    frame_edges = rising_edges(frame_trig)
    frame_numbers = pd.to_numeric(df['FrameNumber'], errors='coerce')
    populated_frames = frame_numbers.dropna().astype(int)

    summary = {
        'row_count': int(len(df)),
        'columns': cols,
        'time_start_s': float(np.nanmin(t)),
        'time_end_s': float(np.nanmax(t)),
        'median_time_step_s': med_dt,
        'estimated_sample_rate_hz': (1.0 / med_dt if med_dt and med_dt > 0 else None),
        'laser_active_start_s': (float(t[active[0]]) if active.size else None),
        'laser_active_end_s': (float(t[active[-1]]) if active.size else None),
        'laser_active_duration_s': (float(t[active[-1]] - t[active[0]]) if active.size > 1 else None),
        'frame_trigger_rising_edges': int(frame_edges.size),
        'frame_number_nonnull_count': int(populated_frames.size),
        'frame_number_min': (int(populated_frames.min()) if populated_frames.size else None),
        'frame_number_max': (int(populated_frames.max()) if populated_frames.size else None),
        'relative_absorption_min_pct': float(pd.to_numeric(df['RelativeAbsorption'], errors='coerce').min()),
        'relative_absorption_max_pct': float(pd.to_numeric(df['RelativeAbsorption'], errors='coerce').max()),
    }
    (out / 'SPOT_ABSORPTION_SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    with sync_path.open('r', encoding='utf-8') as f:
        nb = json.load(f)
    code = '\n\n# ---- CELL ----\n\n'.join(
        ''.join(c.get('source', [])) for c in nb.get('cells', []) if c.get('cell_type') == 'code'
    )
    (out / 'SYNC_NOTEBOOK_CODE.txt').write_text(code, encoding='utf-8')
    sync_tokens = {
        'code_cell_count': sum(1 for c in nb.get('cells', []) if c.get('cell_type') == 'code'),
        'mentions_FrameNumber': code.count('FrameNumber'),
        'mentions_FrameTrigger': code.count('FrameTrigger'),
        'mentions_CameraTrigger': code.count('CameraTrigger'),
        'mentions_processed_captioned': code.lower().count('processed'),
    }
    (out / 'SYNC_NOTEBOOK_SUMMARY.json').write_text(json.dumps(sync_tokens, indent=2), encoding='utf-8')

    image_files = sorted([p for p in imgs.rglob('*') if p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'}])
    records = []
    sample_indices = sorted(set([0, len(image_files)//4, len(image_files)//2, 3*len(image_files)//4, max(0, len(image_files)-1)])) if image_files else []
    sample_dir = out / 'sample_frames'
    sample_dir.mkdir(exist_ok=True)
    for i, p in enumerate(image_files):
        try:
            with Image.open(p) as im:
                arr = np.asarray(im.convert('L'))
                records.append({
                    'index': i,
                    'file': p.name,
                    'width': int(im.width),
                    'height': int(im.height),
                    'mode': im.mode,
                    'mean_gray': float(arr.mean()),
                    'std_gray': float(arr.std()),
                    'min_gray': int(arr.min()),
                    'max_gray': int(arr.max()),
                    'sha256': sha256(p),
                })
                if i in sample_indices:
                    im.save(sample_dir / f'{i:04d}_{p.name}')
        except Exception as e:
            records.append({'index': i, 'file': p.name, 'error': repr(e)})

    with (out / 'SPOT_FRAME_INVENTORY.csv').open('w', newline='', encoding='utf-8') as f:
        fieldnames = sorted({k for r in records for k in r.keys()}) if records else ['index', 'file']
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(records)

    name_time_patterns = []
    for p in image_files[:20]:
        nums = re.findall(r'[-+]?\d*\.?\d+', p.stem)
        name_time_patterns.append({'file': p.name, 'numeric_tokens': nums})
    (out / 'IMAGE_NAME_PATTERNS.json').write_text(json.dumps(name_time_patterns, indent=2), encoding='utf-8')

    custody = {
        'dataset': 'NIST A-AMB2022-01 / mds2-2525',
        'holdout_scan_downloaded': False,
        'files': {
            readme_path.name: {'sha256': sha256(readme_path), 'bytes': readme_path.stat().st_size},
            sync_path.name: {'sha256': sha256(sync_path), 'bytes': sync_path.stat().st_size},
            absorption_path.name: {'sha256': sha256(absorption_path), 'bytes': absorption_path.stat().st_size},
            captioned_zip.name: {'sha256': sha256(captioned_zip), 'bytes': captioned_zip.stat().st_size},
        },
        'image_file_count': len(image_files),
        'image_parse_error_count': sum(1 for r in records if 'error' in r),
    }
    (out / 'G48_CUSTODY_AND_STRUCTURE_RESULT.json').write_text(json.dumps(custody, indent=2), encoding='utf-8')

    print(json.dumps({'summary': summary, 'custody': custody, 'sync': sync_tokens}, indent=2))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
