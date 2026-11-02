"""Shuna Audit v0: weak-test detection for HumanEval via mutation + differential fuzzing.
Reproduce: python3 src/audit.py   (no network/API needed once data/HumanEval.jsonl.gz exists)"""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import ast, copy, gzip, json, random, signal, sys, hashlib, difflib, multiprocessing as mp, io, contextlib

DATA = "data/HumanEval.jsonl.gz"
MAX_MUTANTS = 80; FUZZ_PER_SEED = 30; SEED = 1337

class TO(Exception): pass
def _alarm(*a): raise TO()

# ---------- mutation ----------
CMP = {ast.Lt:[ast.LtE,ast.Gt], ast.LtE:[ast.Lt,ast.GtE], ast.Gt:[ast.GtE,ast.Lt], ast.GtE:[ast.Gt,ast.LtE],
       ast.Eq:[ast.NotEq], ast.NotEq:[ast.Eq]}
BIN = {ast.Add:[ast.Sub], ast.Sub:[ast.Add], ast.Mult:[ast.FloorDiv], ast.FloorDiv:[ast.Mult], ast.Mod:[ast.FloorDiv]}
def mutation_sites(tree):
    sites=[]
    for i,n in enumerate(ast.walk(tree)):
        if isinstance(n,ast.Compare):
            for j,op in enumerate(n.ops):
                for r in CMP.get(type(op),[]): sites.append((i,'cmp',j,r))
        elif isinstance(n,ast.BinOp) and type(n.op) in BIN:
            for r in BIN[type(n.op)]: sites.append((i,'bin',0,r))
        elif isinstance(n,ast.BoolOp): sites.append((i,'bool',0,ast.Or if isinstance(n.op,ast.And) else ast.And))
        elif isinstance(n,ast.Constant) and type(n.value) is int: sites+= [(i,'const',0,1),(i,'const',0,-1)]
        elif isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.Not): sites.append((i,'notdel',0,None))
        elif isinstance(n,ast.Return) and n.value is not None: pass
    return sites
def apply(tree,site):
    t=copy.deepcopy(tree); i,kind,j,r=site
    for k,n in enumerate(ast.walk(t)):
        if k!=i: continue
        if kind=='cmp': n.ops[j]=r()
        elif kind=='bin': n.op=r()
        elif kind=='bool': n.op=r()
        elif kind=='const': n.value=n.value+r
        elif kind=='notdel': n.op=ast.UAdd()  # +x keeps truthiness? no: replace with identity below
        break
    if kind=='notdel':
        class F(ast.NodeTransformer):
            def visit_UnaryOp(s,n):
                s.generic_visit(n); return n.operand if isinstance(n.op,ast.UAdd) else n
        t=F().visit(t)
    ast.fix_missing_locations(t); return ast.unparse(t)
def describe(site): i,k,j,r=site; return f"{k}:{getattr(r,'__name__',r)}@node{i}"

# ---------- input harvesting / fuzz ----------
def harvest_args(test_src):
    out=[]
    for n in ast.walk(ast.parse(test_src)):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='candidate' and not n.keywords:
            try: out.append(tuple(ast.literal_eval(a) for a in n.args))
            except Exception: pass
    return out
def perturb(v,rng,d=0):
    if isinstance(v,bool): return rng.choice([True,False])
    if isinstance(v,int): return v+rng.choice([-2,-1,0,1,2,rng.randint(-20,20)])
    if isinstance(v,float): return round(v+rng.uniform(-3,3),2)
    if isinstance(v,str):
        s=list(v); op=rng.random()
        if s and op<.3: s.pop(rng.randrange(len(s)))
        elif s and op<.6: rng.shuffle(s)
        elif op<.8: s.insert(rng.randint(0,len(s)), rng.choice(v or 'ab1 '))
        return ''.join(s)
    if isinstance(v,list) and d<3:
        s=[perturb(x,rng,d+1) for x in v]; op=rng.random()
        if s and op<.25: s.pop(rng.randrange(len(s)))
        elif s and op<.5: s.append(copy.deepcopy(rng.choice(s)))
        elif op<.7: rng.shuffle(s)
        return s
    if isinstance(v,tuple): return tuple(perturb(list(v),rng,d))
    return v

def run_quiet(fn,args,t=1):
    signal.signal(signal.SIGALRM,_alarm); signal.setitimer(signal.ITIMER_REAL,t)
    try:
        with contextlib.redirect_stdout(io.StringIO()): return ('ok',repr(fn(*copy.deepcopy(args))))
    except TO: return ('timeout',None)
    except BaseException as e: return ('err',type(e).__name__)
    finally: signal.setitimer(signal.ITIMER_REAL,0)

def load_fn(src,name):
    g={}
    with contextlib.redirect_stdout(io.StringIO()): exec(src,g)
    return g[name]
