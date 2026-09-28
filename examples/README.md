# Table Sentry examples

Run from this directory's parent:

```powershell
python -m table_sentry scan examples/train.csv --target label --time observed_at --group subject --pretty --json -
python -m table_sentry compare examples/train.csv examples/test.jsonl --key record_id --json -
```

The fixtures intentionally contain missingness, a timestamp ordering issue, and a
train/test key collision. Findings are review signals, not proof of leakage; shared
keys can be legitimate and association is correlational rather than causal.
