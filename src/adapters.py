"""Turn each benchmark into a uniform list of tasks:
{id, src (canonical program), entry, kind, ...} where kind in {'he','asserts','plus'}"""
import json, gzip, ast
def humaneval():
    return [dict(id=t['task_id'],src=t['prompt']+t['canonical_solution'],entry=t['entry_point'],kind='he',test=t['test'])
            for t in map(json.loads,gzip.open('data/HumanEval.jsonl.gz','rt'))]
def mbpp():
    out=[]
    for t in json.load(open('data/mbpp_sanitized.json')):
        tests='\n'.join(t['test_imports']+t['test_list'])
        names=[n.func.id for n in ast.walk(ast.parse(tests)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        defs=[n.name for n in ast.parse(t['code']).body if isinstance(n,ast.FunctionDef)]
        entry=next((n for n in names if n in defs),defs[-1] if defs else None)
        out.append(dict(id=f"MBPP/{t['task_id']}",src=t['code'],entry=entry,kind='asserts',test=tests))
    return out
def plus(path,prefix):
    out=[]
    for t in map(json.loads,gzip.open(path,'rt')):
        out.append(dict(id=t['task_id'].replace('HumanEval',prefix).replace('Mbpp',prefix),src=t['prompt']+t['canonical_solution'],entry=t['entry_point'],kind='plus',
                        inputs=list(t['base_input'])+(t['plus_input'] if isinstance(t['plus_input'],list) else []),atol=t['atol']))
    return out
def pro(path,prefix):
    import pandas as pd
    out=[]
    for r in pd.read_parquet(path).itertuples():
        src=r.raw_problem+r.raw_solution+"\n\n"+r.new_problem+"\n"+r.new_solution
        import re; defs=re.findall(r"def\s+(\w+)\s*\(",r.new_problem); called=re.findall(r"assert\s+(?:not\s+)?\(?\s*(\w+)\(",r.test_code); entry=(defs[-1] if defs else None) or (called[0] if called else None)
        out.append(dict(id=f"{prefix}/{r.id}",src=src,entry=entry,kind='asserts',test=r.test_code))
    return out
BENCH={'humaneval':humaneval,'mbpp':mbpp,
 'humanevalplus':lambda:plus('data/HumanEvalPlus.jsonl.gz','HumanEvalPlus'),
 'mbppplus':lambda:plus('data/MbppPlus.jsonl.gz','MbppPlus'),
 'humanevalpro':lambda:pro('data/humaneval-pro.parquet','HumanEvalPro'),
 'mbpppro':lambda:pro('data/mbpp-pro.parquet','MbppPro')}
def evoeval(name):
    out=[]
    for t in map(json.loads,gzip.open(f'data/EvoEval_{name}.jsonl.gz','rt')):
        ins=[]
        for s in t['inputs']:
            try: ins.append(list(eval('('+s+',)',{'inf':float('inf'),'nan':float('nan')})))
            except Exception: pass
        out.append(dict(id=t['task_id'].replace('EvoEval',f'EvoEval_{name}'),src=t['prompt'].rstrip('\n')+'\n'+t['canonical_solution'],entry=t['entry_point'],kind='plus',inputs=ins,atol=0))
    return out
for _n in ['difficult','creative','subtle','combine','tool_use']: BENCH[f'evoeval_{_n}']=(lambda n=_n: evoeval(n))
def humanevalnext():
    import pandas as pd
    return [dict(id=r.task_id.replace('HumanEval','HumanEvalNext'),src=r.prompt+r.canonical_solution,entry=r.entry_point,kind='he',test=r.test) for r in pd.read_parquet('data/humanevalnext.parquet').itertuples()]
def bcblitepro():
    import re
    out=[]
    for r in json.load(open('data/bcb_lite_pro.json')):
        src=r['raw_problem']+r['raw_solution']+"\n\n"+r['new_problem']+"\n"+r['new_solution']
        defs=re.findall(r"def\s+(\w+)\s*\(",r['new_problem']); called=re.findall(r"assert\s+(?:not\s+)?\(?\s*(\w+)\(",r['test_code'])
        out.append(dict(id=f"BCBLitePro/{r['id'].split('/')[1]}",src=src,entry=(defs[-1] if defs else None) or (called[0] if called else None),kind='asserts',test=r['test_code']))
    return out
BENCH['humanevalnext']=humanevalnext; BENCH['bcblitepro']=bcblitepro
