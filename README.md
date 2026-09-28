# Table Sentry

Deterministic, read-only diagnostics for CSV and JSONL/NDJSON tables. It finds
exact duplicate rows, missingness, schema problems, train/test key overlap,
review-level suspicious feature associations, and out-of-order timestamps.
Output is portable JSON for CI or human review.

No data is uploaded and there is no model, API key, database, or automatic repair.
Findings are diagnostics, **not proof of causal leakage**. Review each finding in
the data-generating pipeline.

## Install

Python 3.10+ is required:

```bash
git clone https://github.com/fauzanishtiaq1/table-sentry.git
cd table-sentry
python -m venv .venv
# macOS/Linux: . .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
```

Runtime dependencies are empty. Both forms expose the same CLI:

```bash
table-sentry --help
python -m table_sentry --help
```

## Quick start

```bash
table-sentry scan examples/train.csv --target label --id record_id --group subject --time observed_at --pretty
table-sentry scan examples/train.csv --json train-report.json --pretty
table-sentry compare examples/train.csv examples/test.jsonl --key record_id --json split-report.json --pretty
```

JSON goes to stdout by default; the status line goes to stderr. Repeated options
are allowed (`--key site --key subject_id`). Without `--key`, compare uses sorted
shared columns; select the identifier manually when that is not your split key.
`--force` is required to replace an existing output. Inputs are never modified,
including aliases and hard links.

## Output and semantics

Successful output contains `schema_version`, `tool`, `input`, `summary`,
`findings`, and `warnings`; compare additionally contains `splits` and `overlap`.
Findings contain `id`, `kind`, `severity`, `message`, `evidence`, and
`recommendation`. Evidence uses counts and stable hashes, not raw cell values.
Hashes are unsalted SHA-256 comparison fingerprints, **not a secrecy guarantee**.

- Empty CSV fields, JSON `null`, and empty JSON strings are missing and are counted,
  never imputed. A literal sentinel string is not missing.
- Exact duplicates are reported even with `--group`; groups annotate only.
  `--id` is metadata and is not an overlap key unless passed as `--key`.
- Association and time findings are review heuristics, not proof of leakage.
- Malformed CSV/JSONL yields concise stderr and no partial report.

Exit status: 0 completed (findings may exist), 2 invalid input/arguments, 3
unexpected internal error.

## Python API

```python
from table_sentry import ScanOptions, compare_splits, render_json, scan_file

options = ScanOptions(target="outcome", id_columns=("subject_id",),
                      group_columns=("site",), time_column="collected_at")
report = scan_file("data/train.csv", options)
print(render_json(report))
split_report = compare_splits("data/train.csv", "data/test.csv",
                              ScanOptions(overlap_keys=("subject_id",)))
```

See [`docs/usage.md`](docs/usage.md) for CI and interpretation guidance.

## Research basis and limitations

The file-level checks are inspired by *Static analysis by abstract interpretation
against data leakage in machine learning* (Urban, Subotić, and Drobnjaković,
2025, DOI [10.1016/j.scico.2025.103338](https://doi.org/10.1016/j.scico.2025.103338)).
That paper addresses program-level provenance; Table Sentry does **not** reproduce
its abstract interpreter or prove arbitrary pipeline properties. Optional time
checks are motivated by TabReD's time-based evaluation discussion
([arXiv:2406.19380](https://arxiv.org/abs/2406.19380)). No benchmark or human
time-saving claim is made here unless measured in a published run.

## License

MIT; see [`LICENSE`](LICENSE). Citation metadata is in [`CITATION.cff`](CITATION.cff).

## Reproduce the checks

Run `python -m unittest discover -s tests -v` and `python benchmarks/run.py --output benchmarks/results.json`. The checked-in measurements use planted synthetic defects and a clean control, not a human time study.

JSONL schema is strict: each non-empty row must contain the same keys. An absent key is a schema error, not an imputed null. Use explicit JSON `null` or an empty string for a missing cell.
