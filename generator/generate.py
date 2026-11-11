"""Deterministic bounded-memory CSV generator; all people and sales are fictional."""
import argparse, csv, json, random, shutil, tempfile
from datetime import date, timedelta
from pathlib import Path

FIELDS = ['sale_line_id','sold_on','store_id','region','product_id','category','quantity','unit_price_cents','discount_cents']
REGIONS = ['North','South','East','West']
CATEGORIES = ['Electronics','Home','Sport','Fashion','Grocery']

def generate(rows=10000, stores=200, seed=42, output='data/raw', days=90):
    if rows < 1 or stores < 1 or days < 1:
        raise ValueError('rows, stores and days must be positive')
    target = Path(output)
    if target.exists():
        raise FileExistsError(f'{target} exists. Choose another output directory; input is never silently overwritten.')
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.generating-', dir=target.parent))
    rng = random.Random(seed)
    try:
        with (stage/'transactions.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
            previous=None
            for i in range(rows):
                if i % 101 == 100 and previous:
                    writer.writerow(previous);continue
                store=rng.randrange(stores); product=rng.randrange(100);quantity=rng.randint(1,5)
                price=rng.randint(200,30000)
                row=dict(zip(FIELDS,[f'LINE-{i:012d}',str(date(2026,1,1)+timedelta(days=rng.randrange(days))),f'STORE-{store+1:03d}',REGIONS[store%4],f'PROD-{product+1:03d}',CATEGORIES[product%5],quantity,price,rng.randint(0,price//4)]))
                if i % 137 == 136: row['quantity']=-1
                writer.writerow(row);previous=row
        (stage/'manifest.json').write_text(json.dumps({'rows':rows,'stores':stores,'seed':seed,'days':days,'currency':'EUR','synthetic':True},indent=2))
        stage.rename(target)
    except Exception:
        shutil.rmtree(stage,ignore_errors=True);raise
    return str(target)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows',type=int,default=10000);parser.add_argument('--stores',type=int,default=200)
    parser.add_argument('--seed',type=int,default=42);parser.add_argument('--days',type=int,default=90)
    parser.add_argument('--output',default='data/raw')
    print(generate(**vars(parser.parse_args())))
