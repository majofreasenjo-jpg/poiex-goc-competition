from __future__ import annotations
import json, math, os, sys, time
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import requests

ENDPOINT = 'https://turbulence.pha.jhu.edu/service/turbulence.asmx'
SOAP_ACTION = 'http://turbulence.pha.jhu.edu/GetData_Python'
NS = 'http://turbulence.pha.jhu.edu/'
DATASET = 'mhd1024'
TIME = 1.0
N = 1024
DX = 2.0 * math.pi / N
ANCHORS = [(128,256,384),(512,640,768),(800,300,700)]
TEST_TOKEN = 'edu.jhu.pha.turbulence.testing-201406'
MAX_ABS_TOL = 2.0e-2
REL_RMS_TOL = 1.0e-2


def soap_query(function_name: str, points: list[tuple[float,float,float]], spatial: str, components: int, token: str) -> np.ndarray:
    point_xml = ''.join(
        '<ArrayOfFloat>' + ''.join(f'<float>{v:.17g}</float>' for v in p) + '</ArrayOfFloat>'
        for p in points
    )
    body = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetData_Python xmlns="{NS}">
      <function_name>{function_name}</function_name>
      <authToken>{token}</authToken>
      <dataset>{DATASET}</dataset>
      <time>{TIME:.17g}</time>
      <spatialInterpolation>{spatial}</spatialInterpolation>
      <temporalInterpolation>None</temporalInterpolation>
      <points>{point_xml}</points>
    </GetData_Python>
  </soap:Body>
