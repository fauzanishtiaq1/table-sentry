import argparse,csv,json,platform,statistics,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def write(p,rows):
 with p.open('w',newline='',encoding='utf-8') as f: csv.DictWriter(f,fieldnames=list(rows[0])).writeheader();csv.DictWriter(f,fieldnames=list(rows[0])).writerows(rows)
def call(a):
 t=time.perf_counter();p=subprocess.run([sys.executable,*map(str,a)],cwd=ROOT,text=True,capture_output=True);return p,time.perf_counter()-t
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',default='benchmarks/results.json');x=ap.parse_args();n=10000
 with tempfile.TemporaryDirectory() as td:
  d=Path(td);train=[{'record_id':f'id-{i}','subject':f's-{i%50}','observed_at':str(1700000000+i),'target':str((i//2)%2),'feature':str(i//2)} for i in range(n//2)];test=[{'record_id':f'id-{i+n//2}','subject':f's-{i%50}','observed_at':str(1700005000+i),'target':str((i//2)%2),'feature':str(i//2)} for i in range(n//2)];test[0]['record_id']='id-10';test[10]['record_id']='id-11';test[20]['observed_at']='1690000000';test[30]['feature']='';test.append(test[40].copy());clean=[{'record_id':f'clean-{i}','subject':f's-{i%50}','observed_at':str(1700000000+i),'target':'0','feature':str(i%5)} for i in range(n)];write(d/'train.csv',train);write(d/'test.csv',test);write(d/'clean.csv',clean);cases=[]
  for name,path,truth in [('planted-defects',d/'test.csv',{'rows':5001,'missingness':1,'duplicate_rows':1,'suspicious_association':3,'temporal_order':1,'missing_cells':1,'duplicate_extra_rows':1,'out_of_order_rows':1,'unique_overlap_keys':2}),('clean-control',d/'clean.csv',{'rows':10000,'missingness':0,'duplicate_rows':0,'suspicious_association':0,'temporal_order':0,'missing_cells':0,'duplicate_extra_rows':0,'out_of_order_rows':0,'unique_overlap_keys':0})]:
   ts=[];bs=[];overlap_runs=[]
   for i in range(3):
    p,sec=call(['-m','table_sentry','scan',path,'--target','target','--time','observed_at','--group','subject','--json','-']);assert p.returncode==0,p.stderr;o=json.loads(p.stdout);k=[f['kind'] for f in o['findings']];ts.append({'missingness':k.count('missingness'),'duplicate_rows':k.count('duplicate_rows'),'suspicious_association':k.count('suspicious_association'),'temporal_order':k.count('temporal_order'),'runtime_seconds':sec});q=d/f'b{i}.json';p,sec=call(['benchmarks/baseline.py',path,'--train',d/'train.csv','--output',q]);assert p.returncode==0,p.stderr;b=json.loads(q.read_text());b['runtime_seconds']=sec;bs.append(b)
   for repetition in range(3):
    cp,elapsed=call(['-m','table_sentry','compare',d/'train.csv',path,'--key','record_id','--json','-'])
    assert cp.returncode==0,cp.stderr
    comparison=json.loads(cp.stdout)
    assert comparison['overlap']['overlap_count']==truth['unique_overlap_keys']
    overlap_runs.append({'unique_overlap_keys':comparison['overlap']['overlap_count'],'seconds':elapsed})
   assert all(t[x]==truth[x] for t in ts for x in ('missingness','duplicate_rows','suspicious_association','temporal_order'));assert all(b[x]==truth[x] for b in bs for x in ('missing_cells','duplicate_extra_rows','out_of_order_rows','unique_overlap_keys'));cases.append({'case':name,'rows':truth['rows'],'ground_truth':truth,'tool':ts,'baseline':bs,'tool_split_overlap':overlap_runs,'false_positives':{'tool':0,'baseline':0},'median_tool_runtime_seconds':statistics.median(t['runtime_seconds'] for t in ts),'median_baseline_runtime_seconds':statistics.median(b['runtime_seconds'] for b in bs)})
  out=Path(x.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'tool':'table-sentry','python':platform.python_version(),'os':platform.platform(),'repetitions':3,'cases':cases,'limitations':['Association is correlational, not causal leakage proof.','Only selected/shared keys can be compared; unknown shared keys are not inferred.']},indent=2)+'\n');print('BENCHMARK_OK',out)
if __name__=='__main__':main()
