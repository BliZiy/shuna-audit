"""End-to-end: real model output on HE-Pro (Qwen2.5-Coder-1.5B-Instruct q4, greedy, authors' prompt). Pro pass? helper correct?"""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import json,gzip,sys,pandas as pd
sys.path.insert(0,'src'); from audit2 import timed,call,close
import resource; resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
pro=pd.read_parquet('data/humaneval-pro.parquet')
plus={int(t['task_id'].split('/')[1]):t for t in map(json.loads,gzip.open('data/HumanEvalPlus.jsonl.gz','rt'))}
he={int(t['task_id'].split('/')[1]):t for t in map(json.loads,gzip.open('data/HumanEval.jsonl.gz','rt'))}
rows=[]
for l in open('results/gen_humanevalpro_q15.jsonl'):
    x=json.loads(l); i=x['id']; code=x['code']; r=pro.iloc[i]
    pp=timed(lambda: exec(code+"\n"+r.test_code,{'__name__':'x'}),10)[0]=='ok'
    st,g=timed(lambda:(lambda d:(exec(code,d),d)[1])({'__name__':'x'}),5); P=plus[i]; hp=False; ho=False
    if st=='ok' and P['entry_point'] in g:
        cg={}; exec(P['prompt']+P['canonical_solution'],cg); hp=True
        for a in list(P['base_input'])+(P['plus_input'] if isinstance(P['plus_input'],list) else []):
            rs,rv=call(cg,P['entry_point'],a,2)
            if rs!='ok': continue
            ms,mv=call(g,P['entry_point'],a,2)
            if ms!='ok' or not close(mv,rv,P['atol']): hp=False; break
        t=he[i]; ho=timed(lambda:(exec(t['test'],g),g['check'](g[t['entry_point']])),10)[0]=='ok'
    rows.append({'id':i,'pro_pass':pp,'helper_ok_plus':hp,'helper_ok_original':ho})
n=len(rows); pp=[r for r in rows if r['pro_pass']]
print('tasks',n,'pro passes',len(pp),'| of those, helper fails HumanEval+:',sum(not r['helper_ok_plus'] for r in pp),'| fails original HumanEval:',sum(not r['helper_ok_original'] for r in pp), [r['id'] for r in pp if not r['helper_ok_plus']])
json.dump(rows,open('results/endtoend_qwen15_humanevalpro.json','w'))
