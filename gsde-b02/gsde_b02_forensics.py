from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler
from gsde_b02_remote_benchmark import (
    HORIZON, download_and_verify, parse_events, load_year, positive_mask,
    episodes, far30, calibrate, eval_method
)

ENG=['M1','M3','M4']

def active_mask(ts,events):
    t=np.asarray(ts,dtype='datetime64[ns]'); m=np.zeros(len(t),bool)
    for e in events: m|=(t>=np.datetime64(e.start))&(t<=np.datetime64(e.end))
    return m

def diag_bundle(Xfit,X18,X19,ncomp):
    pca=PCA(n_components=min(ncomp,Xfit.shape[1]),random_state=0).fit(Xfit)
    def raw(X):
        S=pca.transform(X); n=S.shape[1]; r=1+(np.arange(n)+1)/n
        e=S*S; W=e.sum(1); qb=np.divide(e@r,W,out=np.ones_like(W),where=W>1e-12); m1=np.log(np.maximum(qb,1e-12))
        a=np.abs(X)+1e-12; total=a.sum(1); pi=np.arange(33); fi=np.arange(33,36); q=np.linspace(1,2,X.shape[1])
        m=a[:,pi].sum(1)/total; qi=(a[:,pi]@q[pi])/(a[:,pi].sum(1)+1e-12); qo=(a[:,fi]@q[fi])/(a[:,fi].sum(1)+1e-12); qbar=(a@q)/(total+1e-12)
        m3=2*m*(1-m)*(qi-qo)/(qbar+1e-12)
        m4=np.zeros(len(X)); u=S[:-1]; b=S[1:]-S[:-1]; u2=(u*u).sum(1); dot=(b*u).sum(1); proj=np.divide(dot,u2,out=np.zeros_like(dot),where=u2>1e-12)[:,None]*u
        perp=b-proj; cur=2*(perp*perp).sum(1); small=u2<=1e-12; cur[small]=2*(b[small]*b[small]).sum(1); m4[1:]=cur
        return np.c_[m1,m3,m4],m
    Df,mf=raw(Xfit); D18,m18=raw(X18); D19,m19=raw(X19)
    c=np.nanmedian(Df,0); mad=np.nanmedian(np.abs(Df-c),0); sc=1.4826*mad; st=np.nanstd(Df,0); sc=np.where(sc>1e-12,sc,np.where(st>1e-12,st,1.0))
    Zf=np.abs((Df-c)/sc); Z18=np.abs((D18-c)/sc); Z19=np.abs((D19-c)/sc); inner=np.nanquantile(Zf,1-.01/3,axis=0)
    return pca,D18,D19,Z18/(inner+1e-12),Z19/(inner+1e-12),inner,m18,m19

def stats(x):
    x=np.asarray(x,float); return {'median':float(np.nanmedian(x)),'q95':float(np.nanquantile(x,.95)),'q99':float(np.nanquantile(x,.99)),'mean':float(np.nanmean(x)),'std':float(np.nanstd(x))}

def strat(m):
    for typ in ('abrupt','incipient'):
        a=[r for r in m['events'] if r['leak_type']==typ]; m[typ+'_recall']=sum(r['detected'] for r in a)/len(a)
    return m

def frontier(score,ts,events):
    rows=[]
    for q in np.unique(np.r_[np.linspace(.90,.99,19),np.linspace(.992,.999,15),[.9992,.9994,.9996,.9998,.9999,.99995]]):
        m=strat(eval_method(score,float(np.quantile(score,q)),ts,events)); rows.append({'q':float(q),'recall':m['recall'],'far30':m['false_alarm_episodes_per_30d'],'delay':m['median_censored_delay_minutes']})
    best={}
    for lim in (.25,1,5,15):
        ok=[r for r in rows if r['far30']<=lim+1e-12]; best[str(lim)]=max(ok,key=lambda r:(r['recall'],-r['delay'])) if ok else None
    return best

