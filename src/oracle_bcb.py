"""Oracle for BigCodeBench-Lite Pro: run the ORIGINAL BigCodeBench unittest suite against the wrong program's base function."""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import json, sys, os, io, unittest, contextlib, pandas as pd
sys.path.insert(0,'src'); from audit2 import timed
import resource; resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
bcb={r.task_id:r for r in pd.read_parquet('data/bcb_v014.parquet').itertuples()}
R=json.load(open('results/bcblitepro/raw.json'))['results']; pro={f"BCBLitePro/{r['id'].split('/')[1]}":r for r in json.load(open('data/bcb_lite_pro.json'))}
def runs(src,test):
    def go():
        g={'__name__':'bcb'}; exec(src,g); exec(test,g)
        s=unittest.defaultTestLoader.loadTestsFromTestCase(g['TestCases']); res=unittest.TestResult(); s.run(res)
        return len(res.failures)+len(res.errors), res.testsRun
    return timed(go,60)
out=[]
for r in R:
    if not r['witnesses']: continue
    p=pro[r['task_id']]; B=bcb[p['id']]; ref=runs(p['raw_problem']+p['raw_solution'],B.test)
    o={'task_id':r['task_id'],'oracle':p['id'],'reference_on_original_tests':str(ref),'per_witness':[]}
    for w in r['witnesses']:
        st=runs(w['mutant_src'],B.test)
        bad=(st[0]=='ok' and st[1][0]>0 and ref[0]=='ok' and ref[1][0]==0)
        o['per_witness'].append({'mutation':w['mutation'],'oracle_disagrees':bad,'oracle_input':'original BigCodeBench unit tests' if bad else None,'oracle_expected':'pass','mutant_helper_output':str(st)})
    out.append(o); print(r['task_id'],'ref',ref,'wrong-helper caught by original tests:',sum(x['oracle_disagrees'] for x in o['per_witness']),'/',len(o['per_witness']))
json.dump(out,open('results/bcblitepro/oracle.json','w'),indent=1)
