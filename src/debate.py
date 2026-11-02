"""Debate check (deterministic prosecutor/defender) for every flagged finding.
Prosecutor: re-runs the evidence (wrong program passes official tests; output differs on witness; oracle disagreement).
Defender tries to refute it with:
  D1 reference sanity  : reference passes official tests; deterministic on witness (3 runs)
  D2 input domain      : witness must look like the official inputs (same type shape; numbers within the official
                         min..max for that argument; string chars drawn from official strings; list lengths >= official min)
  D3 task wording      : docstring words (positive / non-negative / sorted / distinct|unique / non-empty) the witness violates
  D4 harmless diff     : timeout-only, or float difference within 1e-6
  D5 composite check   : for Pro tasks, the wrong solution must also give a wrong FINAL answer on an in-domain input
If the original witness fails D2-D4 the prosecutor gets one retry: a conservative fuzz (values drawn only from the official
inputs) to find a new in-domain witness. Verdicts: confirmed / helper-only (Pro: helper provably wrong, final answer not
shown wrong in-domain) / rejected.   python3 src/debate.py <bench>"""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import json, sys, os, random, copy, re, math
sys.path.insert(0,os.path.dirname(__file__))
import adapters
from audit2 import Task, load, call, close, timed
def shape(v):
    if isinstance(v,bool): return 'bool'
    if isinstance(v,int): return 'int'
    if isinstance(v,float): return 'num'
    if isinstance(v,str): return 'str'
    if isinstance(v,(list,tuple)): return (type(v).__name__,tuple(sorted({shape(x) for x in v}, key=str)))
    if isinstance(v,dict): return 'dict'
    return type(v).__name__
def leaves(v,acc):
    if isinstance(v,bool): acc['b'].add(v)
    elif isinstance(v,(int,float)): acc['n'].append(v)
    elif isinstance(v,str): acc['c'].update(v); acc['s'].append(v)
    elif isinstance(v,(list,tuple)): acc['len'].append(len(v)); [leaves(x,acc) for x in v]
    elif isinstance(v,dict): [leaves(x,acc) for x in list(v.keys())+list(v.values())]
def profile(inputs):
    P={}
    for a in inputs:
        for i,v in enumerate(a):
            p=P.setdefault(i,{'shapes':set(),'n':[],'c':set(),'s':[],'len':[],'b':set(),'vals':[]})
            p['shapes'].add(str(shape(v))); leaves(v,p); p['vals'].append(v)
    return P
def in_domain(args,P):
    if len(args)!=len(P): return False,'arity'
    for i,v in enumerate(args):
        p=P[i]
        if p['shapes'] and str(shape(v)) not in p['shapes']:
            # allow empty containers if any official container shape at that slot
            if not (isinstance(v,(list,tuple)) and len(v)==0 and any(s.startswith("('"+type(v).__name__) for s in p['shapes'])): return False,f'arg{i} type'
        a={'b':set(),'n':[],'c':set(),'s':[],'len':[]}; leaves(v,a)
        if a['n'] and p['n'] and (min(a['n'])<min(p['n']) or max(a['n'])>max(p['n'])): return False,f'arg{i} value out of official range'
        if a['c'] and p['c'] and not a['c']<=p['c']: return False,f'arg{i} new characters'
        if a['len'] and p['len'] and min(a['len'])<min(p['len']): return False,f'arg{i} shorter than any official input'
    return True,''
WORD=[(r'\bpositive\b',lambda a:any(x<=0 for x in nums(a)),'docstring says positive'),
      (r'non-?negative',lambda a:any(x<0 for x in nums(a)),'docstring says non-negative'),
      (r'\bsorted\b',lambda a:any(isinstance(v,list) and v!=sorted(v) for v in a if safe_sortable(v)),'docstring says sorted'),
      (r'\b(distinct|unique|no duplicates?)\b',lambda a:any(isinstance(v,list) and len(v)!=len(set(map(repr,v))) for v in a),'docstring says distinct/unique'),
      (r'non-?empty',lambda a:any(isinstance(v,(list,str,tuple)) and len(v)==0 for v in a),'docstring says non-empty')]
def nums(a):
    acc={'b':set(),'n':[],'c':set(),'s':[],'len':[]}; [leaves(v,acc) for v in a]; return acc['n']
def safe_sortable(v):
    try: sorted(v); return True
    except Exception: return False
def wording(doc,args):
    for pat,viol,msg in WORD:
        if re.search(pat,doc,re.I) and viol(args): return msg
    return ''
def conservative(a,P,rng):
    out=[]
    for i,v in enumerate(a):
        p=P[i]; out.append(cv(v,p,rng))
    return tuple(out)
