"""SWE-bench Verified gold-patch mutation pilot (sympy subset of the 50-task sample; pure-Python, runs without SWE-bench Docker images).
For each task: base_commit worktree + test_patch -> F2P must FAIL; + gold patch -> F2P must PASS; then each mutant of the gold patch's
ADDED lines (operator flips / constant changes / negations) is run on the F2P test files. A mutant that still passes all F2P tests
is a SURVIVOR (test patch does not pin that line; may be an equivalent mutant -> needs manual review). PASS_TO_PASS is NOT run (heavy).
Usage: python3 src/swebench_mutate.py <work_dir> <instance_id> [max_mutants=12]    (work_dir holds sympy_repo/ and venv39/)
Third-party open-source code runs on the host with a timeout (not model-written code)."""
import sys, os, re, json, subprocess, random, shutil, pathlib
import pandas as pd
W=pathlib.Path(sys.argv[1]); IID=sys.argv[2]; MAXM=int(sys.argv[3]) if len(sys.argv)>3 else 12
R=pd.read_parquet('data/swebench/verified.parquet').set_index('instance_id').loc[IID]
REPO=W/'sympy_repo'; WT=W/'wt'/IID; PY=str(W/'venv39/bin/python')
def sh(cmd,cwd=None,timeout=300,inp=None):
    try: p=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=timeout,input=inp,shell=isinstance(cmd,str)); return p.returncode,p.stdout+p.stderr
    except subprocess.TimeoutExpired: return 124,'timeout'
if WT.exists(): sh(f'git worktree remove --force {WT}',cwd=REPO)
os.makedirs(WT.parent,exist_ok=True)
rc,o=sh(f'git worktree add -f --detach {WT} {R.base_commit}',cwd=REPO,timeout=900); assert rc==0,o[-300:]
def apply(patch,cwd):
    rc,o=sh(['git','apply','--whitespace=nowarn','-'],cwd=cwd,inp=patch); return rc==0
tfiles=sorted(set(re.findall(r'^\+\+\+ b/(\S+)',R.test_patch,re.M)))
f2p=json.loads(R.FAIL_TO_PASS) if isinstance(R.FAIL_TO_PASS,str) else list(R.FAIL_TO_PASS)
def run_f2p(tmo=240):
    rc,o=sh([PY,'-m','pytest','-p','no:cacheprovider','-q','-rA','--no-header']+tfiles+['-k',' or '.join(f2p)],cwd=WT,timeout=tmo)
    st={}
    for l in o.split('\n'):
        m=re.match(r'(PASSED|FAILED|ERROR) \S+::(?:\S+::)?(\w+)',l)
        if m: st[m[2]]=m[1]
    ok=all(st.get(t.split('::')[-1])=='PASSED' for t in f2p) if st else False
    return ok,st,o[-400:]
out=dict(instance_id=IID,f2p=f2p,test_files=tfiles)
assert apply(R.test_patch,WT),'test_patch failed'
ok0,st0,tail0=run_f2p(); out['before_gold_f2p_pass']=ok0
assert apply(R.patch,WT),'gold patch failed'
ok1,st1,tail1=run_f2p(); out['after_gold_f2p_pass']=ok1; out['after_gold_status']=st1
if not ok1:
    out['error']='gold does not pass F2P in this env (env mismatch)'; out['tail']=tail1
    json.dump(out,open(f'results/swebench_verified/mut_{IID}.json','w'),indent=1); print(json.dumps(out)); sh(f'git worktree remove --force {WT}',cwd=REPO); sys.exit(0)
sites=[]
for fd in re.split(r'^diff --git ',R.patch,flags=re.M)[1:]:
    fn=re.search(r'^\+\+\+ b/(\S+)',fd,re.M)[1]
    if '/tests/' in fn or fn.startswith('test'): continue
    ln=0
    for l in fd.split('\n'):
        m=re.match(r'@@ -\d+(?:,\d+)? \+(\d+)',l)
        if m: ln=int(m[1])-1; continue
        if l.startswith('+') and not l.startswith('+++'): ln+=1; sites.append((fn,ln,l[1:]))
        elif l.startswith('-') or l.startswith('\\') or l.startswith('---'): pass
        else: ln+=1
MUT=[(r'==','!='),(r'!=','=='),(r'<=','<'),(r'>=','>'),(r' < ',' <= '),(r' > ',' >= '),(r' and ',' or '),(r' or ',' and '),(r'\bTrue\b','False'),(r'\bFalse\b','True'),
     (r' \+ ',' - '),(r' - ',' + '),(r' \* ',' / '),(r'\bnot ',''),(r'\bis None\b','is not None'),(r'\bis not None\b','is None'),(r'\b(\d+)\b',lambda m:str(int(m[1])+1)),(r'\breturn (.+)$','return None')]
muts=[]
for fn,ln,l in sites:
    s=l.strip()
    if not s or s.startswith(('#','"""',"'''")) or s.startswith(('def ','class ','import ','from ')): continue
    for pat,rep in MUT:
        if re.search(pat,l):
            new=re.sub(pat,rep,l,count=1)
            if new!=l: muts.append((fn,ln,l,new,pat))
random.seed(20261026); random.shuffle(muts); muts=muts[:MAXM]; out['n_sites']=len(sites); out['mutants']=[]
for fn,ln,l,new,pat in muts:
    p=WT/fn; src=p.read_text().split('\n'); assert src[ln-1]==l,(src[ln-1],l)
    src[ln-1]=new; p.write_text('\n'.join(src))
    okm,stm,_=run_f2p(); p.write_text('\n'.join(src[:ln-1]+[l]+src[ln:]))
    out['mutants'].append(dict(file=fn,line=ln,orig=l.strip()[:120],mutant=new.strip()[:120],f2p_pass=okm,verdict='SURVIVED' if okm else 'killed'))
    print(IID,fn,ln,'SURVIVED' if okm else 'killed',flush=True)
sh(f'git worktree remove --force {WT}',cwd=REPO)
json.dump(out,open(f'results/swebench_verified/mut_{IID}.json','w'),indent=1)
print(json.dumps({k:v for k,v in out.items() if k!='mutants'}))
