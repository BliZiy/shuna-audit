"""Load a benchmark file into probe tasks {id, entry, ref, style, test | inputs, atol}.
Formats:
  humaneval     : HumanEval jsonl(.gz)  task_id, prompt, canonical_solution, entry_point, test (defines check(candidate))
  humanevalplus : EvalPlus HumanEval+ jsonl(.gz): + base_input/plus_input/atol -> io tests (expected = reference output)
  mbpp          : MBPP json/jsonl: task_id, code, test_list (+ test_imports)  -> module-level asserts
  mbppplus      : EvalPlus MBPP+ jsonl(.gz) -> io tests
  evoeval       : EvoEval jsonl(.gz): prompt, canonical_solution, entry_point, inputs (python literal strings) -> io tests
  generic       : one JSON object per line:
                  {"id": str, "entry_point": str, "reference": "<full reference program>",
                   "test_style": "check" | "asserts" | "io",
                   "test": "<test code>"            (check: defines check(candidate); asserts: module-level asserts on entry_point)
                   "inputs": [[arg1, arg2], ...], "atol": 0 (io only: expected output = reference(*args))}"""
import json, gzip, ast, math, warnings
warnings.filterwarnings('ignore', category=SyntaxWarning)
from shuna_probe._evalplus_mbpp import mbpp_deserialize_inputs

def _read(path):
    op = gzip.open if path.endswith('.gz') else open
    with op(path, 'rt') as f: txt = f.read()
    s = txt.lstrip()
    if s.startswith('['): return json.loads(s)
    return [json.loads(l) for l in txt.splitlines() if l.strip()]

def _entry_from_asserts(code, tests):
    names = [n.func.id for n in ast.walk(ast.parse(tests)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    defs = [n.name for n in ast.parse(code).body if isinstance(n, ast.FunctionDef)]
    return next((n for n in names if n in defs), defs[-1] if defs else None)

def _cap(inputs, cap):
    return inputs if not cap or len(inputs) <= cap else inputs[:cap]

def load(path, fmt, max_inputs=200):
    rows = _read(path); out = []
    for r in rows:
        if fmt == 'humaneval':
            out.append(dict(id=r['task_id'], entry=r['entry_point'], ref=r['prompt'] + r['canonical_solution'], style='check', test=r['test']))
        elif fmt in ('humanevalplus', 'mbppplus'):
            plus = r['plus_input'] if isinstance(r.get('plus_input'), list) else []
            base = list(r['base_input'])
            ins = base + plus[:max(0, max_inputs - len(base))] if max_inputs else base + plus
            if fmt == 'mbppplus': ins = mbpp_deserialize_inputs(r['task_id'], ins)   # restore tuples/sets/complex (EvalPlus)
            out.append(dict(id=r['task_id'], entry=r['entry_point'], ref=r['prompt'] + r['canonical_solution'], style='io',
                            inputs=ins, atol=r.get('atol') or 0))
        elif fmt == 'mbpp':
            code = r.get('code'); tests = '\n'.join(r.get('test_imports', []) + r['test_list'])
            e = _entry_from_asserts(code, tests)
            if e: out.append(dict(id=f"MBPP/{r['task_id']}", entry=e, ref=code, style='asserts', test=tests))
        elif fmt == 'evoeval':
            ins = []
            for s in r['inputs']:
                try: ins.append(list(eval('(' + s + ',)', {'inf': math.inf, 'nan': math.nan})))  # dataset literals, parsed as in adapters.py
                except Exception: pass
            out.append(dict(id=r['task_id'], entry=r['entry_point'], ref=r['prompt'].rstrip('\n') + '\n' + r['canonical_solution'],
                            style='io', inputs=_cap(ins, max_inputs), atol=0))
        elif fmt == 'generic':
            st = r.get('test_style', 'check')
            if st not in ('check', 'asserts', 'io'): raise ValueError(f"{r.get('id')}: test_style must be check|asserts|io")
            t = dict(id=str(r['id']), entry=r['entry_point'], ref=r['reference'], style=st)
            if st == 'io': t.update(inputs=_cap(r['inputs'], max_inputs), atol=r.get('atol', 0))
            else: t['test'] = r['test']
            out.append(t)
        else: raise ValueError(f'unknown format {fmt}')
    return out
