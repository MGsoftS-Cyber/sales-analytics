"""Record real wall-clock measurements; never label reference results as Spark."""
import argparse,csv,tempfile,time
from pathlib import Path
from generator.generate import generate
from pipeline.run import run

def main():
    p=argparse.ArgumentParser();p.add_argument('--engine',choices=['reference','spark'],default='reference');p.add_argument('--sizes',nargs='+',type=int,default=[10000,100000]);p.add_argument('--output',default='data/benchmark.csv');a=p.parse_args()
    import os
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['rows','bytes','engine','duration_seconds','input_rows','rejected_rows','duplicate_rows']);w.writeheader()
        for n in a.sizes:
            with tempfile.TemporaryDirectory() as d:
                raw=Path(d)/'raw';generate(n,200,42,str(raw));os.environ['SQLITE_PATH']=str(Path(d)/'benchmark.db');os.environ['DATABASE_URL']=''
                r=run(str(raw),str(Path(d)/'processed'),a.engine)
                w.writerow({k:({'rows':n,'bytes':(raw/'transactions.csv').stat().st_size,**r})[k] for k in w.fieldnames});f.flush()
if __name__=='__main__':main()