def cv(v,p,rng,d=0):
    if isinstance(v,bool): return v
    if isinstance(v,int) and p['n']:
        ints=[x for x in p['n'] if isinstance(x,int) and not isinstance(x,bool)] or [v]
        if rng.random()<.5: return rng.choice(ints)
        fin=[x for x in p['n'] if isinstance(x,(int,float)) and math.isfinite(x)] or [v]
        lo,hi=int(math.ceil(min(fin))),int(math.floor(max(fin)))
        if lo>hi: return v
        return rng.randint(lo,min(hi,lo+50)) if rng.random()<.6 else rng.randint(lo,hi)
    if isinstance(v,float) and p['n']: return rng.choice(p['n'])
    if isinstance(v,str) and v:
        s=list(v); op=rng.random()
        if op<.4: rng.shuffle(s)
        elif op<.7 and len(s)>1: s.pop(rng.randrange(len(s)))
        else: return rng.choice(p['s']) if p['s'] else v
        return ''.join(s)
    if isinstance(v,list) and d<3:
        s=[cv(x,p,rng,d+1) for x in v]; op=rng.random()
        if op<.3: rng.shuffle(s)
        elif op<.6 and s: s.append(copy.deepcopy(rng.choice(s)))
        elif s and len(s)>min(p['len'] or [0]): s.pop(rng.randrange(len(s)))
        return s
    return v
def debate(bench):
    raw=json.load(open(f'results/{bench}/raw.json'))['results']; T={t['id']:t for t in adapters.BENCH[bench]()}
    orc={o['task_id']:o for o in json.load(open(f'results/{bench}/oracle.json'))} if os.path.exists(f'results/{bench}/oracle.json') else {}
    out=[]
    for r in raw:
        if not r['witnesses']: continue
        if os.environ.get('ONLY') and r['task_id']!=os.environ['ONLY']: continue
        t=T[r['task_id']]; task=Task(t); rng=random.Random(7)
        offi=t['inputs'] if t['kind']=='plus' else task.seeds()
        if not offi: out.append(dict(task_id=r['task_id'],verdict='rejected',reason='no official inputs to define a domain')); continue
        P=profile(offi); doc=t['src']
        g=load(t['src']); best=None; log=[]
        o=orc.get(r['task_id']); ow={w['mutation']:w for w in (o or {}).get('per_witness',[]) if w.get('oracle_disagrees')}
        cands=sorted(r['witnesses'],key=lambda w:w['mutation'] not in ow)[:int(os.environ.get('MAXC','999'))]; print(r['task_id'],len(cands),flush=True)
        for w in cands:
            st,mg=timed(lambda:load(w['mutant_src']),3)
            if st!='ok': continue
            # prosecutor: wrong program still passes official tests?
            ref=[call(g,t['entry'],a,2) for a in t['inputs']] if t['kind']=='plus' else None
            if not task.passes(w['mutant_src'],ref): log.append('evidence did not reproduce'); continue
            tries=[eval(w['input'])]+[conservative(rng.choice(offi),P,rng) for _ in range(int(os.environ.get("TRIES","1500")))]
            for k,a in enumerate(tries):
                a=tuple(a) if isinstance(a,(list,tuple)) else (a,)
                ok,why=in_domain(a,P)
                if not ok: 
                    if k==0: log.append('D2 original witness refuted: '+why)
                    continue
                wd=wording(doc,a)
                if wd:
                    if k==0: log.append('D3 original witness refuted: '+wd)
                    continue
                c1=call(g,t['entry'],a,2); c2=call(g,t['entry'],a,2)
                if c1[0]!='ok' or c1!=c2: continue                       # D1
                m=call(mg,t['entry'],a,2)
                if m[0]=='timeout': continue                                # D4
                if m[0]=='ok' and close(m[1],c1[1],1e-6): continue          # D4
                best=dict(mutation=w['mutation'],input=repr(a)[:300],correct=c1[1][:200],wrong=(m[1] if m[0]=='ok' else m[0])[:200],retry=k>0,oracle=w['mutation'] in ow,diff=w['diff']); break
            if best: break
        if best: verdict='confirmed'; reason='survived D1-D5'+(' (new in-domain witness found on retry)' if best['retry'] else '')
        elif ow: verdict='helper-only'; reason='helper provably wrong (EvalPlus oracle) but no in-domain input shows a wrong final answer'
        else: verdict='rejected'; reason='; '.join(dict.fromkeys(log)) or 'no in-domain witness'
        out.append(dict(task_id=r['task_id'],verdict=verdict,reason=reason,witness=best,oracle_input=(next(iter(ow.values())).get('oracle_input') if ow else None)))
    json.dump(out,open(os.environ.get('OUT',f'results/{bench}/debate.json'),'w'),indent=1)
    c=lambda v:sum(x['verdict']==v for x in out)
    print(bench,'flagged',len(out),'confirmed',c('confirmed'),'helper-only',c('helper-only'),'rejected',c('rejected'))
if __name__=='__main__':
    import resource; resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30)); sys.setrecursionlimit(3000)
    debate(sys.argv[1])
