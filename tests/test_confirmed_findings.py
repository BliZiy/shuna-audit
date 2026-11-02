"""Regression suite: every 'verified' HumanEval finding must still reproduce.
For each finding: canonical passes official tests; the recorded mutant is rebuilt
from source, still passes official tests, and on the witness input returns the
recorded wrong output while canonical returns the recorded expected output."""
import ast, gzip, json, sys, pathlib, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src")); import sandbox; sandbox.enter()  # OpenShell
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import audit  # noqa
F = json.loads((ROOT / "results/findings.json").read_text())
TASKS = {t["task_id"]: t for t in map(json.loads, gzip.open(ROOT / "data/HumanEval.jsonl.gz", "rt"))}
VER = [f for f in F["findings"] if f["status"] == "verified"]

def test_dataset_hash_and_counts():
    import hashlib
    assert hashlib.sha256((ROOT / "data/HumanEval.jsonl.gz").read_bytes()).hexdigest() == F["data_sha256"]
    assert len(VER) == F["n_verified"] == 22
    assert sum(f["status"] == "suspected" for f in F["findings"]) == F["n_suspected"]

def rebuild_mutant(task, mutation):
    canon = task["prompt"] + task["canonical_solution"]
    tree = ast.parse(canon)
    for site in audit.mutation_sites(tree):
        if audit.describe(site) == mutation:
            return canon, audit.apply(tree, site)
    raise AssertionError(f"mutation {mutation} not found")

@pytest.mark.parametrize("f", VER, ids=[f["task_id"] for f in VER])
def test_finding_reproduces(f):
    task = TASKS[f["task_id"]]; w = f["witness"]; ep = task["entry_point"]
    canon, mut = rebuild_mutant(task, w["mutation"])
    assert audit.passes_tests(canon, task), "canonical must pass"
    assert audit.passes_tests(mut, task), "mutant must still pass official tests (finding = weak tests)"
    args = ast.literal_eval(w["input"])
    assert audit.run_quiet(audit.load_fn(canon, ep), args) == ("ok", w["expected_canonical"])
    ms, mv = audit.run_quiet(audit.load_fn(mut, ep), args)
    assert (mv if ms == "ok" else ms) == w["mutant_output"]
    assert mv != w["expected_canonical"]
