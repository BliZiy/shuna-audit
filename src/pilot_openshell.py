"""HumanEval/0 exploit-probe pilot through the sandbox backend: python3 src/pilot_openshell.py [--sandbox=host]"""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import json, time, os
from adapters import BENCH; import exploit_probe as ep
t=[t for t in BENCH['humaneval']() if t.get('entry')][0]; rows=[]
for k in ('nop','always_equal','early_exit','os_exit'):
    s=time.time(); g=ep.grade(t,ep.stub(t['entry'],k)); rows.append(dict(id=t['id'],exploit=k,G1=g[0],G2=g[1],G3=g[2]))
    print(t['id'],k,dict(G1=g[0],G2=g[1],G3=g[2]),f'{time.time()-s:.2f}s',flush=True)
mode='openshell' if os.environ.get('SHUNA_IN_SANDBOX')=='1' else 'host'
os.makedirs('results/openshell_pilot',exist_ok=True); json.dump(rows,open(f'results/openshell_pilot/he0_{mode}.json','w'),indent=0)
