from __future__ import annotations
import argparse, hashlib, json, urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler

ZENODO='https://zenodo.org/records/4017659/files/'
FILES={'2018_SCADA_Flows.csv':'d0602c06946b46287e956f007e4264ee','2018_SCADA_Pressures.csv':'d389d8541350c19ff0bfc6b80f246d35','2019_SCADA_Flows.csv':'28fc99fdcbf80fcd26079e7fe602d6dc','2019_SCADA_Pressures.csv':'5ea1e46d3f2f0a89a3f98d6fd39a851d','dataset_configuration.yaml':'48486401f5b4d0447023f5ce5d242c52'}
HORIZON=10080; COOLDOWN=60; TARGET_CAL_FAR_30D=1.0
@dataclass(frozen=True)
class Event: link_id:str; start:datetime; end:datetime; diameter_m:float; leak_type:str; peak:datetime

def hash_file(p,algo):
 h=hashlib.new(algo)
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def download_and_verify(root:Path):
 root.mkdir(parents=True,exist_ok=True); rec={}
 for name,md5 in FILES.items():
  p=root/name
  if not p.exists(): urllib.request.urlretrieve(ZENODO+name+'?download=1',p)
  got=hash_file(p,'md5'); sha=hash_file(p,'sha256')
  if got!=md5: raise RuntimeError(f'MD5 mismatch {name}: {got} != {md5}')
  rec[name]={'bytes':p.stat().st_size,'md5':got,'sha256':sha,'status':'PASS_CUSTODY'}
 return rec
def parse_events(config_path:Path):
 events=[]; inside=False
 for raw in config_path.read_text(encoding='utf-8').splitlines():
  s=raw.strip()
  if s=='leakages:':inside=True;continue
  if inside and s=='pressure_sensors:':break
  if not inside or not s.startswith('- p'):continue
  parts=[x.strip() for x in s[1:].strip().split(',')]
  if len(parts)!=6:continue
  link,start,end,diam,typ,peak=parts; fmt='%Y-%m-%d %H:%M'
  events.append(Event(link,datetime.strptime(start,fmt),datetime.strptime(end,fmt),float(diam),typ,datetime.strptime(peak,fmt)))
 return events
def load_year(root:Path,year:int):
 f=pd.read_csv(root/f'{year}_SCADA_Flows.csv',sep=';',decimal=',',parse_dates=['Timestamp']); p=pd.read_csv(root/f'{year}_SCADA_Pressures.csv',sep=';',decimal=',',parse_dates=['Timestamp'])
 if len(f)!=105120 or len(p)!=105120: raise RuntimeError(f'row count mismatch {year}: flows={len(f)}, pressures={len(p)}')
 if not f.Timestamp.equals(p.Timestamp): raise RuntimeError(f'timestamp mismatch {year}')
 if f.shape[1]-1!=3 or p.shape[1]-1!=33: raise RuntimeError(f'sensor schema mismatch {year}: {f.shape[1]-1} flows, {p.shape[1]-1} pressures')
 df=pd.concat([p,f.drop(columns='Timestamp')],axis=1)
 if df.isna().any().any(): raise RuntimeError(f'NaNs in {year} SCADA')
 return df,list(p.columns[1:]),list(f.columns[1:])
def robust_scale_fit_transform(train,test,cols):
 scaler=RobustScaler(); Xtr=scaler.fit_transform(train[cols].astype(float).to_numpy()); Xte=scaler.transform(test[cols].astype(float).to_numpy()); return scaler,Xtr,Xte
def gsde_scores(Xtr,Xte,ncomp=8,alpha=.01):
 pca=PCA(n_components=min(ncomp,Xtr.shape[1]),random_state=0).fit(Xtr)
 def diag(X):
  S=pca.transform(X); n=S.shape[1]; r=1.0+(np.arange(n)+1)/n; e=S*S; W=e.sum(axis=1); qbar=np.divide(e@r,W,out=np.ones_like(W),where=W>1e-12); m1=np.log(np.maximum(qbar,1e-12)); a=np.abs(X)+1e-12; total=a.sum(axis=1); pidx=np.arange(33); fidx=np.arange(33,36); q=np.linspace(1,2,X.shape[1]); m=a[:,pidx].sum(axis=1)/total; qi=(a[:,pidx]@q[pidx])/(a[:,pidx].sum(axis=1)+1e-12); qo=(a[:,fidx]@q[fidx])/(a[:,fidx].sum(axis=1)+1e-12); qb=(a@q)/(total+1e-12); m3=2*m*(1-m)*(qi-qo)/(qb+1e-12); m4=np.zeros(len(X)); u=S[:-1]; b=S[1:]-S[:-1]; u2=(u*u).sum(axis=1); dot=(b*u).sum(axis=1); proj=np.divide(dot,u2,out=np.zeros_like(dot),where=u2>1e-12)[:,None]*u; perp=b-proj; cur=2*(perp*perp).sum(axis=1); small=u2<=1e-12; cur[small]=2*(b[small]*b[small]).sum(axis=1); m4[1:]=cur; return np.column_stack([m1,m3,m4]),S
 Dtr,Str=diag(Xtr); Dte,Ste=diag(Xte); center=np.nanmedian(Dtr,axis=0); mad=np.nanmedian(np.abs(Dtr-center),axis=0); scale=1.4826*mad; std=np.nanstd(Dtr,axis=0); scale=np.where(scale>1e-12,scale,np.where(std>1e-12,std,1.0)); Z=np.abs((Dtr-center)/scale); ad=alpha/Dtr.shape[1]; th=np.nanquantile(Z,1-ad,axis=0); scoretr=np.nanmax(Z/(th+1e-12),axis=1); scorete=np.nanmax(np.abs((Dte-center)/scale)/(th+1e-12),axis=1); return scoretr,scorete,pca,Str,Ste
