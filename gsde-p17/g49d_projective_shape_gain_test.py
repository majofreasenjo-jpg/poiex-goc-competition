from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error

DEV_LAST_FRAME=169
INTERNAL_HOLDOUT_FIRST=170
INTERNAL_HOLDOUT_LAST=181
ALPHAS=(0.01,0.1,1.0,10.0,100.0,1000.0)
IDENTITY_ABS_TOL=0.05
IDENTITY_REL_TOL=1e-5


def expanding_folds(n:int):
    starts=(15,22,29,36)
    out=[]
    for s in starts:
        e=min(s+7,n)
        if e>s: out.append((np.arange(s),np.arange(s,e)))
    return out


def fit_ridge_cv(X,y):
    folds=expanding_folds(len(y)); best=None
    for alpha in ALPHAS:
        preds=[]; ys=[]
        for tr,va in folds:
            model=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
            model.fit(X[tr],y[tr]); preds.extend(model.predict(X[va])); ys.extend(y[va])
        rmse=mean_squared_error(ys,preds)**0.5
        if best is None or rmse<best[0]: best=(rmse,alpha)
    model=make_pipeline(StandardScaler(),Ridge(alpha=best[1])).fit(X,y)
    return model,best,folds


def main(geom_csv,safe_csv,effective_csv,masks_npz,out_dir):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    geom=pd.read_csv(geom_csv); safe=pd.read_csv(safe_csv); eff=pd.read_csv(effective_csv)
    z=np.load(masks_npz); frames=z['frames']; masks=z['masks'].astype(np.float64)
    by={int(f):m for f,m in zip(frames,masks)}
    df=geom.merge(safe[['frame','prev_frame','dt_backward_s','V_shape_backward_s_inv','V_amp_backward_um_per_s','predictor_admissible_H20']],on='frame',how='left')
    df=df.merge(eff[['frame','delta_rel_abs_20us_pctpt']],on='frame',how='left')
    df=df.sort_values('frame').reset_index(drop=True)
    for lag in (1,2,3): df[f'abs_lag{lag}']=df['relative_absorption_at_frame_start_pct'].shift(lag)
    scalar=['area_um2','max_normal_depth_um','tangent_width_um','centroid_normal_um','centroid_tangent_um','perimeter_um','compactness','eccentricity','depth_to_width_ratio']
    for c in scalar: df[c+'_d1']=df[c]-df[c].shift(1)
    bins=[f'depth_comp_bin_{i}' for i in range(8)]
    P=df[bins].fillna(0).to_numpy(float); Q=np.vstack([np.zeros((1,8)),P[:-1]]); eps=1e-12; M=.5*(P+Q)
    df['depth_js']=.5*np.sum(np.where(P>0,P*np.log((P+eps)/(M+eps)),0),axis=1)+.5*np.sum(np.where(Q>0,Q*np.log((Q+eps)/(M+eps)),0),axis=1)
    df['depth_hell']=np.sqrt(.5*np.sum((np.sqrt(np.maximum(P,0))-np.sqrt(np.maximum(Q,0)))**2,axis=1))
    df['depth_l1']=np.sum(np.abs(P-Q),axis=1)
    df['depth_l2']=np.sqrt(np.sum((P-Q)**2,axis=1))
    df['depth_entropy']=-np.sum(np.where(P>0,P*np.log(P+eps),0),axis=1)

    cosd=[]; angular_speed=[]; ident_rows=[]
    for _,r in df.iterrows():
        f=int(r.frame); prev=f-1; a=by.get(f); b=by.get(prev)
        if a is None or b is None or a.sum()<=0 or b.sum()<=0:
            cosd.append(np.nan); angular_speed.append(np.nan); continue
        cos=float((a*b).sum()/math.sqrt(a.sum()*b.sum())); d=max(0.0,1.0-cos); cosd.append(d)
        dt=float(r.dt_backward_s) if pd.notna(r.dt_backward_s) else np.nan
        v=math.sqrt(2.0*d)/dt if np.isfinite(dt) and dt>0 else np.nan; angular_speed.append(v)
        if bool(r.predictor_admissible_H20):
            ri=float(r.V_shape_backward_s_inv); ae=abs(ri-v); re=ae/max(abs(ri),1.0)
            ident_rows.append({'frame':f,'V_shape_RI002':ri,'cosine_distance_conventional':d,'angular_speed_conventional':v,'abs_error':ae,'rel_error':re})
    df['mask_cosine_distance_backward']=cosd; df['conventional_angular_speed_s_inv']=angular_speed
    ident=pd.DataFrame(ident_rows); ident.to_csv(out/'RI002_VSHAPE_COSINE_IDENTITY_53.csv',index=False)
    max_abs=float(ident.abs_error.max()); max_rel=float(ident.rel_error.max()); identity_pass=max_abs<=IDENTITY_ABS_TOL and max_rel<=IDENTITY_REL_TOL

    use=df[df.predictor_admissible_H20==True].copy().sort_values('frame').reset_index(drop=True)
    if len(use)!=53: raise RuntimeError(f'Expected 53 predictor-safe rows, got {len(use)}')
    dev=use[use.frame<=DEV_LAST_FRAME].copy(); hold=use[(use.frame>=INTERNAL_HOLDOUT_FIRST)&(use.frame<=INTERNAL_HOLDOUT_LAST)].copy()
    if len(dev)!=41 or len(hold)!=12: raise RuntimeError(f'Frozen split mismatch dev={len(dev)} hold={len(hold)}')

    base_abs=['relative_absorption_at_frame_start_pct','abs_lag1','abs_lag2','abs_lag3']
    r1=base_abs+scalar+[c+'_d1' for c in scalar]+['depth_js','depth_hell','depth_l1','depth_l2','depth_entropy','V_amp_backward_um_per_s','mask_cosine_distance_backward','conventional_angular_speed_s_inv']
    modelsets={'B0_ABSORPTANCE_HISTORY':base_abs,'R1_STRONG_CONVENTIONAL':r1,'R1_PLUS_RI002_VSHAPE':r1+['V_shape_backward_s_inv']}
    ydev=dev.delta_rel_abs_20us_pctpt.to_numpy(float); yhold=hold.delta_rel_abs_20us_pctpt.to_numpy(float)
    result_rows=[]; pred_table=pd.DataFrame({'frame':hold.frame.astype(int),'target_delta_rel_abs_20us_pctpt':yhold})
    for name,cols in modelsets.items():
        Xdev=dev[cols].replace([np.inf,-np.inf],np.nan).fillna(0).to_numpy(float); Xhold=hold[cols].replace([np.inf,-np.inf],np.nan).fillna(0).to_numpy(float)
        model,best,folds=fit_ridge_cv(Xdev,ydev); pred=model.predict(Xhold)
        rmse=float(mean_squared_error(yhold,pred)**0.5); mae=float(mean_absolute_error(yhold,pred)); corr=float(np.corrcoef(yhold,pred)[0,1]) if np.std(pred)>0 and np.std(yhold)>0 else None
        result_rows.append({'model':name,'feature_count':len(cols),'dev_forward_cv_rmse':float(best[0]),'selected_alpha':float(best[1]),'internal_holdout_rmse':rmse,'internal_holdout_mae':mae,'internal_holdout_corr':corr})
        pred_table[name]=pred
    results=pd.DataFrame(result_rows); results.to_csv(out/'G49D_MODEL_TOURNAMENT.csv',index=False); pred_table.to_csv(out/'G49D_INTERNAL_HOLDOUT_PREDICTIONS.csv',index=False)
    r1row=results.set_index('model').loc['R1_STRONG_CONVENTIONAL']; rirow=results.set_index('model').loc['R1_PLUS_RI002_VSHAPE']; b0row=results.set_index('model').loc['B0_ABSORPTANCE_HISTORY']
    incremental=(float(r1row.internal_holdout_rmse)-float(rirow.internal_holdout_rmse))/float(r1row.internal_holdout_rmse)
    adjudication={
      'status':'CLOSED_MATERIAL_NEGATIVE_SEAL','predictor_safe_support_count':53,'development_count':41,'development_frames':'127-169','internal_holdout_count':12,'internal_holdout_frames':'170-181',
      'identity_max_abs_error_s_inv':max_abs,'identity_max_relative_error':max_rel,'identity_pass':identity_pass,
      'mathematical_identity':'V_shape^- = sqrt(2 - 2*cos(s_t,s_t-1))/dt; for normalized binary masks cos = |intersection|/sqrt(|K_t||K_t-1|)',
      'b0_holdout_rmse':float(b0row.internal_holdout_rmse),'r1_holdout_rmse':float(r1row.internal_holdout_rmse),'r1_plus_ri002_holdout_rmse':float(rirow.internal_holdout_rmse),'ri002_relative_rmse_gain_vs_r1':incremental,
      'ri002_scalar_vshape_unique_information_credit':'DENIED_FOR_CURRENT_BINARY_MASK_INSTANTIATION' if identity_pass else 'HOLD','ri002_amplitude_shape_decomposition':'RETAIN_AS_STRUCTURAL_REPRESENTATION','ri002_distinct_predictor_credit':'DENIED_FOR_SCALAR_VSHAPE_CURRENT_INSTANTIATION' if identity_pass else 'HOLD',
      'scan_holdout_downloaded':False,'scan_holdout_inspected':False,'claim_ceiling':'Internal mathematical identity + Spot-only empirical corroboration; no cross-domain validation; no mechanism identification.'}
    (out/'G49D_ADJUDICATION.json').write_text(json.dumps(adjudication,indent=2),encoding='utf-8')
    lines=['G4_9D_PROJECTIVE_SHAPE_GAIN_TEST=CLOSED_MATERIAL_NEGATIVE_SEAL',f'RI002_VSHAPE_COSINE_IDENTITY_PASS={str(identity_pass).upper()}','RI002_SCALAR_VSHAPE_UNIQUE_INFORMATION_CREDIT=DENIED_FOR_CURRENT_BINARY_MASK_INSTANTIATION' if identity_pass else 'RI002_SCALAR_VSHAPE_UNIQUE_INFORMATION_CREDIT=HOLD','RI002_AMPLITUDE_SHAPE_DECOMPOSITION=RETAIN_STRUCTURAL_REPRESENTATION','PREDICTION_GAIN != INFORMATION_GAIN','PARAMETERIZATION_GAIN != MATHEMATICAL_NOVELTY','FORWARD_RI002_KINEMATICS=FORBIDDEN_AS_PREDICTOR','SCAN_HOLDOUT_DOWNLOADED=FALSE','SCAN_HOLDOUT_INSPECTED=FALSE']
    (out/'G49D_ADJUDICATION.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(adjudication,indent=2)); print(results.to_string(index=False))

if __name__=='__main__': main(*sys.argv[1:])
