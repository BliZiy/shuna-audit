"""SWE-bench Verified 50-task sample: STATIC test-patch checks (no code is executed; data = public HF parquet).
Usage (from audit/): python3 src/swebench_static.py [N=50] [SEED=20261026]   -> results/swebench_verified/static.json + static.md
Flags (heuristics, each needs manual confirmation before it is called a finding):
  name_leak   : an identifier the GOLD PATCH introduces (new def/class/kwarg/attr) is used by the TEST PATCH but never appears in the problem statement
  msg_leak    : a string literal in a test assertion/`match=`/assertRaisesMessage that is not in the problem statement (exact error text must be guessed)
  few_asserts : the added test lines contain <=1 assertion-like statement for a multi-file/multi-hunk gold patch (little behavioural coverage)
  weak_assert : F2P-relevant added assertions are only existence/type/None checks (hasattr/isinstance/is not None/assertTrue(x))
  single_f2p  : exactly one FAIL_TO_PASS test (a one-point oracle)
  no_p2p      : no PASS_TO_PASS tests (nothing guards against regressions)
"""
import json, re, sys, random, collections
import pandas as pd
N=int(sys.argv[1]) if len(sys.argv)>1 else 50; SEED=int(sys.argv[2]) if len(sys.argv)>2 else 20261026
D=pd.read_parquet('data/swebench/verified.parquet')
random.seed(SEED)
# stratified by repo (proportional, at least 1 where possible), seeded
ids=[]; by=D.groupby('repo').instance_id.apply(list).to_dict()
quota={r:max(1,round(N*len(v)/len(D))) for r,v in by.items()}
while sum(quota.values())>N: quota[max(quota,key=quota.get)]-=1
while sum(quota.values())<N: quota[max(by,key=lambda r:len(by[r])-quota[r])]+=1
for r,v in sorted(by.items()): ids+=random.sample(sorted(v),quota[r])
S=D.set_index('instance_id').loc[sorted(ids)]
def added(p): return [l[1:] for l in p.split('\n') if l.startswith('+') and not l.startswith('+++')]
def removed(p): return [l[1:] for l in p.split('\n') if l.startswith('-') and not l.startswith('---')]
def files(p): return re.findall(r'^\+\+\+ b/(\S+)',p,re.M)
IDENT=re.compile(r'\b[A-Za-z_][A-Za-z0-9_]{3,}\b')
KW=set('self return import from class None True False with else elif lambda yield assert raise try except finally pass break continue while for def not and is in or if'.split())
def new_idents(patch):
    out=set()
    for l in added(patch):
        m=re.match(r'\s*(?:async\s+)?def\s+(\w+)\s*\((.*)\)',l)
        if m:
            out.add(m[1])
            for a in re.split(r',',m[2]):
                a=a.split(':')[0].split('=')[0].strip(' *')
                if a and a not in('self','cls'): out.add(a)
        m=re.match(r'\s*class\s+(\w+)',l)
        if m: out.add(m[1])
        m=re.match(r'\s*self\.(\w+)\s*=',l)
        if m: out.add(m[1])
    old=set(IDENT.findall('\n'.join(removed(patch))))
    return {i for i in out if len(i)>3 and not i.startswith('__') and i not in old}
ASSERT=re.compile(r'\bassert\w*\b|\.assert\w+\(|pytest\.raises|assertRaises|\bassert_\w+\(|\bok\(|\braises\(')
WEAK=re.compile(r'hasattr|isinstance|is not None|assertTrue\(\w+\)|assertIsNotNone|assertIsInstance|callable\(')
rows=[]
for iid,r in S.iterrows():
    f2p=json.loads(r.FAIL_TO_PASS) if isinstance(r.FAIL_TO_PASS,str) else list(r.FAIL_TO_PASS)
    p2p=json.loads(r.PASS_TO_PASS) if isinstance(r.PASS_TO_PASS,str) else list(r.PASS_TO_PASS)
    ps=r.problem_statement+'\n'+(r.hints_text or '')
    ta=added(r.test_patch); asr=[l for l in ta if ASSERT.search(l)]
    ni=new_idents(r.patch); used=sorted(i for i in ni if re.search(r'\b'+re.escape(i)+r'\b','\n'.join(ta)) and not re.search(r'\b'+re.escape(i)+r'\b',ps))
    lits=[]
    for l in asr:
        if True:   # any string literal (>=12 chars) on an assertion line
            lits+=re.findall(r"""(?:'([^']{12,})'|"([^"]{12,})")""",l)
    lits=[a or b for a,b in lits]; miss=[s for s in lits if s.lower() not in ps.lower() and re.sub(r'\W+',' ',s).strip().lower() not in re.sub(r'\W+',' ',ps).lower()]
    hunks=r.patch.count('\n@@ ')+1
    fl=[]
    if used: fl.append('name_leak')
    if miss: fl.append('msg_leak')
    if len(asr)<=1 and (hunks>=3 or len(files(r.patch))>=2): fl.append('few_asserts')
    if asr and all(WEAK.search(l) for l in asr): fl.append('weak_assert')
    if len(f2p)==1: fl.append('single_f2p')
    if not p2p: fl.append('no_p2p')
    rows.append(dict(instance_id=iid,repo=r.repo,difficulty=r.difficulty,n_f2p=len(f2p),n_p2p=len(p2p),gold_files=len(files(r.patch)),gold_hunks=hunks,
        gold_add=len(added(r.patch)),test_files=len(files(r.test_patch)),test_add=len(ta),test_asserts=len(asr),name_leak_ids=used[:6],msg_leak_examples=[m[:90] for m in miss[:2]],flags=fl))
import os; os.makedirs('results/swebench_verified',exist_ok=True)
json.dump(dict(seed=SEED,n=N,source='princeton-nlp/SWE-bench_Verified (HF parquet, 500 tasks)',rows=rows),open('results/swebench_verified/static.json','w'),indent=1)
C=collections.Counter(f for r in rows for f in r['flags'])
md=[f"# SWE-bench Verified: static test-patch checks, {N}-task sample (seed {SEED}) — PRIVATE\n","No code was executed. Flags are heuristics that need manual confirmation; none is a published finding.\n",
    "Flag counts: "+', '.join(f'{k} {v}' for k,v in sorted(C.items()))+"\n","| instance | diff | F2P | P2P | gold files/hunks | test asserts | flags | evidence |","|---|---|---|---|---|---|---|---|"]
for r in rows:
    ev='; '.join(([f"new in patch, used in test, not in issue: {', '.join(r['name_leak_ids'])}"] if r['name_leak_ids'] else [])+([f"msg not in issue: {r['msg_leak_examples'][0]!r}"] if r['msg_leak_examples'] else []))
    md.append(f"| {r['instance_id']} | {r['difficulty']} | {r['n_f2p']} | {r['n_p2p']} | {r['gold_files']}/{r['gold_hunks']} | {r['test_asserts']} | {', '.join(r['flags'])} | {ev[:160]} |")
open('results/swebench_verified/static.md','w').write('\n'.join(md)+'\n'); print('\n'.join(md[:5]))
