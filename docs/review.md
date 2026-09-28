# Table Sentry adversarial review

**Scope.** Independent review of the source, tests, README examples, isolated installation, and benchmark claims on Windows 11 / Python 3.12.10 (2026-09-28). This review does not reproduce the cited paper's abstract interpreter; it checks the narrower file-level diagnostic contract.

## Evidence run

- `python -m unittest discover -s tests -v`: **21 passed**, 0 skipped, 0 failed.
- `python benchmarks/run.py --output benchmarks/results-review.json`: **passed** for the planted-defect and clean-control cases, three repetitions each. The checked-in measurements are real process timings, not human-hour savings. In the planted case the median Table Sentry scan was 0.2146 s versus 0.0575 s for the lightweight baseline (about 3.7x slower); therefore this run does not support a time-saving claim.
- Fresh `pip install . --target <temporary-directory> --no-deps` from a directory outside the source, followed by `python -m table_sentry scan ...`: **passed** (exit 0, JSON report and stderr status line). The pre-existing `.tmp-install-2/bin/table-sentry.exe` is not a valid portable install: invoking it from the project produced `ModuleNotFoundError: No module named 'table_sentry'`. This appears to be a stale test artifact rather than a failure of a fresh pip target install.
- README scan and compare examples were exercised against `examples/train.csv` and `examples/test.jsonl`; the scan completed and the output is schema-valid. The exact README `--target label --id record_id --group subject --time observed_at` example reports the intended missingness/temporal findings.
- `--force` refusal/replacement and hardlink alias protection passed in the existing CLI tests. No input file was modified.

## Previously reported blocker, rechecked

The earlier review identified a mismatch between the implementation (strict identical JSONL key sets) and wording that treated absent keys as missing. The parent revision now consistently documents strict JSONL schema: every non-empty row must contain the same keys; an absent key is a schema error; explicit JSON `null` or an empty string represents missingness. The targeted two-line reproducer (`{"id":1,"x":"a"}` followed by `{"id":2}`) exits 2 with `inconsistent JSONL keys at line 2`, which is now the documented behavior. No blocker remains on this point.

## Important caveats (not blockers)

- The benchmark's `baseline.py` is a deliberately small CSV-only comparator; it is not a production data-quality tool and is not an apples-to-apples feature comparison. It does establish ground-truth counts for the planted rows and records raw CLI wall time for both processes, but it cannot establish user time saved.
- `compare_splits` reports `overlap_rate` over unique test keys (`len(overlap)/len(sb)`), while matching-row evidence separately counts duplicates. This is internally consistent with a unique-key rate but must stay explicitly documented to avoid readers interpreting it as a row-level overlap rate.
- Hashes are unsalted SHA-256 fingerprints as documented. They avoid emitting raw cell values but are not privacy protection for low-entropy identifiers.
- Association, temporal order, and split overlap are review heuristics; the docs correctly avoid causal-leakage claims.
- Citation metadata and README accurately describe inspiration and limitations; no claim of reproducing the Urban et al. abstract interpreter was found. A garbled Unicode rendering is visible in `README.md`/`CITATION.cff` for author names (`SubotiÄ‡`, `DrobnjakoviÄ‡`), which is a presentation-quality issue, not a technical result.

## Verdict

Core tests and the fresh isolated package workflow pass, and the benchmark is reproducible with honest ground-truth counts. The JSONL contract reconciliation is verified; the review gate is met.
