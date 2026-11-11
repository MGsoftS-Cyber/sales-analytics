"""Pandas adapters for separate public retail demonstration snapshots."""
import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

import pandas as pd
from generator.generate import FIELDS, REGIONS

SOURCES = {
    'uci': ('352/online+retail', 'https://doi.org/10.24432/C5BW33'),
    'uci-ii': ('502/online+retail+ii', 'https://doi.org/10.24432/C5CG6D'),
}


def download(source, cache):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (source + '.zip')
    if not target.exists() or not zipfile.is_zipfile(target):
        partial = target.with_suffix('.part')
        url = 'https://archive.ics.uci.edu/static/public/' + SOURCES[source][0] + '.zip'
        with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as dest:
            shutil.copyfileobj(response, dest)
        with zipfile.ZipFile(partial) as archive:
            if archive.testzip():
                raise ValueError('Corrupt source archive')
        partial.replace(target)
    return target


def frames(source, path, limit):
    if source == 'kaggle':
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as archive, archive.open('train.csv') as stream:
                yield from pd.read_csv(stream, chunksize=50000)
        else:
            yield from pd.read_csv(path, chunksize=50000)
    else:
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as archive:
                name = next(n for n in archive.namelist() if n.lower().endswith('.xlsx'))
                with archive.open(name) as stream:
                    yield from excel_frames(stream, limit)
        else:
            yield from excel_frames(path, limit)


def excel_frames(stream, limit):
    with pd.ExcelFile(stream, engine='openpyxl') as book:
        remaining = limit
        for sheet in book.sheet_names:
            frame = pd.read_excel(book, sheet_name=sheet, nrows=remaining or None)
            yield frame
            if limit:
                remaining -= len(frame)
                if remaining <= 0:
                    break


def cents(value, rate):
    return int((Decimal(str(value)) * Decimal(str(rate)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def ingest(source='uci', input_path=None, output='data/retail', cache='data/downloads', limit=100000):
    if limit < 0:
        raise ValueError('limit must be nonnegative (0 means all rows)')
    target = Path(output)
    if target.exists():
        raise FileExistsError(f'{target} exists; choose a new snapshot directory')
    if source == 'kaggle' and not input_path:
        raise ValueError('Supply --input train.csv or the Kaggle competition ZIP; authentication and rule acceptance are required for download')
    path = Path(input_path) if input_path else download(source, cache)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.ingesting-', dir=target.parent))
    stores, products = {}, {}
    read = kept = 0
    try:
        for frame in frames(source, path, limit):
            if limit:
                frame = frame.head(limit - read)
            frame = frame.rename(columns={'Invoice': 'InvoiceNo', 'Price': 'UnitPrice'})
            required = (['date', 'store_nbr', 'family', 'sales'] if source == 'kaggle' else
                        ['InvoiceNo', 'InvoiceDate', 'StockCode', 'Country', 'Quantity', 'UnitPrice'])
            missing = set(required) - set(frame.columns)
            if missing:
                raise ValueError(f'Missing source columns: {sorted(missing)}')
            read += len(frame)
            if source == 'kaggle':
                dates = pd.to_datetime(frame['date'], errors='coerce')
                qty = pd.to_numeric(frame['sales'], errors='coerce')
                price = pd.Series(1, index=frame.index)  # invented EUR 1 per rounded unit
                store = frame['store_nbr'].astype('string')
                product = frame['family'].astype('string')
                valid = dates.notna() & qty.gt(0) & store.notna() & product.notna()
                # Fractional weighted sales cannot fit the existing integer unit schema.
                qty = qty.round()
                valid &= qty.gt(0)
            else:
                dates = pd.to_datetime(frame['InvoiceDate'], errors='coerce')
                qty = pd.to_numeric(frame['Quantity'], errors='coerce')
                price = pd.to_numeric(frame['UnitPrice'], errors='coerce')
                store = frame['Country'].astype('string')
                product = frame['StockCode'].astype('string')
                valid = (dates.notna() & qty.gt(0) & qty.eq(qty.round()) & price.gt(0)
                         & ~frame['InvoiceNo'].astype(str).str.upper().str.startswith('C')
                         & store.notna() & product.notna())
            normalized = []
            for index in frame.index[valid]:
                amount = cents(price.loc[index], 1 if source == 'kaggle' else '1.17')
                quantity = int(qty.loc[index])
                if not 0 < quantity <= 999999999 or not 0 < amount <= 999999999:
                    continue
                s, p = str(store.loc[index]), str(product.loc[index])
                stores.setdefault(s, len(stores) + 1)
                products.setdefault(p, len(products) + 1)
                kept += 1
                normalized.append([f'LINE-{kept:012d}', dates.loc[index].strftime('%Y-%m-%d'),
                                   f'STORE-{stores[s]:05d}', REGIONS[(stores[s]-1) % 4],
                                   f'PROD-{products[p]:06d}', 'Grocery' if source == 'kaggle' else 'Home',
                                   quantity, amount, 0])
            pd.DataFrame(normalized, columns=FIELDS).to_csv(stage/'transactions.csv', mode='a',
                                                          index=False, header=not (stage/'transactions.csv').exists())
            if limit and read >= limit:
                break
        if not kept:
            raise ValueError('No usable positive sales found')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        manifest = dict(source=source, input_sha256=digest.hexdigest(), input_rows=read,
                        rows=kept, rejected_rows=read-kept, currency='EUR', demonstration=True,
                        attribution=SOURCES[source][1] if source in SOURCES else 'https://www.kaggle.com/competitions/store-sales-time-series-forecasting',
                        notes=('UCI: positive sales only; GBP converted at illustrative fixed 1.17 EUR/GBP; country proxy stores; artificial region buckets; all products Home.'
                               if source != 'kaggle' else 'Kaggle: rounded sales units; invented EUR 1/unit; family proxy products; all products Grocery; artificial region buckets.'),
                        stores=stores, products=products)
        (stage/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        stage.rename(target)
        print(json.dumps({k: v for k, v in manifest.items() if k not in ('stores', 'products')}))
        return manifest
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['uci', 'uci-ii', 'kaggle'], default='uci')
    parser.add_argument('--input', dest='input_path')
    parser.add_argument('--output', default='data/retail')
    parser.add_argument('--cache', default='data/downloads')
    parser.add_argument('--limit', type=int, default=100000)
    ingest(**vars(parser.parse_args()))
