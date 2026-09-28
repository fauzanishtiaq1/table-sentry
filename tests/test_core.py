import json, unittest
from pathlib import Path
from table_sentry.core import *

def _csv(p, text): p.write_text(text, encoding="utf-8", newline="")

class CoreTests(unittest.TestCase):
  def setUp(self):
    import tempfile
    self.tmp=tempfile.TemporaryDirectory(); self.d=Path(self.tmp.name)
  def tearDown(self): self.tmp.cleanup()
  def test_overlap_counts_and_rate(self):
    a=self.d/"a.csv"; b=self.d/"b.csv"
    _csv(a,"id,y\n1,a\n2,b\n2,c\n"); _csv(b,"id,y\n2,z\n3,q\n")
    r=compare_splits(a,b,ScanOptions(overlap_keys=("id",)))
    self.assertEqual(r["overlap"]["overlap_count"],1); self.assertEqual(r["overlap"]["overlap_rate"],.5)
    self.assertNotIn('"2"', render_json(r))

  def test_duplicates_not_suppressed_by_groups(self):
    p=self.d/"x.csv"; _csv(p,"g,v\na,1\na,1\nb,2\n")
    f=[x for x in scan_file(p,ScanOptions(group_columns=("g",)))["findings"] if x["kind"]=="duplicate_rows"][0]
    self.assertEqual(f["evidence"]["duplicate_row_count"],1); self.assertEqual(f["evidence"]["unique_duplicated_keys"],1)

  def test_association_positive_and_constant_negative(self):
    p=self.d/"x.csv"; _csv(p,"x,y\n"+"".join(f"{i},{i}\n" for i in range(30))); self.assertTrue(any(f["kind"]=="suspicious_association" for f in scan_file(p,ScanOptions(target="y"))["findings"]))
    q=self.d/"q.csv"; _csv(q,"x,y\n"+"".join(f"1,{i%2}\n" for i in range(30))); self.assertFalse(any(f["kind"]=="suspicious_association" for f in scan_file(q,ScanOptions(target="y"))["findings"]))

  def test_malformed_and_nonfinite(self):
    p=self.d/"bad.jsonl"; p.write_text('{"a": 1}\n{"a": 2, "b": 3}\n',encoding="utf-8")
    with self.assertRaisesRegex(ValueError,"inconsistent"): scan_file(p)

  def test_json_serialization_does_not_mutate(self):
    p=self.d/"x.jsonl"; p.write_text('{"a":null,"b":"Ã©"}\n',encoding="utf-8")
    r=scan_file(p); before=json.loads(json.dumps(r,default=str)); self.assertEqual(json.loads(render_json(r)),before)

  def test_canonicalization_missing_null_and_numbers(self):
    from table_sentry.core import _canon
    self.assertNotEqual(_canon(None), _canon("__MISSING__")); self.assertEqual(_canon(""), _canon(None))
    self.assertEqual(_canon("1.0"), _canon("1")); self.assertEqual(_canon("1e3"), _canon("1000"))

  def test_repeated_feature_association_and_unique_id_control(self):
    p=self.d/"x.csv"; _csv(p,"x,y\n"+"".join(f"{i%3},{i%2}\n" for i in range(30)))
    self.assertFalse(any(f["kind"]=="suspicious_association" for f in scan_file(p,ScanOptions(target="y"))["findings"]))
    q=self.d/"q.csv"; _csv(q,"x,y\n"+"".join(f"a,{i%2}\n" for i in range(30))); self.assertFalse(any(f["kind"]=="suspicious_association" for f in scan_file(q,ScanOptions(target="y"))["findings"]))

  def test_time_bad_only_and_schema_order(self):
    p=self.d/"t.csv"; _csv(p,"t,x\nbad,1\n")
    self.assertEqual([f for f in scan_file(p,ScanOptions(time_column="t"))["findings"] if f["kind"]=="temporal_order"][0]["evidence"]["unparseable_count"],1)
    a=self.d/"a.csv"; b=self.d/"b.csv"; _csv(a,"id,x\n1,a\n"); _csv(b,"x,id\na,1\n")
    self.assertEqual(compare_splits(a,b,ScanOptions(overlap_keys=("id",)))["overlap"]["overlap_count"],1)

  def test_missingness_precision_and_numeric_time(self):
    from table_sentry.core import _canon
    self.assertNotEqual(_canon("1234567890123456789012345678901"), _canon("1234567890123456789012345678902"))
    self.assertEqual(_canon("1.00"),_canon("1e0"))
    p=self.d/"empty.csv"; _csv(p,"id,value,time\n1,,100\n2,ok,101\n")
    result=scan_file(p,ScanOptions(time_column="time"))
    self.assertEqual(next(f["evidence"]["missing_count"] for f in result["findings"] if f["kind"]=="missingness"),1)
    self.assertFalse(any(f["kind"]=="temporal_order" for f in result["findings"]))

  def test_shared_columns_across_formats(self):
    a=self.d/"a.csv"; b=self.d/"b.jsonl"
    _csv(a,"id,feature\n1,old\n")
    b.write_text('{"id":1,"other":"different"}\n',encoding="utf-8")
    self.assertEqual(compare_splits(a,b)["overlap"]["overlap_count"],1)