def baseline_scores(Xtr,Xte,pca,Str,Ste):
 out={}; out['B0_RAW_MAX_ROBUST_Z']=(np.max(np.abs(Xtr),axis=1),np.max(np.abs(Xte),axis=1)); Rtr=Xtr-pca.inverse_transform(Str); Rte=Xte-pca.inverse_transform(Ste); out['B1_PCA_SPE']=((Rtr*Rtr).sum(axis=1),(Rte*Rte).sum(axis=1)); ev=np.maximum(pca.explained_variance_,1e-12); out['B2_PCA_T2']=((Str*Str/ev).sum(axis=1),(Ste*Ste/ev).sum(axis=1)); Dtr=np.vstack([np.zeros((1,Xtr.shape[1])),np.diff(Xtr,axis=0)]); Dte=np.vstack([np.zeros((1,Xte.shape[1])),np.diff(Xte,axis=0)]); c=np.median(Dtr,axis=0); mad=np.median(np.abs(Dtr-c),axis=0); sc=1.4826*mad; st=np.std(Dtr,axis=0); sc=np.where(sc>1e-12,sc,np.where(st>1e-12,st,1.0)); out['B3_DELTA_MAX_ROBUST_Z']=(np.max(np.abs((Dtr-c)/sc),axis=1),np.max(np.abs((Dte-c)/sc),axis=1)); return out
def positive_mask(ts,events,horizon=HORIZON):
 t=np.asarray(ts,dtype='datetime64[ns]'); m=np.zeros(len(t),bool); h=np.timedelta64(horizon,'m')
 for e in events: s=np.datetime64(e.start); end=min(np.datetime64(e.end),s+h); m|=(t>=s)&(t<=end)
 return m
def episodes(ts,alarms,cooldown=COOLDOWN):
 t=np.asarray(ts,dtype='datetime64[ns]'); idx=np.flatnonzero(alarms)
 if not len(idx): return np.array([],dtype='datetime64[ns]')
 gap=np.timedelta64(cooldown,'m'); out=[t[idx[0]]]; last=t[idx[0]]
 for i in idx[1:]:
  cur=t[i]
  if cur-last>gap: out.append(cur)
  last=cur
 return np.asarray(out,dtype='datetime64[ns]')
def far30(ep,ts,pos):
 t=np.asarray(ts,dtype='datetime64[ns]'); pset=set(t[pos].astype('int64').tolist()); false=sum(int(x.astype('int64')) not in pset for x in ep); days=float((t[-1]-t[0])/np.timedelta64(1,'D'))+5/(24*60); return false/days*30,false
def calibrate(score,ts,events):
 pos=positive_mask(ts,events); qs=np.r_[np.linspace(.90,.99,46),np.linspace(.991,.999,45),np.linspace(.9991,.99999,60)]; best=None
 for q in qs:
  th=float(np.quantile(score,q)); ep=episodes(ts,score>th); far,_=far30(ep,ts,pos)
  if far<=TARGET_CAL_FAR_30D: best=(th,float(q),float(far),int(len(ep))); break
 if best is None: th=float(np.max(score)+np.finfo(float).eps); best=(th,1.0,0.0,0)
 return {'threshold':best[0],'quantile':best[1],'calibration_far_30d':best[2],'calibration_episode_count':best[3]}
