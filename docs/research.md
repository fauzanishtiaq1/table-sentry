# Table Sentry research basis

## Product decision

Table Sentry is a local, read-only CSV/JSONL data-quality and split-leakage
diagnostic. It emits actionable findings, but never edits input data or claims
that a suspicious column is causal leakage. The first release deliberately
targets tabular files and standard-library Python so it works without a paid
service, database, or model download.

## Primary research basis

The strongest directly actionable recent source found is **Static analysis by
abstract interpretation against data leakage in machine learning** by Caterina
Urban, Pavle Subotić, and Filip Drobnjaković, *Science of Computer Programming*
246 (December 2025), article 103338, DOI 10.1016/j.scico.2025.103338
(publisher page:
<https://www.sciencedirect.com/science/article/pii/S0167642325000772>). The
paper describes tracking the origin of data used for training and testing and
checking that the sources are disjoint and untainted; it distinguishes
train/test contamination and target leakage. Table Sentry implements the
file-level analogue: deterministic row fingerprints detect exact overlap
between explicitly supplied train/test files, while schema/provenance metadata
and high-association feature diagnostics produce reviewable target-leakage
signals. It does **not** claim to prove arbitrary Python-pipeline provenance,
which requires the paper's program-level analysis and is outside a CSV tool.

As corroborating evidence that leakage can materially inflate apparent model
quality, **Data leakage inflates prediction performance in connectome-based
machine learning models** (Nature Communications, 2024, DOI
10.1038/s41467-024-46150-w) explicitly discusses evaluating on unseen data and
reports leakage-related inflation in a real ML workflow:
<https://www.nature.com/articles/s41467-024-46150-w>. This is domain-specific,
so it motivates the warning and benchmark design but is not treated as a
general effect-size claim for this tool.

The primary **TabReD** preprint (Rubachev, Kartashev, Gorishniy, Babenko, arXiv
2406.19380, 2024; subsequently ICLR 2025) finds that realistic tabular applications
require distribution drift and time-based evaluation, not only random splits:
<https://arxiv.org/abs/2406.19380>. Table
Sentry therefore reports optional temporal-order checks when a user supplies a
time column, but it does not silently choose a split for the user.

## Competing tools and honest differentiation

- Great Expectations and Pandera provide expressive schema/data contracts, but
  require third-party dependencies and are primarily user-authored assertions;
  Table Sentry is a zero-dependency, one-command triage report with automatic
  duplicate/split-overlap and suspicious-feature diagnostics.
- Deequ/SQL data-quality systems are useful at warehouse scale, but require a
  JVM or query engine. Table Sentry is for a small/medium local file and emits
  portable JSON that CI can archive.
- ydata-profiling and DataPrep produce rich profiles, but do not specialize in
  train/test overlap or leakage-oriented review. Table Sentry is intentionally
  narrower and deterministic.

These are positioning observations, not a claim of novel algorithms or a
benchmark against those projects. Their code/data are not redistributed.

## Rights and reproducibility

The cited papers are used only as scholarly references; no paper text, code,
weights, or datasets are bundled. The tool's original implementation can be
MIT-licensed. Users must have rights to the CSV/JSONL files they scan. The
SciDirect/Nature/Papers With Code pages are source links, not permission to
copy publisher assets. No patent-clearance or scientific-validity guarantee is
made.

## Useful benchmark (fixed before implementation)

`benchmarks/run.py` must generate a deterministic synthetic dataset
under a temporary directory with: (1) exact duplicate train/test rows, (2) a
near-duplicate identifier column, (3) a post-outcome feature highly associated
with the target, (4) legitimate repeated measurements grouped by `subject_id`
where every selected overlap key differs by timestamp (groups do not excuse
exact duplicate keys),
and (5) a benign continuous feature. It runs the same CLI twice: a baseline
manual script that checks only row counts and nulls, and Table Sentry. Report
wall-clock seconds from `time.perf_counter`, findings by seeded defect type,
and false positives on the legitimate repeated-measurement control. The output
must include the raw command, Python version, row counts, and machine details;
do not state human time savings or percentages unless actually measured. The
acceptance target is detection of every injected exact-overlap defect and
presence of a review-level warning for the injected suspicious feature, with
zero duplicate-overlap finding on the control after grouping is configured.
