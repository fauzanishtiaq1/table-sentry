import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = self.d / name; p.write_text(text, encoding="utf-8", newline=""); return p

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "table_sentry", *map(str, args)], cwd=ROOT, text=True, capture_output=True)

    def test_missing_is_empty_or_null_not_literal_sentinel(self):
        p = self.write("missing.csv", "id,value\n1,\n2,__MISSING__\n")
        r = self.cli("scan", p, "--json", "-")
        self.assertEqual(r.returncode, 0, r.stderr)
        obj = json.loads(r.stdout)
        miss = [f for f in obj["findings"] if f["kind"] == "missingness"]
        self.assertEqual({f["evidence"]["column"]: f["evidence"]["missing_count"] for f in miss}, {"value": 1})

    def test_numeric_equivalence_and_precision(self):
        p = self.write("numbers.csv", "x\n1\n1.0\n1e0\n0.1000000000000000000001\n")
        r = self.cli("scan", p, "--json", "-")
        self.assertEqual(r.returncode, 0, r.stderr)
        # Equal decimal spellings are canonicalized, while nearby high precision values remain distinct.
        from table_sentry.core import _canon, _hash
        self.assertEqual(_canon("1"), _canon("1.0")); self.assertEqual(_canon("1e0"), _canon("1"))
        self.assertNotEqual(_canon("0.1000000000000000000001"), _canon("0.1"))
        self.assertEqual(len(_hash(["1"])), 64)

    def test_overlap_unique_keys_and_row_counts_cross_format(self):
        train = self.write("train.csv", "id,score\na,1\na,2\nb,3\n")
        test = self.write("test.jsonl", '{"id":"a","label":9}\n{"id":"c","label":4}\n')
        r = self.cli("compare", train, test, "--key", "id", "--json", "-")
        self.assertEqual(r.returncode, 0, r.stderr); obj = json.loads(r.stdout)
        self.assertEqual(obj["overlap"]["overlap_count"], 1)
        finding = next(f for f in obj["findings"] if f["kind"] == "split_overlap")
        self.assertEqual(finding["evidence"]["train_matching_rows"], 2)
        self.assertEqual(finding["evidence"]["test_matching_rows"], 1)

    def test_malformed_headers_and_options_are_exit_two(self):
        for text in ("a,a\n1,2\n", ",b\n1,2\n", "a,b\n1\n"):
            p = self.write("bad.csv", text); r = self.cli("scan", p, "--json", "-")
            self.assertEqual(r.returncode, 2); self.assertEqual(r.stdout, "")
        p = self.write("ok.csv", "a\n1\n")
        r = self.cli("scan", p, "--target", "absent", "--json", "-"); self.assertEqual(r.returncode, 2)

    def test_association_positive_and_constant_legitimate_negative(self):
        lines = ["feature,target"] + [f"g{i//2},{(i//2)%2}" for i in range(40)]
        leak = self.write("leak.csv", "\n".join(lines) + "\n")
        r = self.cli("scan", leak, "--target", "target", "--json", "-"); self.assertEqual(r.returncode, 0)
        self.assertTrue(any(f["kind"] == "suspicious_association" for f in json.loads(r.stdout)["findings"]))
        clean = self.write("clean.csv", "group,target\n" + "\n".join(f"g{i//2},0" for i in range(40)) + "\n")
        r = self.cli("scan", clean, "--target", "target", "--json", "-"); self.assertEqual(r.returncode, 0)
        self.assertFalse(any(f["kind"] == "suspicious_association" for f in json.loads(r.stdout)["findings"]))

    def test_unix_and_iso_time_ordering(self):
        p = self.write("time.csv", "group,t\na,1704067201\na,1704067200\n")
        r = self.cli("scan", p, "--time", "t", "--group", "group", "--json", "-")
        self.assertEqual(r.returncode, 0); self.assertTrue(any(f["kind"] == "temporal_order" for f in json.loads(r.stdout)["findings"]))
        q = self.write("iso.csv", "group,t\na,2024-01-01T00:00:00Z\na,2024-01-01T00:01:00Z\n")
        r = self.cli("scan", q, "--time", "t", "--group", "group", "--json", "-"); self.assertEqual(r.returncode, 0)
        self.assertFalse(any(f["kind"] == "temporal_order" for f in json.loads(r.stdout)["findings"]))

    def test_scan_is_read_only(self):
        p = self.write("readonly.csv", "id\n1\n2\n")
        before = hashlib.sha256(p.read_bytes()).digest(); r = self.cli("scan", p, "--json", "-"); self.assertEqual(r.returncode, 0)
        self.assertEqual(before, hashlib.sha256(p.read_bytes()).digest())

if __name__ == "__main__": unittest.main()
