"""Bundle tasks + prompts + strong checks for the Kaggle end-to-end notebook."""
import json, gzip, sys, os, copy, pandas as pd
sys.path.insert(0,'src'); import adapters
from audit2 import timed, load, call
import resource; resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
OUT='../kaggle/shuna-audit-data'
F={b['id']:b for b in json.load(open('results/findings_v2.json'))['benchmarks']}
W="You are an exceptionally intelligent coding assistant that consistently delivers accurate and reliable responses to user instructions.\n@@ Instruction\n{instruction}\n\n@@ Response\n{response}"
HE_STOP=["\ndef ","\nclass ","\nif __name__","\nprint(","\nassert","\n```"]
def plusmap(path):
    return {int(t['task_id'].split('/')[1]):t for t in map(json.loads,gzip.open(path,'rt'))}
HP=plusmap('data/HumanEvalPlus.jsonl.gz'); MP=plusmap('data/MbppPlus.jsonl.gz')
HE={x['task_id']:x for x in map(json.loads,gzip.open('data/HumanEval.jsonl.gz','rt'))}
mb={t['task_id']:t for t in json.load(open('data/mbpp_sanitized.json'))}
pro={'humanevalpro':pd.read_parquet('data/humaneval-pro.parquet'),'mbpppro':pd.read_parquet('data/mbpp-pro.parquet')}
rows=[]; stats={}
for b in ['humaneval','mbpp','humanevalnext','humanevalpro','mbpppro']:
    conf={i['task_id']:i for i in F[b]['items'] if i['status']=='confirmed'}
    deb={d['task_id']:d for d in json.load(open(f'results/{b}/debate.json'))}
    n_strong=0
    for t in adapters.BENCH[b]():
        tid=t['id']; num=int(tid.split('/')[-1])
        if b=='humaneval': raw=HE[tid]
        r=dict(bench=b,task_id=tid,ref_src=t['src'],entry=t['entry'],test_kind=t['kind'],test=t['test'],confirmed=tid in conf,strong=[])
        if b=='humaneval':
            r.update(prompt=raw['prompt'],prefix=raw['prompt'],stop=HE_STOP)
        elif b=='humanevalnext':
            p=pd.read_parquet('data/humanevalnext.parquet').set_index('task_id').loc[tid.replace('HumanEvalNext','HumanEval'),'prompt']
            r.update(prompt=p,prefix=p,stop=HE_STOP)
        elif b=='mbpp':
            m=mb[num]; p=f'"""\n{m["prompt"]}\n{m["test_list"][0]}\n"""\n'
            r.update(prompt=p,prefix='',stop=['\n"""','\nassert','\nprint(','\nif __name__','\n```'])
        else:
            x=pro[b].set_index('id').loc[str(num) if pro[b]['id'].dtype==object else num]
            p1,p2=x.raw_problem.strip(),x.new_problem.strip()
            ins=f"Write a solution of python file to the following problems, the solution of the second problem requires single or multiple calls to the first solution.\n```python\n{p1}\n{p2}\n```"
            pre=f"```python\n{p1}\n"
            r.update(prompt=W.format(instruction=ins,response=pre),prefix=p1+"\n",stop=["```","\n@@"])
        if tid in conf:
            g=load(t['src']); ins=[]
            w=(deb.get(tid) or {}).get('witness')
            if w:
                try: ins.append(eval(w['input']))
                except Exception: pass   # witness repr was truncated at 300 chars
            if b in('humaneval','mbpp'):
                P=(HP if b=='humaneval' else MP).get(num)
                if P: ins+= [tuple(a) for a in (list(P['base_input'])+(P['plus_input'] if isinstance(P['plus_input'],list) else []))][:300]
            for a in ins:
                a=tuple(a) if isinstance(a,(list,tuple)) else (a,)
                st,v=call(g,t['entry'],a,2)
                ar=repr(a)
                if st=='ok' and len(ar)<20000 and len(v)<20000:
                    try: eval(ar); r['strong'].append([ar,v])
                    except Exception: pass
            n_strong+=bool(r['strong'])
        rows.append(r)
    stats[b]=dict(tasks=sum(x['bench']==b for x in rows),confirmed=len(conf),with_strong_check=n_strong)
with open(f'{OUT}/tasks.jsonl','w') as f:
    for r in rows: f.write(json.dumps(r)+"\n")
import shutil; shutil.copy('results/findings_v2.json',f'{OUT}/findings_v2.json')
json.dump(stats,open(f'{OUT}/stats.json','w'),indent=1); print(stats)
