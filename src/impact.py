"""Score-impact simulation for HumanEval Pro using REAL model code released by EvoEval (51 models, greedy).
For each model & task: program = model's own HumanEval solution (the helper) + HE-Pro canonical composite.
Q: does HE-Pro's official test accept it while the helper is wrong per EvalPlus HumanEval+ inputs?
python3 src/impact.py   (worker: --model <zip>)"""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import sys, os, json, gzip, zipfile, io, contextlib, signal, copy, subprocess, concurrent.futures as cf
sys.path.insert(0,os.path.dirname(__file__))
from audit2 import call, close, timed
def worker(zp):
    import pandas as pd, resource; sys.setrecursionlimit(3000)
    pro=pd.read_parquet('data/humaneval-pro.parquet'); plus={int(t['task_id'].split('/')[1]):t for t in map(json.loads,gzip.open('data/HumanEvalPlus.jsonl.gz','rt'))}
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30)); z=zipfile.ZipFile(zp); root=z.namelist()[0].split('/')[0]; out=[]
    for i in range(164):
        try: helper=z.read(f'{root}/humaneval/HumanEval_{i}/0.py').decode()
        except KeyError: continue
        r=pro.iloc[i]; P=plus[i]
        prog=helper+"\n\n"+r.new_problem+"\n"+r.new_solution
        pro_pass=timed(lambda: exec(prog+"\n"+r.test_code,{'__name__':'x'}),10)[0]=='ok'
        st,g=timed(lambda: (lambda d:(exec(helper,d),d)[1])({'__name__':'x'}),5)
        hp=None
        if st=='ok' and P['entry_point'] in g:
            cg={}; exec(P['prompt']+P['canonical_solution'],cg); hp=True
            ins=list(P['base_input'])+(P['plus_input'] if isinstance(P['plus_input'],list) else [])
            for a in ins:
                rs,rv=call(cg,P['entry_point'],a,2)
                if rs!='ok': continue
                ms,mv=call(g,P['entry_point'],a,2)
                if ms!='ok' or not close(mv,rv,P['atol']): hp=False; break
        else: hp=False
        out.append({'task':i,'pro_pass':pro_pass,'helper_correct_plus':hp})
    return {'model':root,'rows':out}
if __name__=='__main__':
    if sys.argv[1:2]==['--model']:
        r=worker(sys.argv[2]); json.dump(r,open(sys.argv[3],'w')); sys.exit()
    zs=sorted(f'data/evoeval_samples/{f}' for f in os.listdir('data/evoeval_samples') if f.endswith('.zip'))
    def run(zp):
        try: f='/tmp/imp_'+os.path.basename(zp)+'.json'; p=subprocess.run([sys.executable,__file__,'--model',zp,f],capture_output=True,text=True,timeout=1500); return json.load(open(f))
        except Exception as e: return {'model':zp,'error':str(e)[:200]}
    with cf.ThreadPoolExecutor(4) as ex: R=list(ex.map(run,zs))
    json.dump(R,open('results/impact_humanevalpro.json','w'))
    tot_fa=tot_pass=0
    for m in R:
        if 'rows' not in m: print(m['model'],'ERR',m.get('error')); continue
        rows=m['rows']; pp=[x for x in rows if x['pro_pass']]; fa=[x for x in pp if not x['helper_correct_plus']]
        tot_fa+=len(fa); tot_pass+=len(pp)
        print(f"{m['model']:40s} pro_pass {len(pp):3d}  accepted_with_wrong_helper {len(fa):3d}  tasks {[x['task'] for x in fa][:12]}")
    print('TOTAL accepted-with-wrong-helper',tot_fa,'of',tot_pass,'Pro passes',f'({100*tot_fa/max(tot_pass,1):.1f}%)')