def passes_tests(src,task):
    signal.signal(signal.SIGALRM,_alarm); signal.setitimer(signal.ITIMER_REAL,3)
    try:
        g={}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(src,g); exec(task['test'],g); g['check'](g[task['entry_point']])
        return True
    except BaseException: return False
    finally: signal.setitimer(signal.ITIMER_REAL,0)

def audit_task(task):
    rng=random.Random(SEED+int(task['task_id'].split('/')[1]))
    canon=task['prompt']+task['canonical_solution']; ep=task['entry_point']
    res={'task_id':task['task_id'],'entry_point':ep,'canonical_passes':passes_tests(canon,task),
         'n_test_calls':len(harvest_args(task['test'])),'mutants_tried':0,'survivors':0,'equivalent_or_unknown':0,'witnesses':[]}
    try: tree=ast.parse(canon)
    except Exception: return res
    # only mutate inside the entry function body (not prompt docstring constants? docstring is str, fine)
    sites=mutation_sites(tree); rng.shuffle(sites); sites=sites[:MAX_MUTANTS]
    seeds=harvest_args(task['test']); fuzz=[]
    for s in seeds:
        for _ in range(FUZZ_PER_SEED): fuzz.append(perturb(s,rng))
    fuzz=seeds+fuzz
    try: cfn=load_fn(canon,ep)
    except Exception: return res
    cref=[run_quiet(cfn,a) for a in fuzz]
    for site in sites:
        try: msrc=apply(tree,site)
        except Exception: continue
        if msrc==ast.unparse(tree): continue
        res['mutants_tried']+=1
        if not passes_tests(msrc,task): continue
        res['survivors']+=1
        try: mfn=load_fn(msrc,ep)
        except Exception: continue
        wit=None
        for a,(cs,cv) in zip(fuzz,cref):
            if cs!='ok': continue
            ms,mv=run_quiet(mfn,a)
            if (ms,mv)!=(cs,cv): wit={'input':repr(a),'expected_canonical':cv,'mutant_output':mv if ms=='ok' else ms}; break
        if wit:
            diff=''.join(difflib.unified_diff(canon.splitlines(1),msrc.splitlines(1),'canonical','mutant',n=1))
            res['witnesses'].append({'mutation':describe(site),'diff':diff,**wit})
        else: res['equivalent_or_unknown']+=1
    return res

def dupes(tasks):
    out=[]; ps=[(t['task_id'],t['prompt']) for t in tasks]
    for i in range(len(ps)):
        for j in range(i+1,len(ps)):
            r=difflib.SequenceMatcher(None,ps[i][1],ps[j][1]).quick_ratio()
            if r>0.85 and difflib.SequenceMatcher(None,ps[i][1],ps[j][1]).ratio()>0.8: out.append((ps[i][0],ps[j][0],round(r,3)))
    return out

if __name__=='__main__' and len(sys.argv)>2 and sys.argv[1]=='--task':
    import resource; resource.setrlimit(resource.RLIMIT_AS,(1<<30,1<<30)); sys.setrecursionlimit(3000)
    tasks=[json.loads(l) for l in gzip.open(DATA,'rt')]; t=tasks[int(sys.argv[2])]
    r=audit_task(t); json.dump(r,open(f"results/per_task/{sys.argv[2]}.json",'w')); sys.exit(0)
if __name__=='__main__':
    tasks=[json.loads(l) for l in gzip.open(DATA,'rt')]
    sha=hashlib.sha256(open(DATA,'rb').read()).hexdigest()
    import subprocess, concurrent.futures as cf, os
    os.makedirs('results/per_task',exist_ok=True)
    def one(t):
        n=t['task_id'].split('/')[1]; f=f'results/per_task/{n}.json'
        if not os.path.exists(f):
            try: subprocess.run([sys.executable,__file__,'--task',n],timeout=180,capture_output=True)
            except subprocess.TimeoutExpired: pass
        if os.path.exists(f): return json.load(open(f))
        return {'task_id':t['task_id'],'error':'task audit timed out or crashed (resource limit)','witnesses':[]}
    with cf.ThreadPoolExecutor(6) as ex: results=list(ex.map(one,tasks))
    out={'benchmark':'HumanEval (openai/human-eval)','data_sha256':sha,'seed':SEED,'max_mutants':MAX_MUTANTS,
         'n_tasks':len(tasks),'results':results,'near_duplicate_prompts':dupes(tasks)}
    json.dump(out,open('results/raw_results.json','w'),indent=1)
    v=[r for r in results if r['witnesses']]
    print('tasks',len(tasks),'canonical_fail',sum(not r['canonical_passes'] for r in results),'flagged',len(v),
          'survivors_no_witness',sum(1 for r in results if r['survivors'] and not r['witnesses']))