def eval_method(score,threshold,ts,events,horizon=HORIZON):
 t=np.asarray(ts,dtype='datetime64[ns]'); ep=episodes(t,score>threshold); used=np.zeros(len(ep),bool); rows=[]; h=np.timedelta64(horizon,'m')
 for e in sorted(events,key=lambda z:z.start):
  s=np.datetime64(e.start); deadline=min(np.datetime64(e.end),s+h); cand=np.where((~used)&(ep>=s)&(ep<=deadline))[0]
  if len(cand): j=int(cand[0]); used[j]=True; det=ep[j]; delay=float((det-s)/np.timedelta64(1,'m')); peak=np.datetime64(e.peak); plead=float((peak-det)/np.timedelta64(1,'m')) if det<=peak else None; rows.append({'link_id':e.link_id,'leak_type':e.leak_type,'start':e.start.isoformat(' '),'detected':True,'detection_time':str(det),'delay_minutes':delay,'peak_lead_minutes':plead})
  else: rows.append({'link_id':e.link_id,'leak_type':e.leak_type,'start':e.start.isoformat(' '),'detected':False,'detection_time':None,'delay_minutes':None,'peak_lead_minutes':None})
 delays=[r['delay_minutes'] if r['detected'] else float(horizon) for r in rows]; raw=[r['delay_minutes'] for r in rows if r['detected']]; pos=positive_mask(t,events,horizon); far,false=far30(ep,t,pos); return {'total_events':len(rows),'detected_events':sum(r['detected'] for r in rows),'recall':sum(r['detected'] for r in rows)/max(1,len(rows)),'median_censored_delay_minutes':float(np.median(delays)),'median_detected_delay_minutes':float(np.median(raw)) if raw else None,'false_alarm_episodes_per_30d':float(far),'false_alarm_episode_count':int(false),'episode_count':int(len(ep)),'events':rows}
def sensitivity(score,threshold,ts,events): return {str(h):eval_method(score,threshold,ts,events,h)['recall'] for h in (1440,4320,10080)}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--raw-dir',default='raw'); ap.add_argument('--out-dir',default='artifacts'); a=ap.parse_args(); raw=Path(a.raw_dir); out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True); custody=download_and_verify(raw); events=parse_events(raw/'dataset_configuration.yaml'); ev18=[e for e in events if e.start.year==2018]; ev19=[e for e in events if e.start.year==2019]
 if len(ev18)!=14 or len(ev19)!=19: raise RuntimeError(f'event counts unexpected: {len(ev18)}, {len(ev19)}')
 d18,pcols,fcols=load_year(raw,2018); d19,p2,f2=load_year(raw,2019); assert pcols==p2 and fcols==f2; cols=pcols+fcols; _,X18,X19=robust_scale_fit_transform(d18,d19,cols); g18,g19,pca,S18,S19=gsde_scores(X18,X19); methods={'GSDE_M1_M3_M4':(g18,g19)}; methods.update(baseline_scores(X18,X19,pca,S18,S19)); results={}
 for name,(s18,s19) in methods.items(): cal=calibrate(s18,d18.Timestamp.to_numpy(),ev18); met=eval_method(s19,cal['threshold'],d19.Timestamp.to_numpy(),ev19); met['sensitivity_recall_by_horizon_minutes']=sensitivity(s19,cal['threshold'],d19.Timestamp.to_numpy(),ev19); results[name]={'calibration':cal,'evaluation':met}
 basenames=[x for x in results if x.startswith('B')]; best=min(basenames,key=lambda n:(results[n]['evaluation']['median_censored_delay_minutes'],-results[n]['evaluation']['recall'],results[n]['evaluation']['false_alarm_episodes_per_30d'])); G=results['GSDE_M1_M3_M4']['evaluation']; B=results[best]['evaluation']; checks={'delay_10pct_better':G['median_censored_delay_minutes']<=.9*B['median_censored_delay_minutes'],'far_no_worse':G['false_alarm_episodes_per_30d']<=B['false_alarm_episodes_per_30d']+1e-12,'recall_no_material_loss':G['recall']+0.05>=B['recall']}; verdict='PASS' if all(checks.values()) else 'FAIL'; report={'gate':'G4_3_B02_PREREGISTERED_EMPIRICAL_REPLAY_V1_2','contract':'B02_EVALUATION_CONTRACT_V1_2','custody':custody,'schema':{'rows_2018':len(d18),'rows_2019':len(d19),'pressure_sensors':len(pcols),'flow_sensors':len(fcols)},'protocol_correction':{'strict_leak_free_2018_days':7.5625,'strict_leak_free_2018_rows_5min':2178,'calibration_semantics':'HISTORICAL_2018_ALL_ROWS_NOT_HEALTHY_NOMINAL','new_onset_events_2019':len(ev19),'carry_in_events_excluded_from_primary_recall':4},'results':results,'best_baseline':best,'pass_checks':checks,'verdict':verdict,'truth_ceiling':{'official_battledim_localization_score_computed':False,'desalination_validation':False,'membrane_fouling_validation':False,'cross_domain_validation':False}}; (out/'B02_G4_3_RESULT.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); pd.DataFrame(results['GSDE_M1_M3_M4']['evaluation']['events']).to_csv(out/'B02_GSDE_EVENT_MATCHES.csv',index=False); print(json.dumps({'verdict':verdict,'best_baseline':best,'checks':checks,'gsde':G,'best':B,'custody':custody},indent=2))
if __name__=='__main__': main()
