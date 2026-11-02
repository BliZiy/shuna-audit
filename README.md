# Shuna Audit: Reward Integrity Leaderboard

An open audit of the **graders** (unit tests) of public AI coding benchmarks. We list every task where the official tests give full marks to a program that is wrong, along with a witness input, the correct output, the wrong output and the diff.

Maintained by BliZi (Shuna). Contact: shuna@mail.grokbot.com

## Headline numbers (method v3, frozen Oct 18, 2026)
| Benchmark | Tasks | Confirmed weak-test tasks | Helper-only | Suspected | Rejects a correct solution |
|---|---|---|---|---|---|
| HumanEval Pro | 164 | **40** (24%) | 3 | 8 | 0 |
| MBPP Pro | 378 | **25** (7%) | 14 | 19 | 3 (exact float equality: 36, 117, 260) |
| BigCodeBench-Lite Pro | 57 | **2** (213, 897) | 0 | 0 | 1 (551: expected values only hold in UTC+8) |
| HumanEval | 164 | 20 | 6 | 4 | 0 |
| MBPP | 427 | 53 | 11 | 17 | 0 |
| HumanEval+ / MBPP+ | 164 / 378 | 2 / 11 | 0 | 0 | 0 |
| HumanEvalNext (82 public) | 82 | 7 | 0 | 0 | 0 |
| EvoEval Creative / Subtle / Tool-Use / Difficult / Combine | 100 each | 7 / 1 / 12 / 6 / 5 | 0 | 0 | 0 |
| **Total** | | **191** | | | |

**Confirmed** = a wrong program passes all official tests, it survives an adversarial prosecutor/defender review, and it is backed by the EvalPlus oracle or a documented manual review (`data/manual_review.json`). "Confirmed" means confirmed by our oracle/manual review, not by independent experts.

## Score impact
We measured how much these weak tests inflate model scores (Kaggle run, Oct 20, 2026). Those numbers will be published on **Nov 5, 2026**.

## Caveats
Small samples; confidence intervals overlap; scores move by a few points at most. Some findings may turn out to be acceptable test behavior. Maintainers can dispute any item (open an issue) and we will mark it disputed/withdrawn rather than delete it.

## Disclosure
HumanEval Pro / MBPP Pro / BCB-Lite Pro authors were notified privately on Oct 18, 2026 (count correction Oct 19) with 14 days' notice before publication.

## Layout
- `data/findings.json`: every item per benchmark (status, witness, correct vs. wrong output, diff)
- `results/<benchmark>/`: raw mutation, oracle and debate outputs
- `site/`: static leaderboard (open `site/index.html`)
- `src/`: pipeline (`audit2.py` → `oracle.py` → `debate.py` → `build_findings_v2.py` → `build_site.py`); `src/repro.py` reproduces a task
- `shuna_probe/`: grader exploit probe (see its docstring); `tests/`: regression tests

Code that runs mutant/model code calls `src/sandbox.py` first; run it inside a sandbox or container. Use `SHUNA_SANDBOX=host` only at your own risk.

## License
Code: MIT. Our data and annotations: CC BY 4.0. Benchmark task text belongs to the original benchmarks under their own licenses.
