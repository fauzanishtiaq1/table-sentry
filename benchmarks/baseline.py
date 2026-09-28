import argparse,csv,json
from collections import Counter
from pathlib import Path
def read(p):
    with Path(p).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def main():
    a=argparse.ArgumentParser();a.add_argument('input');a.add_argument('--train');a.add_argument('--time',default='observed_at');a.add_argument('--key',default='record_id');a.add_argument('--output',required=True);x=a.parse_args(); rows=read(x.input)
    miss=sum(1 for r in rows for v in r.values() if v is None or v==''); dup=sum(n-1 for n in Counter(tuple(sorted(r.items())) for r in rows).values() if n>1);out=0;prior={}
    for r in rows:
        try:
            t=float(r[x.time]);g=r.get('subject','')
            if g in prior and t<prior[g]:out+=1
            prior[g]=t
        except (KeyError,ValueError):pass
    overlap=0
    if x.train: overlap=len(({r.get(x.key) for r in read(x.train)}&{r.get(x.key) for r in rows})-{None})
    Path(x.output).write_text(json.dumps({'rows':len(rows),'missing_cells':miss,'duplicate_extra_rows':dup,'out_of_order_rows':out,'unique_overlap_keys':overlap})+'\n',encoding='utf-8');print('BASELINE_OK')
if __name__=='__main__':main()
