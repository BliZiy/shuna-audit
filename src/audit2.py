"""Shuna Audit v1 (multi-benchmark). python3 src/audit2.py <bench>   | single task: --one <bench> <idx>"""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import ast, copy, json, random, signal, sys, io, contextlib, os, math, difflib, hashlib
sys.path.insert(0,os.path.dirname(__file__))
from audit import mutation_sites, apply, describe, perturb, TO, _alarm
import adapters
MAX_MUTANTS=80; FUZZ_PER_SEED=30; SEED=1337; MAX_SEEDS=40

def timed(fn,t):
    signal.signal(signal.SIGALRM,_alarm); signal.setitimer(signal.ITIMER_REAL,t)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()): return ('ok',fn())
    except TO: return ('timeout',None)
    except BaseException as e: return ('err',type(e).__name__)
    finally: signal.setitimer(signal.ITIMER_REAL,0)
def load(src):
    g={'__name__':'cand'}; exec(src,g); return g
def call(g,entry,args,t=1): return timed(lambda: repr(g[entry](*copy.deepcopy(args))),t)
def close(a,b,atol):
    if a==b: return True
    try:
        x,y=eval(a),eval(b)
        if isinstance(x,float) and isinstance(y,float): return math.isclose(x,y,rel_tol=1e-6,abs_tol=max(atol,1e-9))
        if isinstance(x,(list,tuple)) and isinstance(y,(list,tuple)) and len(x)==len(y):
            return all(close(repr(p),repr(q),atol) for p,q in zip(x,y))
    except Exception: pass
    return False

class Task:
    def __init__(s,t): s.t=t
    def passes(s,src,ref=None):
        t=s.t
        if t['kind']=='plus':
            st,g=timed(lambda:load(src),2)
            if st!='ok': return False
            for a,(rs,rv) in zip(t['inputs'],ref):
                ms,mv=call(g,t['entry'],a,2)
                if rs!=ms or (rs=='ok' and not close(mv,rv,t['atol'])): return False
            return True
        def run():
            g=load(src)
            if t['kind']=='he': exec(t['test'],g); g['check'](g[t['entry']])
            else: exec(t['test'],g)
        return timed(run,5)[0]=='ok'
    def seeds(s):
        t=s.t
        if t['kind']=='plus': return [tuple(x) for x in t['inputs'][:MAX_SEEDS]]
        names={'candidate',t['entry']}; out=[]
        for n in ast.walk(ast.parse(t['test'])):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in names and not n.keywords:
                try: out.append(tuple(ast.literal_eval(a) for a in n.args))
                except Exception: pass
        return out[:MAX_SEEDS]

def audit(t):
    rng=random.Random(SEED+int(hashlib.md5(t['id'].encode()).hexdigest()[:8],16)); T=Task(t)
    res=dict(task_id=t['id'],entry=t['entry'],mutants_tried=0,survivors=0,equivalent_or_unknown=0,witnesses=[])
    ref=None
    try:
        g=load(t['src'])
        if t['kind']=='plus': ref=[call(g,t['entry'],a,2) for a in t['inputs']]
    except BaseException as e: res['canonical_passes']=False; res['canonical_error']=type(e).__name__; return res
    res['canonical_passes']=T.passes(t['src'],ref)
    if not res['canonical_passes']:
        if t['kind']=='asserts':  # find which assert fails: evidence of a wrong expected value
            for line in t['test'].splitlines():
                if line.strip().startswith('assert'):
                    st,_=timed(lambda: exec(line,dict(g)),3)
                    if st!='ok':
                        m=None
                        try:
                            node=ast.parse(line.strip()).body[0].test
                            if isinstance(node,ast.Compare): m=timed(lambda: repr(eval(ast.unparse(node.left),dict(g))),3)
                        except Exception: pass
                        res.setdefault('failing_asserts',[]).append({'assert':line.strip()[:300],'canonical_returns':m[1][:200] if m and m[0]=='ok' else str(m)})
        return res
    tree=ast.parse(t['src']); sites=mutation_sites(tree); rng.shuffle(sites)
    seeds=T.seeds(); fuzz=list(seeds)+[perturb(x,rng) for x in seeds for _ in range(FUZZ_PER_SEED)]
    cref=[call(g,t['entry'],a) for a in fuzz]
    seen=set(); base=ast.unparse(tree)
    for site in sites:
        if res['mutants_tried']>=MAX_MUTANTS: break
        try: msrc=apply(tree,site)
        except Exception: continue
        if msrc==base or msrc in seen: continue
        seen.add(msrc); res['mutants_tried']+=1
        if not T.passes(msrc,ref): continue
        res['survivors']+=1
        try: mg=load(msrc)
        except BaseException: continue
        wit=None
        for a,(cs,cv) in zip(fuzz,cref):
            if cs!='ok': continue
            ms,mv=call(mg,t['entry'],a)
            if ms!='ok' or not close(mv,cv,t.get('atol',0)): wit=dict(input=repr(a)[:500],expected_canonical=cv[:300],mutant_output=(mv if ms=='ok' else ms)[:300]); break
        if wit:
            res['witnesses'].append(dict(mutation=describe(site),diff=''.join(difflib.unified_diff(t['src'].splitlines(1),msrc.splitlines(1),'canonical','mutant',n=1))[:3000],mutant_src=msrc[:8000],**wit))
        else: res['equivalent_or_unknown']+=1
    return res

if __name__=='__main__':
    if sys.argv[1]=='--one':
        import resource; resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30)); sys.setrecursionlimit(3000)
        b,i=sys.argv[2],int(sys.argv[3]); t=adapters.BENCH[b]()[i]
        json.dump(audit(t),open(f'results/{b}/per_task/{i}.json','w')); sys.exit(0)
    import subprocess, concurrent.futures as cf
    b=sys.argv[1]; tasks=adapters.BENCH[b](); os.makedirs(f'results/{b}/per_task',exist_ok=True)
    def one(i):
        f=f'results/{b}/per_task/{i}.json'
        if not os.path.exists(f):
            try: subprocess.run([sys.executable,__file__,'--one',b,str(i)],timeout=400,capture_output=True)
            except subprocess.TimeoutExpired: pass
        return json.load(open(f)) if os.path.exists(f) else dict(task_id=tasks[i]['id'],error='timeout/crash',witnesses=[])
    with cf.ThreadPoolExecutor(6) as ex: R=list(ex.map(one,range(len(tasks))))
    json.dump(dict(benchmark=b,n_tasks=len(tasks),seed=SEED,results=R),open(f'results/{b}/raw.json','w'),indent=1)
    print(b,'tasks',len(tasks),'canonical_fail',sum(r.get('canonical_passes') is False for r in R),'errors',sum('error' in r for r in R),'with_witness',sum(bool(r['witnesses']) for r in R))
