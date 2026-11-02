"""Lower bound: of HE-Pro passes, how many use a helper that FAILS THE ORIGINAL HumanEval tests (no EvalPlus judgment involved)?"""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import json,gzip,zipfile,sys,os
sys.path.insert(0,'src'); from audit2 import timed
import resource; resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
he={int(t['task_id'].split('/')[1]):t for t in map(json.loads,gzip.open('data/HumanEval.jsonl.gz','rt'))}
R=json.load(open('results/impact_humanevalpro.json')); out=[]; LB=UB=TOT=0; per_task={}
for m in R:
    if 'rows' not in m: continue
    z=zipfile.ZipFile(f"data/evoeval_samples/{m['model']}.zip"); lb=[]
    for x in m['rows']:
        if not x['pro_pass']: continue
        TOT+=1
        if x['helper_correct_plus']: continue
        UB+=1; t=he[x['task']]; h=z.read(f"{m['model']}/humaneval/HumanEval_{x['task']}/0.py").decode()
        ok=timed(lambda: (lambda g:(exec(h,g),exec(t['test'],g),g['check'](g[t['entry_point']])))({'__name__':'x'}),10)[0]=='ok'
        if not ok: lb.append(x['task']); per_task[x['task']]=per_task.get(x['task'],0)+1
    LB+=len(lb); out.append({'model':m['model'],'fails_original_humaneval_but_passes_pro':lb})
json.dump({'per_model':out,'per_task':per_task,'total_pro_passes':TOT,'upper_bound_evalplus':UB,'lower_bound_original_tests':LB},open('results/impact_humanevalpro_bounds.json','w'),indent=1)
print('models',len(out),'Pro passes',TOT,'| helper wrong per HumanEval+ (upper):',UB,f'{100*UB/TOT:.1f}%','| helper fails ORIGINAL HumanEval tests (lower):',LB,f'{100*LB/TOT:.1f}%')
print('top tasks',sorted(per_task.items(),key=lambda kv:-kv[1])[:15])
