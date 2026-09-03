from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error

ALPHAS=(0.01,0.1,1.0,10.0,100.0,1000.0)
KS=(2,4,8)
FOLD_STARTS=(18,25,32,39,46)


def blockavg_30x32(a: np.ndarray) -> np.ndarray:
    if a.shape != (600,640): raise RuntimeError(f'Expected raw mask shape 600x640, got {a.shape}')
    return a.reshape(30,20,32,20).mean(axis=(1,3)).ravel()


def cv_splits(n:int):
    out=[]
    for s in FOLD_STARTS:
        e=min(s+7,n)
        if e>s: out.append((np.arange(s),np.arange(s,e)))
    return out


def ridge_cv_base(X,y):
    folds=cv_splits(len(y)); best=None
    for a in ALPHAS:
        ps=[]; ys=[]
        for tr,va in folds:
            sc=StandardScaler().fit(X[tr]); m=Ridge(alpha=a).fit(sc.transform(X[tr]),y[tr])
            ps.extend(m.predict(sc.transform(X[va]))); ys.extend(y[va])
        rm=float(mean_squared_error(ys,ps)**0.5)
        if best is None or rm<best[0]: best=(rm,a)
    return best


def ridge_cv_rep(base,R,y):
    folds=cv_splits(len(y)); best=None
    for k in KS:
        for a in ALPHAS:
            ps=[];ys=[]
            for tr,va in folds:
                p=PCA(n_components=k,svd_solver='full').fit(R[tr])
                Xtr=np.c_[base[tr],p.transform(R[tr])]; Xva=np.c_[base[va],p.transform(R[va])]
                sc=StandardScaler().fit(Xtr); m=Ridge(alpha=a).fit(sc.transform(Xtr),y[tr])
                ps.extend(m.predict(sc.transform(Xva)));ys.extend(y[va])
            rm=float(mean_squared_error(ys,ps)**0.5)
            if best is None or rm<best[0]: best=(rm,k,a)
    return best


