import json,sys,re
sys.path.insert(0,'src'); import adapters
for b in sys.argv[1:]:
    T={t['id']:t for t in adapters.BENCH[b]()}
    for x in json.load(open(f'results/{b}/debate.json')):
        if x['verdict']!='confirmed': continue
        w=x['witness']; t=T[x['task_id']]
        doc=re.findall(r'"""(.*?)"""',t['src'],re.S); doc=(doc[-1] if doc else t['src'][-600:]).strip().replace('\n',' ')
        dl=[l.strip() for l in w['diff'].splitlines() if l[:1] in '+-' and l[:3] not in('---','+++') and l[1:].strip()]
        print(f"## {x['task_id']} {t['entry']}\nDOC: {re.sub(' +',' ',doc)[:330]}\nDIFF: {' || '.join(dl)[-200:]}\nIN {w['input'][:150]} | REF {w['correct'][:80]} | WRONG {w['wrong'][:80]}\n")
