"""Final status = debate (necessary) + independent confirmation (EvalPlus oracle or documented manual review)."""
import json, os
NAMES={'humanevalpro':'HumanEval Pro','mbpppro':'MBPP Pro','bcblitepro':'BigCodeBench-Lite Pro','humanevalnext':'HumanEvalNext (public 82)','evoeval_difficult':'EvoEval Difficult','evoeval_creative':'EvoEval Creative','evoeval_subtle':'EvoEval Subtle','evoeval_combine':'EvoEval Combine','evoeval_tool_use':'EvoEval Tool-Use','humaneval':'HumanEval','mbpp':'MBPP (sanitized)','humanevalplus':'HumanEval+','mbppplus':'MBPP+'}
PRIOR={'humanevalpro':'Likely new (no prior report found). Authors notified Oct 18 (correction to 40/25 sent 11:11 PM ET); embargo to Nov 1.','mbpppro':'Likely new. Authors notified Oct 18; embargo to Nov 1.','bcblitepro':'Likely new; same authors as HumanEval Pro (covered by the same embargo in spirit).',
 'humanevalnext':'Likely new (2025 TSE benchmark; only 82 tasks public).','humaneval':'Known since EvalPlus (2023).','mbpp':'Known since EvalPlus (2023).','humanevalplus':'Gaps after EvalPlus hardening; likely new.','mbppplus':'Gaps after EvalPlus hardening; likely new.'}
for n in ['difficult','creative','subtle','combine','tool_use']: PRIOR[f'evoeval_{n}']='Spec/reference bugs already reported (issue #2, 2025); weak-test findings likely new.'
EXTRA={'mbpppro':[('MbppPro/36','exact float equality: reference fails on Python 3.13'),('MbppPro/117','exact float equality'),('MbppPro/260','exact float equality')],
 'bcblitepro':[('BCBLitePro/551',"expected values only hold when the machine's timezone is UTC+8 (reference returns 1 in UTC, 28801 in Asia/Shanghai)")]}
M=json.load(open('results/manual_review.json')); out={'generated':'2026-10-18','benchmarks':[]}
for b,name in NAMES.items():
    if not os.path.exists(f'results/{b}/debate.json'): continue
    raw=json.load(open(f'results/{b}/raw.json'))['results']; D=json.load(open(f'results/{b}/debate.json'))
    man=M.get(b,{}); items=[]
    for d in D:
        n=d['task_id'].split('/')[1]
        if d['verdict']=='rejected' or n in man.get('reject',{}): st='rejected'; note=man.get('reject',{}).get(n) or d['reason']
        elif d['verdict']=='helper-only': st='helper-only'; note=d['reason']+(f" (EvalPlus input {d['oracle_input'][:60]})" if d.get('oracle_input') else '')
        elif d['witness'] and d['witness'].get('oracle'): st='confirmed'; note='debate survived + EvalPlus oracle'
        elif n in man.get('confirm',{}): st='confirmed'; note='debate survived + manual review: '+man['confirm'][n]
        else: st='suspected'; note='survived debate but no independent confirmation yet'
        w=d.get('witness') or {}
        items.append(dict(task_id=d['task_id'],status=st,note=note,witness_input=w.get('input',''),correct=w.get('correct',''),wrong_solution_output=w.get('wrong',''),diff=w.get('diff','')))
    for tid,why in EXTRA.get(b,[]): items.append(dict(task_id=tid,status='rejects-correct-solution',note=why))
    c=lambda s:sum(i['status']==s for i in items)
    out['benchmarks'].append(dict(id=b,name=name,n_tasks=len(raw),verified=c('confirmed'),verified_oracle=0,verified_manual=0,confirmed=c('confirmed'),helper_only=c('helper-only'),suspected=c('suspected'),rejected=c('rejected'),rejects_correct=c('rejects-correct-solution'),prior_work=PRIOR[b],items=items))
json.dump(out,open('results/findings_v2.json','w'),indent=1)
for x in out['benchmarks']: print(f"{x['name']:28s} tasks {x['n_tasks']:3d} | confirmed {x['confirmed']:3d} | helper-only {x['helper_only']:2d} | suspected {x['suspected']:2d} | rejected {x['rejected']:2d} | rejects-correct {x['rejects_correct']}")