def main(geom_csv,safe_csv,effective_csv,masks_npz,out_dir):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    geom=pd.read_csv(geom_csv); safe=pd.read_csv(safe_csv); eff=pd.read_csv(effective_csv)
    z=np.load(masks_npz); by={int(f):m.astype(np.float64) for f,m in zip(z['frames'],z['masks'])}
    df=(geom.merge(safe[['frame','V_amp_backward_um_per_s','predictor_admissible_H20']],on='frame',how='left')
            .merge(eff[['frame','delta_rel_abs_20us_pctpt']],on='frame',how='left').sort_values('frame'))
    for lag in (1,2,3): df[f'abs_lag{lag}']=df['relative_absorption_at_frame_start_pct'].shift(lag)
    use=df[df['predictor_admissible_H20']==True].copy().sort_values('frame').reset_index(drop=True)
    if len(use)!=53: raise RuntimeError(f'Expected 53 predictor-safe Spot rows, got {len(use)}')

    reps={'RAW_PAIR_PCA':[],'NORMALIZED_PAIR_PCA':[],'RAW_DIFF_PCA':[],'PROJECTIVE_TANGENT_PCA':[]}
    identity_rows=[]
    for f in use.frame.astype(int):
        now=by[f]; prev=by[f-1]; nn=float(now.sum()); npv=float(prev.sum())
        if nn<=0 or npv<=0: raise RuntimeError(f'Zero support in predictor-safe frame {f}')
        sn=now/math.sqrt(nn); sp=prev/math.sqrt(npv); c=float((now*prev).sum()/math.sqrt(nn*npv)); tangent=sn-c*sp
        ortho=float(np.sum(tangent*sp))
        identity_rows.append({'frame':f,'cosine':c,'tangent_prev_inner_product':ortho,'tangent_norm':float(np.linalg.norm(tangent)),'sqrt_1_minus_cos2':math.sqrt(max(0.0,1-c*c))})
        reps['RAW_PAIR_PCA'].append(np.r_[blockavg_30x32(prev),blockavg_30x32(now)])
        reps['NORMALIZED_PAIR_PCA'].append(np.r_[blockavg_30x32(sp),blockavg_30x32(sn)])
        reps['RAW_DIFF_PCA'].append(blockavg_30x32(now-prev))
        reps['PROJECTIVE_TANGENT_PCA'].append(blockavg_30x32(tangent))
    for k in reps: reps[k]=np.asarray(reps[k],dtype=float)

    base=use[['relative_absorption_at_frame_start_pct','abs_lag1','abs_lag2','abs_lag3','amplitude_sqrt_um2','V_amp_backward_um_per_s']].replace([np.inf,-np.inf],np.nan).fillna(0).to_numpy(float)
    y=use['delta_rel_abs_20us_pctpt'].to_numpy(float)
    rows=[]; b=ridge_cv_base(base,y); rows.append({'representation':'BASE_CONTEXT_ONLY','latent_dim':0,'selected_alpha':b[1],'development_forward_cv_rmse':b[0]})
    for name,R in reps.items():
        best=ridge_cv_rep(base,R,y); rows.append({'representation':name,'latent_dim':best[1],'selected_alpha':best[2],'development_forward_cv_rmse':best[0]})
    res=pd.DataFrame(rows).sort_values('development_forward_cv_rmse').reset_index(drop=True); res.to_csv(out/'G49E_REPRESENTATION_EFFICIENCY_TOURNAMENT.csv',index=False)
    ident=pd.DataFrame(identity_rows); ident.to_csv(out/'G49E_PROJECTIVE_TANGENT_IDENTITY.csv',index=False)

    proj=float(res.loc[res.representation=='PROJECTIVE_TANGENT_PCA','development_forward_cv_rmse'].iloc[0])
    conv=res[res.representation.isin(['RAW_PAIR_PCA','NORMALIZED_PAIR_PCA','RAW_DIFF_PCA'])].sort_values('development_forward_cv_rmse'); best_conv=float(conv.iloc[0].development_forward_cv_rmse); best_conv_name=str(conv.iloc[0].representation)
    base_rm=float(res.loc[res.representation=='BASE_CONTEXT_ONLY','development_forward_cv_rmse'].iloc[0]); relative_vs_best=(best_conv-proj)/best_conv
    ortho_max=float(np.max(np.abs(ident.tangent_prev_inner_product))); norm_err=float(np.max(np.abs(ident.tangent_norm-ident.sqrt_1_minus_cos2)))
    status='DEVELOPMENT_NEGATIVE_PROJECTIVE_TANGENT_NOT_SELECTED' if proj>=best_conv else 'DEVELOPMENT_CANDIDATE_PROJECTIVE_TANGENT'
    adj={'status':status,'spot_role':'DEVELOPMENT_EXPLORATORY_ONLY_AFTER_G4_9D_INTERNAL_HOLDOUT_OPENED','predictor_safe_rows':53,'fold_starts':list(FOLD_STARTS),'fold_validation_width':7,'latent_budget_candidates':list(KS),'ridge_alphas':list(ALPHAS),'base_context_cv_rmse':base_rm,'projective_tangent_cv_rmse':proj,'best_conventional_equal_access_representation':best_conv_name,'best_conventional_cv_rmse':best_conv,'projective_relative_gain_vs_best_conventional':relative_vs_best,'projective_tangent_orthogonality_max_abs':ortho_max,'projective_tangent_norm_identity_max_abs_error':norm_err,'information_novelty_claim':False,'representation_efficiency_claim':'DEVELOPMENT_ONLY','scan_holdout_downloaded':False,'scan_holdout_inspected':False,'claim_ceiling':'Spot-only exploratory representation-efficiency result; zero confirmatory credit; no mechanism identification; no cross-domain validation.'}
    (out/'G49E_ADJUDICATION.json').write_text(json.dumps(adj,indent=2),encoding='utf-8')
    lines=['G4_9E_PROJECTIVE_FIELD_EFFICIENCY='+status,'SPOT_ROLE=DEVELOPMENT_EXPLORATORY_ONLY','PROJECTIVE_FIELD_INFORMATION_NOVELTY=NOT_CLAIMED','EQUAL_ACCESS_CONVENTIONAL_RIVAL_REQUIRED=TRUE','SCAN_HOLDOUT_DOWNLOADED=FALSE','SCAN_HOLDOUT_INSPECTED=FALSE','NO_CONFIRMATORY_CREDIT=TRUE']
    (out/'G49E_ADJUDICATION.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(adj,indent=2)); print(res.to_string(index=False))

if __name__=='__main__': main(*sys.argv[1:])