</soap:Envelope>'''
    last = None
    for attempt in range(1, 5):
        try:
            r = requests.post(
                ENDPOINT,
                data=body.encode('utf-8'),
                headers={'Content-Type':'text/xml; charset=utf-8','SOAPAction':f'"{SOAP_ACTION}"','User-Agent':'GMATIVE-GSDE-G4.10B-custody-probe'},
                timeout=120,
            )
            r.raise_for_status()
            root = ET.fromstring(r.content)
            fault = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
            if fault is not None:
                raise RuntimeError('SOAP fault: ' + ' '.join(t.strip() for t in fault.itertext() if t.strip()))
            vals = [float(x.text) for x in root.findall(f'.//{{{NS}}}GetData_PythonResult/{{{NS}}}float')]
            if len(vals) != len(points) * components:
                # Some ASMX serializers emit result floats without the service namespace.
                vals = [float(x.text) for x in root.findall('.//GetData_PythonResult/float')]
            if len(vals) != len(points) * components:
                raise RuntimeError(f'{function_name}: expected {len(points)*components} floats, got {len(vals)}')
            arr = np.asarray(vals, dtype=np.float64).reshape(len(points), components)
            if not np.isfinite(arr).all():
                raise RuntimeError(f'{function_name}: non-finite values')
            return arr
        except Exception as e:
            last = repr(e)
            print(f'RETRY {function_name} attempt={attempt} error={last}', flush=True)
            time.sleep(min(3*attempt, 9))
    raise RuntimeError(f'{function_name} failed after retries: {last}')


def coord(idx: tuple[int,int,int]) -> tuple[float,float,float]:
    return tuple(i * DX for i in idx)


def stencil_catalog():
    entries=[]
    seen={}
    for ai,a in enumerate(ANCHORS):
        def add(tag, idx):
            if idx not in seen:
                seen[idx]=len(entries); entries.append({'idx':idx,'coord':coord(idx),'tags':[tag]})
            else:
                entries[seen[idx]]['tags'].append(tag)
        add(f'a{ai}:c', a)
        for axis in range(3):
            for off in (-2,-1,1,2):
                q=list(a); q[axis]=(q[axis]+off)%N; q=tuple(q)
                add(f'a{ai}:d{axis}:{off}', q)
    return entries


def fd4_from_catalog(values_by_idx: dict[tuple[int,int,int],np.ndarray], a: tuple[int,int,int]) -> np.ndarray:
    # rows = vector component, cols = spatial derivative x/y/z
    g=np.zeros((3,3),dtype=np.float64)
    for axis in range(3):
        def v(off):
            q=list(a); q[axis]=(q[axis]+off)%N; return values_by_idx[tuple(q)]
        g[:,axis] = (-v(2) + 8*v(1) - 8*v(-1) + v(-2)) / (12.0*DX)
    return g


def unpack_service_grad(row: np.ndarray) -> np.ndarray:
    return row.reshape(3,3)


def rel_rms(a,b):
    num=float(np.sqrt(np.mean((a-b)**2)))
    den=max(float(np.sqrt(np.mean(b**2))),1e-12)
    return num/den


def main(out_dir: str):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    token=os.environ.get('JHTDB_TOKEN',TEST_TOKEN)
    catalog=stencil_catalog()
    pts=[e['coord'] for e in catalog]
    print(f'Frozen dataset={DATASET} time={TIME} dx={DX:.17g} anchors={ANCHORS} unique_points={len(pts)}')

    u_all=soap_query('GetVelocity',pts,'None',3,token)
    b_all=soap_query('GetMagneticField',pts,'None',3,token)
    anchor_pts=[coord(a) for a in ANCHORS]
    gu_srv_raw=soap_query('GetVelocityGradient',anchor_pts,'None_Fd4',9,token)
    gb_srv_raw=soap_query('GetMagneticFieldGradient',anchor_pts,'None_Fd4',9,token)

    u_by={e['idx']:u_all[i] for i,e in enumerate(catalog)}
    b_by={e['idx']:b_all[i] for i,e in enumerate(catalog)}
    rows=[]; operator_rows=[]
    all_u_abs=[]; all_b_abs=[]; all_u_ref=[]; all_b_ref=[]
    for ai,a in enumerate(ANCHORS):
        gu_loc=fd4_from_catalog(u_by,a); gb_loc=fd4_from_catalog(b_by,a)
        gu_srv=unpack_service_grad(gu_srv_raw[ai]); gb_srv=unpack_service_grad(gb_srv_raw[ai])
        du=gu_srv-gu_loc; db=gb_srv-gb_loc
        all_u_abs.extend(np.abs(du).ravel()); all_b_abs.extend(np.abs(db).ravel())
        all_u_ref.extend(gu_srv.ravel()); all_b_ref.extend(gb_srv.ravel())
        uc=u_by[a]; bc=b_by[a]
        q_bu=gu_srv @ bc
        q_ub=gb_srv @ uc
        q_ind=q_bu-q_ub
        operator_rows.append({
            'anchor':ai,'ix':a[0],'iy':a[1],'iz':a[2],
            'u_norm':float(np.linalg.norm(uc)),'B_norm':float(np.linalg.norm(bc)),
            'div_u_service':float(np.trace(gu_srv)),'div_B_service':float(np.trace(gb_srv)),
            'Q_Bu_norm':float(np.linalg.norm(q_bu)),'Q_uB_norm':float(np.linalg.norm(q_ub)),
            'Q_induction_norm':float(np.linalg.norm(q_ind)),
            'Q_induction_x':float(q_ind[0]),'Q_induction_y':float(q_ind[1]),'Q_induction_z':float(q_ind[2]),
        })
        for c in range(3):
            for d in range(3):
                rows.append({'anchor':ai,'field':'u','component':c,'derivative_axis':d,'service_fd4':gu_srv[c,d],'local_fd4':gu_loc[c,d],'abs_error':abs(du[c,d])})
                rows.append({'anchor':ai,'field':'B','component':c,'derivative_axis':d,'service_fd4':gb_srv[c,d],'local_fd4':gb_loc[c,d],'abs_error':abs(db[c,d])})

    comp=pd.DataFrame(rows); comp.to_csv(out/'G410B_GRADIENT_CUSTODY_COMPARISON.csv',index=False)
    op=pd.DataFrame(operator_rows); op.to_csv(out/'G410B_TARGET_NATIVE_OPERATOR_PROBE.csv',index=False)
    rawrows=[]
    for i,e in enumerate(catalog):
        rawrows.append({'ix':e['idx'][0],'iy':e['idx'][1],'iz':e['idx'][2],'x':e['coord'][0],'y':e['coord'][1],'z':e['coord'][2],
                        'tags':'|'.join(e['tags']),'ux':u_all[i,0],'uy':u_all[i,1],'uz':u_all[i,2],
                        'Bx':b_all[i,0],'By':b_all[i,1],'Bz':b_all[i,2]})
    pd.DataFrame(rawrows).to_csv(out/'G410B_FROZEN_POINT_FIELD_VALUES.csv',index=False)

    u_max=float(np.max(all_u_abs)); b_max=float(np.max(all_b_abs))
    u_srv=np.asarray(all_u_ref); b_srv=np.asarray(all_b_ref)
    # Rebuild local arrays in the same row order from comparison table for relative RMS.
    u_cmp=comp[comp.field=='u']; b_cmp=comp[comp.field=='B']
    u_rel=rel_rms(u_cmp.service_fd4.to_numpy(),u_cmp.local_fd4.to_numpy())
    b_rel=rel_rms(b_cmp.service_fd4.to_numpy(),b_cmp.local_fd4.to_numpy())
    nondeg=int((op.Q_induction_norm>1e-8).sum())
    gradient_pass=(u_max<=MAX_ABS_TOL and b_max<=MAX_ABS_TOL and u_rel<=REL_RMS_TOL and b_rel<=REL_RMS_TOL)
    operator_pass=nondeg>=2 and np.isfinite(op.select_dtypes(include=[np.number]).to_numpy()).all()
    status='PASS_CUSTODY_NO_SCORING' if gradient_pass and operator_pass else 'HOLD_DERIVATIVE_OR_OPERATOR_CUSTODY'
    receipt={
        'status':status,'dataset':DATASET,'time':TIME,'grid_n':N,'dx':DX,'anchors':ANCHORS,
        'unique_field_query_points':len(pts),'public_testing_token_used':token==TEST_TOKEN,
        'velocity_gradient_max_abs_error':u_max,'magnetic_gradient_max_abs_error':b_max,
        'velocity_gradient_relative_rms_error':u_rel,'magnetic_gradient_relative_rms_error':b_rel,
        'max_abs_tolerance':MAX_ABS_TOL,'relative_rms_tolerance':REL_RMS_TOL,
        'nondegenerate_Q_induction_anchors':nondeg,
        'max_abs_div_u_service':float(np.max(np.abs(op.div_u_service))),
        'max_abs_div_B_service':float(np.max(np.abs(op.div_B_service))),
        'scoring_performed':False,'future_time_access':False,'random_cv_used':False,
        'sensor_only_proxy_used':False,'scan_holdout_accessed':False,
        'empirical_credit':0,
        'claim_ceiling':'Data/derivative custody and target-native operator reconstructibility only; no predictive scoring; no incremental-value claim.'
    }
    (out/'G410B_CUSTODY_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    lines=[
        f'G4_10B_MHD_CUSTODY_PROBE={status}',
        f'VELOCITY_GRADIENT_CUSTODY={"PASS" if u_max<=MAX_ABS_TOL and u_rel<=REL_RMS_TOL else "FAIL"}',
        f'MAGNETIC_GRADIENT_CUSTODY={"PASS" if b_max<=MAX_ABS_TOL and b_rel<=REL_RMS_TOL else "FAIL"}',
        f'Q_INDUCTION_TARGET_NATIVE_RECONSTRUCTIBLE={"TRUE" if operator_pass else "FALSE"}',
        'SCORING_PERFORMED=FALSE','FUTURE_TIME_ACCESS=FALSE','RANDOM_CV_USED=FALSE','SENSOR_ONLY_PROXY_USED=FALSE','SCAN_HOLDOUT_ACCESSED=FALSE','EMPIRICAL_CREDIT=0'
    ]
    (out/'G410B_ADJUDICATION.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2)); print(op.to_string(index=False)); print('\n'.join(lines))
    if status!='PASS_CUSTODY_NO_SCORING':
        raise SystemExit(7)

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: g410b_mhd_custody_probe.py OUT_DIR')
    main(sys.argv[1])
