"""Merge raw audits + EvalPlus oracle + manual review into results/findings_v1.json"""
import json, os
MANUAL={  # reviewed by reading the docstring; only used where no independent oracle exists
 'humanevalplus':{'verified':{90:"next_smallest([1,2]) must be 2; mutant returns None for any 2-element list"},
   'suspected':{6:"unbalanced parens (outside spec)",25:"n=0 outside spec",59:"n=13 is prime; spec says n is not prime",76:"negative inputs, spec silent",94:"negative ints, spec unclear",129:"ragged grid outside spec",135:"duplicates forbidden by spec"}},
 'mbppplus':{'verified':{71:"comb_sort returns an unsorted list",100:"returns 1219, which is not a palindrome",123:"5020 is amicable and <= limit, so must be included",133:"counts 0.88 as negative",166:"[0,2] has one even-XOR pair",468:"wrong max increasing-subsequence product on a valid list",576:"[2,2,2] is not a sub-array of [1,4,2,5,2]",577:"last digit of 3! is 6, mutant says 5",751:"[-1,1,22,18,3,6] is not a min-heap (6 < 22)"},
   'suspected':{96:"bool input",103:"negative m",239:"n=0 edge",260:"negative n",428:"bool list",556:"n inconsistent with list",583:"timeout only (slow, maybe not wrong)",599:"timeout only",622:"unsorted arrays outside spec",722:"'above' vs '>=' ambiguous",733:"unsorted array outside spec",763:"negative n",771:"whitespace string, ambiguous",784:"no even element",799:"d=31 rotation semantics ambiguous"}}}
MANUAL.update({'evoeval_subtle':{'verified':{90:"next_largest([18,6]) must be 6; mutant returns None for every 2-element list"},'suspected':{}},
 'evoeval_tool_use':{'verified':{11:"get_next_day('2018-1-31') returns the impossible date '2018-01-32'"},'suspected':{}},
 'evoeval_combine':{'verified':{26:"mutant maps 'eight' to 9 and returns () instead of ('eight', 1)"},'suspected':{}}})
NAMES={'humaneval':'HumanEval','mbpp':'MBPP (sanitized)','humanevalplus':'HumanEval+ (EvalPlus v0.1.10)','mbppplus':'MBPP+ (EvalPlus v0.2.0)','humanevalpro':'HumanEval Pro (2024/ACL 2025)','mbpppro':'MBPP Pro (2024/ACL 2025)','evoeval_difficult':'EvoEval Difficult (COLM 2024)','evoeval_creative':'EvoEval Creative','evoeval_subtle':'EvoEval Subtle','evoeval_combine':'EvoEval Combine','evoeval_tool_use':'EvoEval Tool-Use'}
PRIOR={'humaneval':'Known: EvalPlus (2023) showed weak tests. Our result re-confirms it.','mbpp':'Known: EvalPlus/MBPP+ (2023) re-tested MBPP. Re-confirmation.',
 'humanevalplus':'Gaps remaining AFTER EvalPlus hardening. No prior report found in a quick search.','mbppplus':'Gaps remaining AFTER EvalPlus hardening. No prior report found in a quick search.',
 'humanevalpro':'No prior test-strength audit found (checked repo issues, X, web). Repo issue #2 (2025) reported ambiguous specs, a different flaw. Authors claim 100% verified tests.','mbpppro':'Same as HumanEval Pro.','evoeval_difficult':'Spec/reference errors already reported (GitHub issue #2, 2025). Weak-test (accepts-wrong) findings not previously reported as far as we found. Mostly unreviewed: treat as suspected.','evoeval_creative':'Spec/reference errors already reported (GitHub issue #2, 2025). Weak-test (accepts-wrong) findings not previously reported as far as we found. Mostly unreviewed: treat as suspected.','evoeval_subtle':'Spec/reference errors already reported (GitHub issue #2, 2025). Weak-test (accepts-wrong) findings not previously reported as far as we found. Mostly unreviewed: treat as suspected.','evoeval_combine':'Spec/reference errors already reported (GitHub issue #2, 2025). Weak-test (accepts-wrong) findings not previously reported as far as we found. Mostly unreviewed: treat as suspected.','evoeval_tool_use':'Spec/reference errors already reported (GitHub issue #2, 2025). Weak-test (accepts-wrong) findings not previously reported as far as we found. Mostly unreviewed: treat as suspected.'}
out={'generated':'2026-10-18','benchmarks':[]}
for b in NAMES:
    raw=json.load(open(f'results/{b}/raw.json'))['results']
    orc={o['task_id']:o for o in json.load(open(f'results/{b}/oracle.json'))} if os.path.exists(f'results/{b}/oracle.json') else {}
    items=[]
    for r in raw:
        n=int(r['task_id'].split('/')[1]) if r['task_id'].split('/')[1].isdigit() else -1; man=MANUAL.get(b,{})
        if r.get('canonical_passes') is False:
            items.append(dict(task_id=r['task_id'],status='rejects-correct-solution',note='official reference solution fails the official tests on Python 3.13 (exact float equality)',evidence=r.get('failing_asserts'))); continue
        if not r['witnesses']: continue
        o=orc.get(r['task_id']); ow=next((w for w in (o or {}).get('per_witness',[]) if w.get('oracle_disagrees')),None)
        if ow:
            w=next(x for x in r['witnesses'] if x['mutation']==ow['mutation'])
            st,note='verified-oracle',f"wrong helper passes; EvalPlus ({o['oracle']}) shows it is wrong on input {ow['oracle_input'][:80]} (expected {ow['oracle_expected'][:40]}, got {ow['mutant_helper_output'][:40]})"
        elif n in man.get('verified',{}): w,st,note=r['witnesses'][0],'verified-manual',man['verified'][n]
        else: w,st,note=r['witnesses'][0],'suspected',man.get('suspected',{}).get(n,'witness input may be outside spec or the mutant may be harmless; not reviewed against an oracle')
        items.append(dict(task_id=r['task_id'],status=st,note=note,witness_input=w['input'],correct=w['expected_canonical'],wrong_solution_output=w['mutant_output'],diff=w['diff'],wrong_mutants_passing=len(r['witnesses'])))
    c=lambda s:sum(i['status']==s for i in items)
    out['benchmarks'].append(dict(id=b,name=NAMES[b],n_tasks=len(raw),verified=c('verified-oracle')+c('verified-manual'),verified_oracle=c('verified-oracle'),verified_manual=c('verified-manual'),suspected=c('suspected'),rejects_correct=c('rejects-correct-solution'),prior_work=PRIOR[b],items=items))
json.dump(out,open('results/findings_v1.json','w'),indent=1)
for x in out['benchmarks']: print(f"{x['name']}: {x['n_tasks']} tasks | verified {x['verified']} ({100*x['verified']/x['n_tasks']:.1f}%) [oracle {x['verified_oracle']}, manual {x['verified_manual']}] | suspected {x['suspected']} | rejects-correct {x['rejects_correct']}")