def variant(d18,d19,cols,ev18,ev19,fit_mask=None,ncomp=8,do_frontier=False):
    A=d18[cols].to_numpy(float); B=d19[cols].to_numpy(float); sf=RobustScaler().fit(A if fit_mask is None else A[fit_mask]); X18=sf.transform(A); X19=sf.transform(B); Xfit=X18 if fit_mask is None else X18[fit_mask]
    pca,D18,D19,R18,R19,inner,m18,m19=diag_bundle(Xfit,X18,X19,ncomp)
    idx={'M1':[0],'M3':[1],'M4':[2],'M1_M3':[0,1],'M1_M4':[0,2],'M3_M4':[1,2],'M1_M3_M4':[0,1,2]}; methods={}
    for name,ii in idx.items():
        s18=np.max(R18[:,ii],1); s19=np.max(R19[:,ii],1); cal=calibrate(s18,d18.Timestamp.to_numpy(),ev18); met=strat(eval_method(s19,cal['threshold'],d19.Timestamp.to_numpy(),ev19))
        methods[name]={'calibration':cal,'evaluation':met}
        if do_frontier: methods[name]['oracle_2019_best_by_far30']=frontier(s19,d19.Timestamp.to_numpy(),ev19)
    peaks=[]; t=d19.Timestamp.to_numpy(dtype='datetime64[ns]'); h=np.timedelta64(HORIZON,'m')
    for e in ev19:
        s=np.datetime64(e.start); mask=(t>=s)&(t<=min(np.datetime64(e.end),s+h)); pk=np.max(R19[mask],0); peaks.append({'link_id':e.link_id,'leak_type':e.leak_type,**{ENG[i]:float(pk[i]) for i in range(3)}})
    return {'fit_rows':int(len(Xfit)),'ncomp':ncomp,'cum_evr':float(np.sum(pca.explained_variance_ratio_)),'evr':pca.explained_variance_ratio_.tolist(),'inner_thresholds':dict(zip(ENG,map(float,inner))),
            'diag_2018':{ENG[i]:stats(D18[:,i]) for i in range(3)},'diag_2019':{ENG[i]:stats(D19[:,i]) for i in range(3)},'pressure_mass_2018':stats(m18),'pressure_mass_2019':stats(m19),'methods':methods,'event_peaks':peaks}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--raw-dir',default='raw'); ap.add_argument('--out-dir',default='artifacts'); a=ap.parse_args(); raw=Path(a.raw_dir); out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    custody=download_and_verify(raw); events=parse_events(raw/'dataset_configuration.yaml'); ev18=[e for e in events if e.start.year==2018]; ev19=[e for e in events if e.start.year==2019]
    d18,p,f=load_year(raw,2018); d19,p2,f2=load_year(raw,2019); cols=p+f; nominal=~active_mask(d18.Timestamp.to_numpy(),ev18); assert nominal.sum()==2178
    frozen=variant(d18,d19,cols,ev18,ev19,None,8,True); strict=variant(d18,d19,cols,ev18,ev19,nominal,8,False)
    dims=[]
    for n in (4,8,16,24,36):
        v=variant(d18,d19,cols,ev18,ev19,None,n,False); e=v['methods']['M1_M3_M4']['evaluation']; dims.append({'ncomp':n,'cum_evr':v['cum_evr'],'recall':e['recall'],'abrupt_recall':e['abrupt_recall'],'incipient_recall':e['incipient_recall'],'delay':e['median_censored_delay_minutes'],'far30':e['false_alarm_episodes_per_30d']})
    comp=[]
    for name,r in frozen['methods'].items():
        e=r['evaluation']; c=r['calibration']; comp.append({'method':name,'cal_q':c['quantile'],'cal_far30':c['calibration_far_30d'],'recall':e['recall'],'abrupt_recall':e['abrupt_recall'],'incipient_recall':e['incipient_recall'],'delay':e['median_censored_delay_minutes'],'far30':e['false_alarm_episodes_per_30d'],'episodes':e['episode_count']})
    report={'status':'B02_POST_FAIL_EXPLORATORY_FORENSICS_ONLY','firewalls':['2019_POST_FAIL_EXPLORATORY_ONLY','NO_CONFIRMATORY_CREDIT','B02_V1_2_FAIL_IMMUTABLE','NO_RETROACTIVE_RESCUE'],
            'custody':custody,'strict_nominal_rows':int(nominal.sum()),'frozen_fit':frozen,'strict_nominal_fit_sensitivity':strict,'latent_dim_sensitivity':dims,'comparison':comp}
    (out/'B02_G4_4_POST_FAIL_FORENSICS.json').write_text(json.dumps(report,indent=2)); pd.DataFrame(comp).to_csv(out/'B02_ENGINE_COMPARISON.csv',index=False); pd.DataFrame(frozen['event_peaks']).to_csv(out/'B02_EVENT_ENGINE_PEAKS.csv',index=False); pd.DataFrame(dims).to_csv(out/'B02_LATENT_DIM_SENSITIVITY.csv',index=False)
    print(json.dumps({'comparison':comp,'latent_dims':dims,'strict_combo':strict['methods']['M1_M3_M4']['evaluation'],'cum_evr_8':frozen['cum_evr'],'pressure_mass_2018':frozen['pressure_mass_2018'],'pressure_mass_2019':frozen['pressure_mass_2019']},indent=2))
if __name__=='__main__': main()
