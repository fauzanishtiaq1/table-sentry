# Table Sentry contract

## Scope

Python 3.10+, standard library first. Read-only diagnostics for CSV and JSONL.
No automatic repair, network call, model/API key, or data upload. Exit status
0 means the scan completed (even if findings exist); 2 means invalid CLI/input;
3 means an internal scan error. Findings are diagnostics, not proof of leakage.

## Core API (`table_sentry/core.py`)

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

@dataclass(frozen=True)
class ScanOptions:
    target: str | None = None
    id_columns: tuple[str, ...] = ()
    time_column: str | None = None
    group_columns: tuple[str, ...] = ()
    overlap_keys: tuple[str, ...] = ()
    association_threshold: float = 0.98
    sample_limit: int = 20

def scan_file(path: str | Path, options: ScanOptions = ScanOptions()) -> dict[str, Any]: ...
def compare_splits(train: str | Path, test: str | Path,
                   options: ScanOptions = ScanOptions()) -> dict[str, Any]: ...
def render_json(result: Mapping[str, Any], *, indent: int = 2) -> str: ...
```

Implementations must not mutate inputs. CSV is UTF-8, preserves the first row as
the header, uses `csv.DictReader`, and rejects duplicate/empty headers and rows
with extra or missing fields. JSONL means one JSON object per non-empty line;
each object must be a mapping, and all records must have the same key set.
Malformed input is an exit-2 error with line number and no partial JSON result.
Missing values are exactly empty CSV fields, JSON `null`, or empty JSON strings;
they canonicalize to `__MISSING__` and are counted, never imputed. Strings are
Unicode NFC-normalized without trimming; numeric values use invariant decimal
form only when the complete field parses as finite decimal, otherwise strings.
`overlap_keys` defaults to sorted shared columns. Hashing uses SHA-256 over
length-prefixed UTF-8 canonical fields and never leaks raw cell values.

## JSON output schema

Top-level object: `schema_version` (`"1.0"`), `tool`, `input` (path basename,
format, row_count, columns), `summary` (finding_count, severity_counts,
completed_at_utc), `findings` (array), and `warnings` (array). Each finding has
`id`, `kind` (`schema`, `missingness`, `duplicate_rows`, `split_overlap`,
`suspicious_association`, `temporal_order`), `severity` (`info|warning|error`),
`message`, `evidence` (JSON-safe counts/column names/hashed keys), and
`recommendation`. `compare_splits` additionally has `splits` (train/test row
counts) and `overlap` (key_columns, overlap_count, overlap_rate).

## CLI

`python -m table_sentry scan INPUT [--target COL] [--id COL ...]
[--group COL ...] [--time COL] [--json OUT|-] [--pretty]`

`python -m table_sentry compare TRAIN TEST [--key COL ...] [--target COL]
[--json OUT|-] [--pretty]`

Repeated options may be supplied multiple times. `--json -` writes JSON to
stdout; otherwise output is UTF-8 to the requested new file and never overwrites
an existing file unless `--force` is explicitly supplied. Human summary goes to
stderr when JSON is stdout. Invalid paths, missing columns, malformed rows, or
unsupported extensions produce a concise stderr message and exit 2.

## Acceptance-critical semantics

Exact duplicate rows in one file are reported regardless of `group_columns`;
groups only annotate counts and cannot suppress a duplicate. A duplicate
finding reports duplicate row count and unique duplicated-key count. Cross-file
overlap compares canonicalized selected key values and reports unique overlap,
matching row counts, and `overlap_rate = overlapping unique keys / unique keys
in test`; it never reports row contents. `id_columns` are metadata unless
supplied as `--key`; `group_columns` are annotations, never implicit keys.

Categorical association warns when a non-target column uniquely determines the
target among at least 20 complete rows and at least two target classes. Numeric
association warns with at least 30 complete pairs and absolute Pearson
correlation at least 0.98; constant/non-finite columns are skipped. These are
review heuristics, not proof of leakage. Temporal checks parse ISO-8601,
RFC3339 offsets, or numeric Unix seconds; unparseable values count as missing.
They report out-of-order timestamps within each configured group and never drop
rows. Findings and keys are sorted by kind, column, and stable hash.

JSONL schema is strict: each non-empty row must contain the same keys. An absent key is a schema error, not an imputed null. Use explicit JSON `null` or an empty string for a missing cell.
