# Usage guide

Table Sentry reads only named local files and writes JSON to stdout or a new path.

## Scan and compare

```bash
python -m table_sentry scan data/train.csv --target label --id subject_id --group site --time observed_at --json reports/train.json --pretty
python -m table_sentry compare data/train.csv data/test.csv --key subject_id --json reports/split.json --pretty
```

`overlap` reports selected `key_columns`, unique `overlap_count`, and
`overlap_rate` (overlapping unique keys divided by unique test keys). It reports
hashes and counts, not row contents. Always pass `--key` when an entity identifier
is known. `.ndjson` is accepted as `.jsonl`.

## CI

```bash
python -m pip install .
python -m table_sentry scan data/train.csv --target label --json reports/train.json
python -m table_sentry compare data/train.csv data/test.csv --key subject_id --json reports/split.json
```

Exit 0 means diagnostics completed; CI may apply its own policy to findings.
Malformed input or invalid paths return 2. The tool never silently repairs data.

## Interpretation

`duplicate_rows` means exact canonical rows repeat; repeated measurements may be
legitimate. Groups annotate but never suppress duplicates. `suspicious_association`
is a review signal under minimum sample requirements, not causal leakage; check
feature availability at prediction time. `temporal_order` reports out-of-order
timestamps within configured groups and never drops records.

Missingness is literal: empty fields, JSON `null`, and empty JSON strings count as
missing; a string sentinel remains a value. Unsalted SHA-256 hashes are stable
comparison fingerprints, not anonymization.

## Python API

```python
from table_sentry import ScanOptions, compare_splits, scan_file

report = scan_file("data/train.jsonl", ScanOptions(target="label", id_columns=("subject_id",)))
comparison = compare_splits("data/train.csv", "data/test.csv",
                            ScanOptions(overlap_keys=("subject_id",)))
```

Returned values are JSON-safe dictionaries; use `render_json(value, indent=2)` for
deterministic serialization.

JSONL schema is strict: each non-empty row must contain the same keys. An absent key is a schema error, not an imputed null. Use explicit JSON `null` or an empty string for a missing cell.
