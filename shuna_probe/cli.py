"""CLI: python -m shuna_probe <tasks.jsonl> --format humaneval|humanevalplus|mbpp|mbppplus|evoeval|generic [options]
Runs exploit stubs (and the reference solution as a false-flag control, plus optional --solutions) under graders
G1-G4, prints a per-grader table and writes evidence: <out>/evidence.jsonl (one line per task x candidate),
<out>/summary.json, <out>/table.md. Offline, CPU-only; all candidate code runs in child processes inside the
OpenShell sandbox (audit/src/sandbox.py) unless --sandbox=host / SHUNA_SANDBOX=host."""
import os, sys, shutil
PKG = os.path.dirname(os.path.abspath(__file__)); AUDIT = os.path.dirname(PKG)
sys.path.insert(0, AUDIT); sys.path.insert(0, os.path.join(AUDIT, 'src'))

def _prepare_for_sandbox():
    """Make argv sandbox-mappable before sandbox.enter(): entrypoint under audit/, file args copied under audit/results/."""
    sys.argv[0] = os.path.join(PKG, '__main__.py')
    inbox = os.path.join(AUDIT, 'results', '_probe_inputs')
    for i, a in enumerate(sys.argv[1:], 1):
        prev = sys.argv[i - 1]
        if a.startswith('-') or prev in ('--format', '--exploits', '--graders', '--jobs', '--max-inputs', '--limit', '--timeout', '--name'): continue
        if prev == '--out':
            p = os.path.abspath(a)
            if not p.startswith(os.path.join(AUDIT, 'results') + os.sep) and os.environ.get('SHUNA_SANDBOX') != 'host' and '--sandbox=host' not in sys.argv:
                raise SystemExit('shuna_probe: --out must be under audit/results/ (only results/ is copied back from the sandbox)')
            sys.argv[i] = p; continue
        if os.path.isfile(a):
            p = os.path.abspath(a)
            if not p.startswith(AUDIT + os.sep):
                os.makedirs(inbox, exist_ok=True); q = os.path.join(inbox, os.path.basename(p)); shutil.copy(p, q); p = q
            sys.argv[i] = p

def _work(args):
    from shuna_probe import core
    t, cname, sol, graders, timeout = args
    g = core.grade(t, sol, graders, timeout)
    return dict(id=t['id'], candidate=cname, **g)

def run(tasks, exploits, graders, jobs=4, timeout=10, solutions=None, reference=True):
    from shuna_probe import core
    from multiprocessing import Pool
    jobs_list = []
    for t in tasks:
        if reference: jobs_list.append((t, 'reference', t['ref'], graders, timeout))
        for k in exploits: jobs_list.append((t, k, core.stub(t['entry'], k), graders, timeout))
        if solutions and t['id'] in solutions: jobs_list.append((t, 'solution', solutions[t['id']], graders, timeout))
    with Pool(jobs) as p: rows = p.map(_work, jobs_list, chunksize=4)
    return rows

def summarize(rows, graders):
    cands = []; [cands.append(r['candidate']) for r in rows if r['candidate'] not in cands]
    s = {}
    for c in cands:
        rs = [r for r in rows if r['candidate'] == c]
        s[c] = dict(n=len(rs), **{g: sum(bool(r.get(g)) for r in rs) for g in graders})
    return s

def table(name, summary, graders):
    lines = [f'| {name} | n | ' + ' | '.join(graders) + ' |', '|---|---|' + '---|' * len(graders)]
    for c, v in summary.items():
        cells = [f"{v[g]} ({100 * v[g] / v['n']:.1f}%)" if v['n'] else '-' for g in graders]
        lines.append(f"| {c} | {v['n']} | " + ' | '.join(cells) + ' |')
    return '\n'.join(lines)

def main(argv=None):
    as_command = argv is None                      # console script / python -m: return None so sys.exit(main()) exits 0
    if argv is None:
        _prepare_for_sandbox()
        import sandbox; sandbox.enter()            # re-runs this CLI inside a fresh OpenShell sandbox (or host fallback)
        argv = sys.argv[1:]
    import argparse, json, time
    from shuna_probe import core, loaders
    ap = argparse.ArgumentParser(prog='shuna_probe', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('tasks'); ap.add_argument('--format', required=True, choices=['humaneval', 'humanevalplus', 'mbpp', 'mbppplus', 'evoeval', 'generic'])
    ap.add_argument('--name', help='label for the table/output dir (default: file stem)')
    ap.add_argument('--out', help='output dir (default audit/results/probe/<name>)')
    ap.add_argument('--exploits', default=','.join(core.EXPLOITS), help='comma list; available: ' + ','.join(core.EXPLOITS))
    ap.add_argument('--graders', default=','.join(core.GRADERS))
    ap.add_argument('--solutions', help='optional jsonl {"id":..., "solution": "<program>"} graded as candidate "solution"')
    ap.add_argument('--no-reference', action='store_true', help='skip the reference false-flag control')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 2); ap.add_argument('--timeout', type=float, default=10)
    ap.add_argument('--max-inputs', type=int, default=200, help='cap io-style inputs per task (0 = all)')
    ap.add_argument('--limit', type=int, default=0, help='only the first N tasks')
    a = ap.parse_args(argv)
    name = a.name or os.path.basename(a.tasks).split('.')[0]
    out = a.out or os.path.join(AUDIT, 'results', 'probe', name); os.makedirs(out, exist_ok=True)
    tasks = loaders.load(a.tasks, a.format, a.max_inputs)
    if a.limit: tasks = tasks[:a.limit]
    exploits = [x for x in a.exploits.split(',') if x]; graders = tuple(g for g in a.graders.split(',') if g)
    bad = [x for x in exploits if x not in core.EXPLOITS] + [g for g in graders if g not in core.GRADERS]
    if bad: raise SystemExit(f'unknown exploit/grader: {bad}')
    sols = None
    if a.solutions: sols = {r['id']: r['solution'] for r in loaders._read(a.solutions)}
    t0 = time.time()
    rows = run(tasks, exploits, graders, a.jobs, a.timeout, sols, not a.no_reference)
    summ = summarize(rows, graders)
    with open(os.path.join(out, 'evidence.jsonl'), 'w') as f:
        for r in rows: f.write(json.dumps(r) + '\n')
    meta = dict(name=name, tasks_file=os.path.basename(a.tasks), format=a.format, n_tasks=len(tasks), graders=graders,
                exploits={k: core.EXPLOITS[k][0] for k in exploits}, max_inputs=a.max_inputs, seconds=round(time.time() - t0, 1),
                sandbox='openshell' if os.environ.get('SHUNA_IN_SANDBOX') == '1' else 'host', summary=summ)
    json.dump(meta, open(os.path.join(out, 'summary.json'), 'w'), indent=1)
    tb = table(name, summ, graders); open(os.path.join(out, 'table.md'), 'w').write(tb + '\n')
    print(tb); print(f"\n{len(tasks)} tasks, {len(rows)} gradings, {meta['seconds']}s, sandbox={meta['sandbox']}; evidence: {os.path.relpath(out, AUDIT)}/evidence.jsonl", flush=True)
    return None if as_command else meta

if __name__ == '__main__': main()
