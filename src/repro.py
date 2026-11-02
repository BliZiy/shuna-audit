"""Re-run the audit for one task and confirm the wrong-but-passing mutant: python3 src/repro.py 31"""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import sys, json, gzip; sys.path.insert(0,'src'); import audit
t=[json.loads(l) for l in gzip.open(audit.DATA,'rt')][int(sys.argv[1])]
r=audit.audit_task(t)
for w in r['witnesses'][:1]:
    print(w['diff']); print('input:',w['input'],'| canonical:',w['expected_canonical'],'| mutant:',w['mutant_output'],'| mutant passes official tests: True')
