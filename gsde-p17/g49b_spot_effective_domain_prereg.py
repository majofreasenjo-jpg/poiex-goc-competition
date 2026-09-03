from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS_US = (20, 40, 100)


def interp_with_support(t: np.ndarray, y: np.ndarray, q: float) -> tuple[float | None, bool]:
    finite = np.isfinite(t) & np.isfinite(y)
    if finite.sum() < 2:
        return None, False
    tf = t[finite]
    yf = y[finite]
    if q < tf[0] or q > tf[-1]:
        return None, False
    return float(np.interp(q, tf, yf)), True


def main(source_dir: str, g49a_out_dir: str, out_dir: str) -> None:
    src = Path(source_dir)
    g49a = Path(g49a_out_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(src / 'Spot on Bare Metal_Calibrated Absorption Data.csv')
    fmap = pd.read_csv(g49a / 'SPOT_DEVELOPMENT_FRAME_MAP_080_227.csv')

    t = pd.to_numeric(df['Time'], errors='coerce').to_numpy(float)
    rel = pd.to_numeric(df['RelativeAbsorption'], errors='coerce').to_numpy(float)
    unc = pd.to_numeric(df['AbsAbsorptionUncertainty'], errors='coerce').to_numpy(float)
    laser = pd.to_numeric(df['InputLaser'], errors='coerce').to_numpy(float)

    finite_unc = np.isfinite(t) & np.isfinite(unc)
    if not finite_unc.any():
        raise SystemExit('No finite NIST absorption uncertainty support')
    unc_start = float(t[finite_unc].min())
    unc_end = float(t[finite_unc].max())

    rows=[]
    for _, r in fmap.iterrows():
        rr=r.to_dict()
        start=float(r['start_time_s'])
        start_unc = r.get('absolute_absorption_uncertainty_at_frame_start_W')
        start_cal = bool(pd.notna(start_unc) and unc_start <= start <= unc_end)
        rr['sync_admissible'] = r['observation_status'] == 'PASS'
        rr['calibrated_start_admissible'] = start_cal
        for h in HORIZONS_US:
            q=start+h*1e-6
            yq, ysupport = interp_with_support(t, rel, q)
            uq, usupport = interp_with_support(t, unc, q)
            lq, lsupport = interp_with_support(t, laser, q)
            rr[f'target_time_{h}us_s']=q
            rr[f'target_rel_abs_{h}us_pct']=yq
            rr[f'target_abs_unc_{h}us_W']=uq
            rr[f'target_input_laser_{h}us_W']=lq
            rr[f'target_measurement_supported_{h}us']=bool(ysupport)
            rr[f'target_uncertainty_supported_{h}us']=bool(usupport)
            rr[f'effective_domain_H{h}']=bool(rr['sync_admissible'] and start_cal and ysupport and usupport)
        rows.append(rr)

    m=pd.DataFrame(rows)
    m.to_csv(out/'SPOT_EFFECTIVE_DOMAIN_MAP.csv', index=False)

    domains={
        'D_SYNC': m.loc[m.sync_admissible,'frame'].astype(int).tolist(),
        'D_CALIBRATED_START': m.loc[m.calibrated_start_admissible,'frame'].astype(int).tolist(),
    }
    for h in HORIZONS_US:
        domains[f'D_H{h}']=m.loc[m[f'effective_domain_H{h}'],'frame'].astype(int).tolist()

    def compact(x):
        return {'count':len(x),'first':x[0] if x else None,'last':x[-1] if x else None,'frames':x}

    summary={
        'uncertainty_support_start_s':unc_start,
        'uncertainty_support_end_s':unc_end,
        'domains':{k:compact(v) for k,v in domains.items()},
        'rules':[
            'D_SYNC is synchronization/image availability only; it is not the primary empirical domain.',
            'D_CALIBRATED_START requires finite NIST absolute absorption uncertainty at the predictor frame start.',
            'D_Hh additionally requires the h-horizon target time to remain inside finite NIST uncertainty support.',
            'No frame outside D_Hh may enter the primary benchmark for horizon h.',
            '20/40/100 us remain engineering horizons, not causal-age claims.',
            'Scan is untouched and may not be used to alter these domains.'
        ]
    }
    (out/'G49B_EFFECTIVE_DOMAIN_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

    baselines={
        'registry':'P17_STRONG_CONVENTIONAL_AND_EQUAL_ACCESS_RIVALS_V0_1',
        'freeze_scope':'Spot development only; no Scan tuning.',
        'primary_target':'Delta relative absorptance at H20; H40/H100 sensitivity only.',
        'conventional_R1':[
            'B0 absorptance-history persistence/autoregression',
            'B1 B0 + cavity area/equivalent radius',
            'B2 B1 + max depth + width',
            'B3 centroid + aspect ratio + perimeter + compactness + eccentricity or target-native equivalents',
            'B4 normalized depth composition + L1/L2/TV + Jensen-Shannon + Hellinger + entropy + cosine/angular change',
            'B5 conventional derivatives/change-point/CUSUM',
            'B6 PCA/SVD or standard low-dimensional shape basis fit only on Spot training blocks'
        ],
        'equal_access_rivals':[
            'RIVAL_POLY polynomial equal-history model',
            'RIVAL_BILINEAR low-rank bilinear equal-history model',
            'RIVAL_RECURRENT recurrent sequence model with identical history window',
            'RIVAL_GRAPH contour/graph/message-passing model using identical observed masks/history when implemented'
        ],
        'ri002_credit_rule':'RI002 earns distinct credit only if it improves the strongest frozen same-information admissible comparator and the conclusion is invariant to preregistered segmentation/timing perturbations.',
        'ri006_role':'SUPPORT_CONTROL unless a source-faithful turnover/differential-growth-covariance component is isolated and survives compositional/change-point comparators.',
        'forbidden':['random-row CV across autocorrelated frames','Scan-guided feature selection','Scan-guided horizon selection','post-hoc clock choice','future absorptance leakage','calling prediction gain mechanism identification']
    }
    (out/'P17_BASELINE_RIVAL_REGISTRY_V0_1.json').write_text(json.dumps(baselines,indent=2),encoding='utf-8')

    split={
        'name':'P17_SPOT_TEMPORAL_BLOCKED_DEVELOPMENT_PROTOCOL_V0_1',
        'domain_rule':'Use only D_Hh for the corresponding horizon.',
        'cross_validation':'blocked temporal folds; no random row split',
        'recommended_minimum':'contiguous train/validation blocks with purge gap >= maximum model history + maximum target horizon',
        'freeze_before_scan':['segmentation','surface reference','feature definitions','history length','regularization','model classes','hyperparameters','router thresholds','seeds','compute budget','kill criteria'],
        'scan_access':'one-shot only after complete freeze'
    }
    (out/'P17_SPOT_BLOCKED_CV_PROTOCOL_V0_1.json').write_text(json.dumps(split,indent=2),encoding='utf-8')

    firewalls=[
        'SYNCHRONIZED_FRAME != CALIBRATED_BENCHMARK_FRAME',
        'FINITE_IMAGE != FINITE_ABSORPTION_UNCERTAINTY',
        'TARGET_AVAILABLE != TARGET_UNCERTAINTY_SUPPORTED',
        'FRAME_HORIZON != CAUSAL_CLOCK',
        'BLOCKED_TEMPORAL_CV_REQUIRED=TRUE',
        'RANDOM_ROW_CV=FORBIDDEN',
        'SCAN_HOLDOUT_DOWNLOADED=FALSE',
        'SCAN_HOLDOUT_INSPECTED=FALSE',
        'EMPIRICAL_BENCHMARK_EXECUTED=FALSE',
    ]
    (out/'G49B_ADJUDICATION.txt').write_text('\n'.join(firewalls)+'\n',encoding='utf-8')

    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main(sys.argv[1],sys.argv[2],sys.argv[3])
