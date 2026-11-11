"""Small-data reference engine for local use and correctness comparisons."""
import csv, json, re
from datetime import date
from pathlib import Path
from collections import defaultdict

REGIONS={'North','South','East','West'}
CATEGORIES={'Electronics','Home','Sport','Fashion','Grocery'}

def normalize(row):
    try:
        if not re.fullmatch(r'LINE-\d+',row['sale_line_id']): raise ValueError('invalid sale ID')
        if not re.fullmatch(r'STORE-\d+',row['store_id']): raise ValueError('invalid store')
        if not re.fullmatch(r'PROD-\d+',row['product_id']): raise ValueError('invalid product')
        if row['region'] not in REGIONS or row['category'] not in CATEGORIES: raise ValueError('unknown dimension')
        if str(date.fromisoformat(row['sold_on'])) != row['sold_on']: raise ValueError('invalid date')
        for field in ['quantity','unit_price_cents','discount_cents']:
            if not re.fullmatch(r'\d{1,9}',str(row[field])): raise ValueError('invalid numeric field')
            row[field]=int(row[field])
        total=row['quantity']*row['unit_price_cents']
        if row['quantity']<1 or row['discount_cents']>total: raise ValueError('invalid quantity or discount')
        return row, None
    except (ValueError,KeyError,TypeError) as exc:
        return None, str(exc)

def process(input_path, output):
    out=Path(output);out.mkdir(parents=True)
    groups=defaultdict(lambda:[0,0,0]);seen={};count=bad=duplicates=0
    files=sorted(Path(input_path).glob('*.csv'))
    if not files: raise ValueError('No CSV input files found')
    with (out/'rejected.jsonl').open('w') as reject, (out/'clean.jsonl').open('w') as clean:
        for file in files:
            with file.open(newline='') as f:
                for raw in csv.DictReader(f):
                    count+=1;row,error=normalize(dict(raw))
                    if error:
                        bad+=1;reject.write(json.dumps({'record':raw,'reason':error})+'\n');continue
                    key=row['sale_line_id']; signature=json.dumps(row,sort_keys=True)
                    if key in seen:
                        if seen[key] != signature: raise ValueError(f'Conflicting duplicate ID: {key}')
                        duplicates+=1;continue
                    seen[key]=signature;clean.write(json.dumps(row)+'\n')
                    key=(row['sold_on'],row['store_id'],row['region'],row['product_id'],row['category'])
                    agg=groups[key];agg[0]+=row['quantity']*row['unit_price_cents']-row['discount_cents'];agg[1]+=row['quantity'];agg[2]+=1
    return [(*key,*values) for key,values in sorted(groups.items())],count,bad,duplicates
