import json
d=json.load(open('results/raw_results.json'))
VER={10:"shortest palindrome of 'xz' must be 'xzx'",20:"closest pair; negatives are valid floats",31:"is_prime(2) must be True",40:"no three distinct elements sum to 0",43:"-1 and 1 sum to zero",46:"fib4(4)=2 is in spec",59:"largest prime factor of 64 is 2",71:"(4,2,2) is degenerate -> -1 per spec",72:"[2,4,-1,2] is not a palindrome -> False (negative weight unusual but irrelevant)",75:"32=2^5 is not a product of exactly 3 primes",76:"x=10 is not a power of 1",80:"'aab' has adjacent repeats -> not happy",99:"closest_integer('1') = 1",105:"7 is in 1..9 and must map to 'Seven'",108:"-11 has signed digit sum 0, must not count",114:"min subarray sum of [1,-4] is -4",118:"leading 'u' does not count -> ''",126:"[2,1,2,3] is not sorted",127:"intersection length 4 is not prime -> NO",150:"4 is not prime -> y",154:"'wxy' is a rotation found in 'xyw'",157:"(4,5,3) is a right triangle"}
SUS={6:"input has unbalanced parens (outside spec)",18:"empty substring - spec silent",25:"n=0 likely outside spec",39:"n=0 outside spec (n>=1)",69:"spec says positive ints; input has 0/negatives",94:"negative ints - spec unclear",116:"spec says non-negative but official tests use negatives - ambiguous task",124:"single-digit day; format mm-dd-yyyy arguably invalid",129:"ragged non-square grid outside spec",135:"spec forbids duplicates; input has duplicates",163:"negative bound - spec ambiguous about digits"}
items=[]
for r in d['results']:
    n=int(r['task_id'].split('/')[1])
    if not r['witnesses']: continue
    st='verified' if n in VER else 'suspected'
    items.append({'task_id':r['task_id'],'status':st,'reviewer_note':VER.get(n) or SUS.get(n),'wrong_mutants_passing':len(r['witnesses']),
                  'official_test_calls':r['n_test_calls'],'mutants_tried':r['mutants_tried'],'witness':r['witnesses'][0],'repro':f'python3 src/repro.py {n}'})
out={'benchmark':d['benchmark'],'data_sha256':d['data_sha256'],'method':'AST mutation of canonical solution -> keep mutants passing official tests -> differential fuzz vs canonical on perturbed test inputs -> human-style spec review',
     'n_tasks':d['n_tasks'],'n_verified':sum(i['status']=='verified' for i in items),'n_suspected':sum(i['status']=='suspected' for i in items),
     'near_duplicates':[{'pair':p[:2],'ratio':p[2],'note':'same template, different bracket chars; not a flaw'} for p in d['near_duplicate_prompts']],'findings':items}
json.dump(out,open('results/findings.json','w'),indent=1)
L=[f"# Shuna Audit #1 — HumanEval weak-test findings\n",f"Dataset: openai/human-eval `HumanEval.jsonl.gz` (sha256 `{d['data_sha256'][:16]}…`), all {d['n_tasks']} tasks. Run date 2026-10-18. Cost: $0 (local CPU, no LLM).\n",
"## Headline\n",f"- **{out['n_verified']} tasks verified** to accept a demonstrably wrong solution (the mutant passes every official test but returns a different, spec-violating answer on a valid input).",
f"- **{out['n_suspected']} tasks suspected** — the mutant differs only on inputs that are outside or ambiguous under the task spec. Not counted as flaws.",
"- All 164 canonical solutions pass their own tests. One near-duplicate pair (56/61) is intentional, not a flaw.\n",
"## Method\n1. Parse each canonical solution; create up to 80 small mutants (flip `<`/`<=`, `+`/`-`, `and`/`or`, ±1 on integer constants, drop `not`).\n2. Keep mutants that still pass the official `check()`.\n3. Fuzz: perturb the inputs used in the official tests (≈30 variants each) and compare mutant vs canonical outputs. A difference = witness.\n4. Review each witness against the docstring: is the input valid, and is the canonical answer the right one?\n",
"## False-positive risk (read this)\n- 'Verified' depends on (a) the canonical solution being correct on the witness input and (b) our reading of the spec. Both were checked by reading, not by an independent expert — treat as strong but not final.\n- 'Suspected' items are probably not test bugs; they mostly show underspecified prompts.\n- Survivors with no witness (30 tasks) are likely equivalent mutants and are NOT reported.\n- Mutation testing measures test *strength*; a model would still need to produce such a bug for it to inflate scores. Impact on pass@1 is not yet measured.\n",
"## Verified\n| Task | Why the mutant is wrong | Witness input | Correct | Mutant | # passing wrong mutants |\n|---|---|---|---|---|---|"]
for i in items:
    if i['status']=='verified': w=i['witness']; L.append(f"| {i['task_id']} | {i['reviewer_note']} | `{w['input'][:50]}` | `{w['expected_canonical'][:30]}` | `{str(w['mutant_output'])[:30]}` | {i['wrong_mutants_passing']} |")
L.append("\n## Suspected (not counted)\n| Task | Note | Witness input |\n|---|---|---|")
for i in items:
    if i['status']=='suspected': L.append(f"| {i['task_id']} | {i['reviewer_note']} | `{i['witness']['input'][:50]}` |")
L.append("\n## Reproduce\n```\ncd shuna-audit\npython3 src/audit.py      # ~1 min on 8 cores\npython3 src/triage.py\npython3 src/repro.py 31   # shows diff + witness for one task\n```\nFull diffs per item: `results/findings.json`.")
open('findings.md','w').write('\n'.join(L)); print(out['n_verified'],out['n_suspected'])
