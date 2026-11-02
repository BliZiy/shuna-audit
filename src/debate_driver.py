"""Run debate per task in its own process with a hard wall-clock cap; merge into debate.json."""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import json,os,subprocess,sys
b=sys.argv[1]; cap=int(sys.argv[2]) if len(sys.argv)>2 else 120
raw=json.load(open(f'results/{b}/raw.json'))['results']; os.makedirs(f'results/{b}/debate_parts',exist_ok=True); out=[]
for r in raw:
    if not r['witnesses']: continue
    t=r['task_id']; f=f"results/{b}/debate_parts/{t.split('/')[1]}.json"
    if not os.path.exists(f):
        try: subprocess.run([sys.executable,'-W','ignore','src/debate.py',b],env={**os.environ,'ONLY':t,'OUT':f},timeout=cap,capture_output=True)
        except subprocess.TimeoutExpired: json.dump([dict(task_id=t,verdict='rejected',reason=f'debate timed out after {cap}s (not confirmed)',witness=None,oracle_input=None)],open(f,'w'))
    part=json.load(open(f)) if os.path.exists(f) else [dict(task_id=t,verdict='rejected',reason='debate crashed',witness=None,oracle_input=None)]
    out+=part; print(t,part[0]['verdict'] if part else '-',flush=True)
json.dump(out,open(f'results/{b}/debate.json','w'),indent=1)
c=lambda v:sum(x['verdict']==v for x in out); print(b,'flagged',len(out),'confirmed',c('confirmed'),'helper-only',c('helper-only'),'rejected',c('rejected'))
