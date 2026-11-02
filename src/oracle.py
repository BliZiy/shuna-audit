"""Independent oracle: re-check each wrong-but-passing mutant against EvalPlus' validated inputs
(contract-respecting, expected = EvalPlus canonical) for the ORIGINAL function.
If the mutant's version of that function disagrees with EvalPlus on any input, the flaw is
'verified (EvalPlus oracle)'. python3 src/oracle.py <bench>"""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import json, gzip, sys, os, subprocess, concurrent.futures as cf
sys.path.insert(0,os.path.dirname(__file__))
from audit2 import load, call, close, timed
PLUS={'he':'data/HumanEvalPlus.jsonl.gz','mbpp':'data/MbppPlus.jsonl.gz'}
def plus_map(kind):
    m={}
    for t in map(json.loads,gzip.open(PLUS[kind],'rt')): m[t['task_id'].split('/')[1]]=t
    return m
def key_for(bench,task_id,entry_name_map):
    n=task_id.split('/')[1]
    if bench in('humaneval','humanevalpro'): return 'he',n
    if bench=='mbpp': return 'mbpp',n
    if bench=='mbpppro': return 'mbpp',entry_name_map.get(int(n))
def check(bench,idx):
    import resource; resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    R=json.load(open(f'results/{bench}/raw.json'))['results'][idx]
    out={'task_id':R['task_id'],'oracle':None,'per_witness':[]}
    if not R['witnesses']: return out
    kind,k=key_for(bench,R['task_id'],MBPP_PRO_MAP if bench=='mbpppro' else {})
    P=plus_map(kind).get(k) if k else None
    if not P: out['oracle']='no matching EvalPlus task'; return out
    out['oracle']=P['task_id']
    g=load(P['prompt']+P['canonical_solution']); inputs=list(P['base_input'])+(P['plus_input'] if isinstance(P['plus_input'],list) else [])
    ref=[call(g,P['entry_point'],a,2) for a in inputs]
    for w in R['witnesses']:
        res={'mutation':w['mutation'],'oracle_disagrees':False}
        st,mg=timed(lambda:load(w['mutant_src']),3)
        if st!='ok' or P['entry_point'] not in mg: res['note']='helper not found in mutant'; out['per_witness'].append(res); continue
        for a,(rs,rv) in zip(inputs,ref):
            if rs!='ok': continue
            ms,mv=call(mg,P['entry_point'],a,2)
            if ms!='ok' or not close(mv,rv,P['atol']):
                res.update(oracle_disagrees=True,oracle_input=repr(a)[:300],oracle_expected=rv[:200],mutant_helper_output=(mv if ms=='ok' else ms)[:200]); break
        out['per_witness'].append(res)
    return out
def build_mbpppro_map():
    import pandas as pd, re
    plus={}
    for t in map(json.loads,gzip.open(PLUS['mbpp'],'rt')): plus.setdefault(t['entry_point'],t['task_id'].split('/')[1])
    m={}
    for r in pd.read_parquet('data/mbpp-pro.parquet').itertuples():
        names=re.findall(r"def\s+(\w+)\s*\(",r.raw_problem+r.raw_solution)
        for nm in names:
            if nm in plus: m[int(r.id)]=plus[nm]; break
    return m
MBPP_PRO_MAP={}
if __name__=='__main__':
    if sys.argv[1]=='--one':
        b,i=sys.argv[2],int(sys.argv[3])
        if b=='mbpppro': MBPP_PRO_MAP=json.load(open('results/mbpppro/plusmap.json'),object_hook=lambda d:{int(k):v for k,v in d.items()})
        json.dump(check(b,i),open(f'results/{b}/oracle/{i}.json','w')); sys.exit()
    b=sys.argv[1]; os.makedirs(f'results/{b}/oracle',exist_ok=True)
    if b=='mbpppro': json.dump(build_mbpppro_map(),open('results/mbpppro/plusmap.json','w'))
    R=json.load(open(f'results/{b}/raw.json'))['results']
    idx=[i for i,r in enumerate(R) if r['witnesses']]
    def one(i):
        f=f'results/{b}/oracle/{i}.json'
        try: subprocess.run([sys.executable,__file__,'--one',b,str(i)],timeout=300,capture_output=True)
        except subprocess.TimeoutExpired: pass
        return json.load(open(f)) if os.path.exists(f) else {'task_id':R[i]['task_id'],'oracle':'timeout'}
    with cf.ThreadPoolExecutor(3) as ex: O=list(ex.map(one,idx))
    json.dump(O,open(f'results/{b}/oracle.json','w'),indent=1)
    v=[o for o in O if any(w.get('oracle_disagrees') for w in o.get('per_witness',[]))]
    print(b,'flagged',len(O),'oracle-verified',len(v),'no-oracle',sum(1 for o in O if not str(o.get('oracle','')).startswith(('HumanEval','Mbpp'))))
