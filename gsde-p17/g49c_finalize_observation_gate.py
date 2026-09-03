from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MIN_REPRESENTATION_SUPPORT = 7
MIN_MEDIAN_JACCARD = 0.80
LASER_EXCITATION_THRESHOLD_W = 10.0


def shape_speed(m_prev: np.ndarray, m_now: np.ndarray, dt_s: float) -> float | None:
    n0 = int(m_prev.sum()); n1 = int(m_now.sum())
    if n0 <= 0 or n1 <= 0 or dt_s <= 0:
        return None
    s0 = m_prev.astype(np.float32) / math.sqrt(n0)
    s1 = m_now.astype(np.float32) / math.sqrt(n1)
    return float(np.linalg.norm(s1 - s0) / dt_s)


def main(out_dir: str) -> None:
    out = Path(out_dir)
    geom = pd.read_csv(out / 'SPOT_RAW_GEOMETRY_NOMINAL_AND_UNCERTAINTY.csv').sort_values('frame').reset_index(drop=True)
    npz = np.load(out / 'SPOT_NOMINAL_MASKS_080_227.npz')
    frames = npz['frames'].astype(int)
    masks = npz['masks'].astype(bool)
    mask_by_frame = {int(f): masks[i] for i, f in enumerate(frames)}

    # Causal excitation state: no vapor depression is physically admissible before the laser has fired.
    laser_now = pd.to_numeric(geom['input_laser_at_frame_start_W'], errors='coerce').fillna(0.0) >= LASER_EXCITATION_THRESHOLD_W
    laser_has_fired = laser_now.cummax()

    h20 = geom['effective_domain_H20'].fillna(False).astype(bool) if 'effective_domain_H20' in geom else pd.Series(False, index=geom.index)
    present = geom['mask_present'].fillna(False).astype(bool)
    rep_support = pd.to_numeric(geom['representation_present_count'], errors='coerce').fillna(0) >= MIN_REPRESENTATION_SUPPORT
    rep_j = pd.to_numeric(geom['jaccard_median_vs_nominal'], errors='coerce').fillna(-1.0) >= MIN_MEDIAN_JACCARD
    identified = h20 & laser_has_fired & present & rep_support & rep_j

    states = []
    for i, r in geom.iterrows():
        if not h20.iloc[i]: state = 'OUTSIDE_H20_EFFECTIVE_DOMAIN'
        elif not laser_has_fired.iloc[i]: state = 'NO_CAUSAL_LASER_EXCITATION'
        elif not present.iloc[i]: state = 'MASK_ABSENT'
        elif not rep_support.iloc[i]: state = 'REPRESENTATION_SUPPORT_HOLD'
        elif not rep_j.iloc[i]: state = 'REPRESENTATION_INSTABILITY_HOLD'
        else: state = 'IDENTIFIED_OBSERVATION_PASS'
        states.append(state)
    geom['laser_has_fired'] = laser_has_fired
    geom['identified_observation_H20'] = identified
    geom['identified_observation_state_H20'] = states
    geom.to_csv(out / 'SPOT_GEOMETRY_WITH_IDENTIFIED_OBSERVATION_GATE.csv', index=False)

    # Leakage-safe backward kinematics. Predictor at frame t uses only masks at t-1 and t.
    rows = []
    prev = None
    for i, r in geom.iterrows():
        f = int(r['frame'])
        rec = {'frame': f, 'identified_observation_H20': bool(identified.iloc[i])}
        if prev is None:
            rec.update({'prev_frame': None, 'dt_backward_s': None, 'V_shape_backward_s_inv': None, 'V_amp_backward_um_per_s': None, 'predictor_admissible_H20': False})
        else:
            pf = int(prev['frame'])
            dt = float(r['start_time_s'] - prev['start_time_s'])
            both_identified = bool(identified.iloc[i] and identified.iloc[i-1])
            if both_identified and pf in mask_by_frame and f in mask_by_frame:
                m0 = mask_by_frame[pf]; m1 = mask_by_frame[f]
                vs = shape_speed(m0, m1, dt)
                a0 = math.sqrt(float(m0.sum()) * (1.923**2)) if m0.sum() else None
                a1 = math.sqrt(float(m1.sum()) * (1.923**2)) if m1.sum() else None
                va = abs(a1-a0)/dt if a0 is not None and a1 is not None and dt > 0 else None
                admissible = vs is not None and va is not None
            else:
                vs = va = None; admissible = False
            rec.update({'prev_frame': pf, 'dt_backward_s': dt, 'V_shape_backward_s_inv': vs, 'V_amp_backward_um_per_s': va, 'predictor_admissible_H20': admissible})
        rows.append(rec); prev = r
    kin = pd.DataFrame(rows)
    kin.to_csv(out / 'RI002_BACKWARD_PREDICTOR_SAFE_KINEMATICS_SPOT.csv', index=False)

    pass_frames = geom.loc[identified, 'frame'].astype(int).tolist()
    predictor_frames = kin.loc[kin['predictor_admissible_H20'].fillna(False), 'frame'].astype(int).tolist()
    runs = []
    if pass_frames:
        a = b = pass_frames[0]
        for f in pass_frames[1:]:
            if f == b + 1: b = f
            else: runs.append([a,b]); a=b=f
        runs.append([a,b])

    pre_activation_false_candidates = int(((geom['frame'] < int(geom.loc[laser_now, 'frame'].min())) & present).sum()) if laser_now.any() else int(present.sum())
    pre_activation_admitted = int(((geom['frame'] < int(geom.loc[laser_now, 'frame'].min())) & identified).sum()) if laser_now.any() else 0

    summary = {
        'gate': 'P17_SPOT_IDENTIFIED_OBSERVATION_GATE_V0_1',
        'primary_horizon': '20 us engineering horizon, not causal clock',
        'criteria': {
            'effective_domain_H20': True,
            'causal_laser_excitation': f'cumulative InputLaser >= {LASER_EXCITATION_THRESHOLD_W} W',
            'nominal_mask_present': True,
            'representation_support_min_of_9': MIN_REPRESENTATION_SUPPORT,
            'median_jaccard_vs_nominal_min': MIN_MEDIAN_JACCARD,
            'surface_attachment_and_300um_support': 'enforced upstream by segmentation V3',
        },
        'identified_frame_count': len(pass_frames),
        'identified_first_frame': pass_frames[0] if pass_frames else None,
        'identified_last_frame': pass_frames[-1] if pass_frames else None,
        'identified_contiguous_runs': runs,
        'backward_predictor_admissible_frame_count': len(predictor_frames),
        'backward_predictor_first_frame': predictor_frames[0] if predictor_frames else None,
        'backward_predictor_last_frame': predictor_frames[-1] if predictor_frames else None,
        'pre_activation_raw_candidate_count': pre_activation_false_candidates,
        'pre_activation_admitted_count': pre_activation_admitted,
        'forward_kinematics_role': 'DESCRIPTIVE_DIAGNOSTIC_ONLY_FORBIDDEN_AS_PREDICTOR',
        'scan_holdout_downloaded': False,
        'scan_holdout_inspected': False,
        'empirical_benchmark_executed': False,
    }
    (out / 'G49C_IDENTIFIED_OBSERVATION_GATE_SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    with (out / 'G49C_ADJUDICATION.txt').open('a', encoding='utf-8') as f:
        f.write('G4_9C_IDENTIFIED_OBSERVATION_GATE=FROZEN_SPOT_ONLY\n')
        f.write(f'IDENTIFIED_H20_FRAMES={len(pass_frames)}\n')
        f.write(f'BACKWARD_PREDICTOR_ADMISSIBLE_H20_FRAMES={len(predictor_frames)}\n')
        f.write('FORWARD_RI002_KINEMATICS=DESCRIPTIVE_ONLY_FORBIDDEN_AS_PREDICTOR\n')
        f.write('BACKWARD_RI002_KINEMATICS=ONLY_PREDICTOR_SAFE_KINEMATICS\n')
        f.write('NO_FUTURE_IMAGE_ACCESS=TRUE\n')
        f.write('PREDICTOR_SUPPORT_MUST_BE_MATCHED_ACROSS_RIVALS=TRUE\n')

    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main(sys.argv[1])
