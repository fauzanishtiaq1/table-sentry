import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).parents[1]
def run_cli(*args):
    return subprocess.run([sys.executable, '-m', 'table_sentry', *map(str,args)], cwd=ROOT, text=True, capture_output=True, env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING='utf-8'))
class CliTests(unittest.TestCase):
    def test_scan_json_stdout_and_stderr(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'данные spaced.csv'; p.write_text('id,target,group\n1,yes,A\n2,no,A\n2,no,A\n',encoding='utf-8')
            r=run_cli('scan',p,'--id','id','--group','group','--pretty'); self.assertEqual(r.returncode,0,r.stderr)
            x=json.loads(r.stdout); self.assertEqual(x['input']['row_count'],3); self.assertGreaterEqual(x['summary']['finding_count'],1); self.assertIn('scanned',r.stderr)
    def test_compare_and_output_safety(self):
        with tempfile.TemporaryDirectory() as d:
            q=Path(d); a=q/'train.csv'; b=q/'test.csv'; o=q/'reports'/'result.json'; a.write_text('id,value\n1,a\n2,b\n'); b.write_text('id,value\n2,b\n3,c\n')
            self.assertEqual(run_cli('compare',a,b,'--key','id','--json',o).returncode,0); self.assertEqual(json.loads(o.read_text())['overlap']['overlap_count'],1)
            self.assertEqual(run_cli('compare',a,b,'--key','id','--json',o).returncode,2); self.assertEqual(run_cli('compare',a,b,'--key','id','--json',o,'--force').returncode,0)
    def test_input_alias_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'input.csv'; b=Path(d)/'alias.csv'; a.write_text('id\n1\n')
            try: b.hardlink_to(a)
            except OSError: b.symlink_to(a)
            self.assertEqual(run_cli('scan',a,'--json',b,'--force').returncode,2); self.assertEqual(a.read_text(),'id\n1\n')
    def test_bad_path_is_concise_exit_two(self):
        with tempfile.TemporaryDirectory() as d: r=run_cli('scan',Path(d)/'missing file.csv')
        self.assertEqual(r.returncode,2); self.assertIn('not a file',r.stderr); self.assertNotIn('Traceback',r.stderr)
