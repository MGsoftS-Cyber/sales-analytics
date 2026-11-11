import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from pipeline.ingest import ingest
from pipeline.run import run
from app.service import response


class RetailImportTests(unittest.TestCase):
    def test_uci_cancellations_currency_sheets_and_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            source = p/'retail.xlsx'
            frame = pd.DataFrame({
                'Invoice': ['1', 'C2', '3', '4'], 'InvoiceDate': ['2011-01-01']*4,
                'StockCode': ['A']*4, 'Country': ['France']*4,
                'Quantity': [2, 1, -2, 1], 'Price': [2.5, 2.5, 2.5, 0]})
            with pd.ExcelWriter(source) as writer:
                frame.to_excel(writer, sheet_name='first', index=False)
                frame.head(1).to_excel(writer, sheet_name='second', index=False)
            meta = ingest('uci-ii', source, p/'raw', limit=0)
            self.assertEqual((meta['input_rows'], meta['rows'], meta['rejected_rows']), (5, 2, 3))
            with patch.dict(os.environ, {'DATABASE_URL': '', 'SQLITE_PATH': str(p/'db')}):
                run(p/'raw', p/'out')
                self.assertEqual(response('/api/overview', {})['revenue_cents'], 1172)
                self.assertEqual(response('/api/dataset', {})['source'], 'uci-ii')
                with self.assertRaises(RuntimeError):
                    run(p/'missing', p/'out')
                self.assertEqual(response('/api/dataset', {})['source'], 'uci-ii')
            with self.assertRaises(FileExistsError):
                ingest('uci-ii', source, p/'raw')

    def test_kaggle_fractional_units_and_limit(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            pd.DataFrame({'date': ['2017-01-01']*4, 'store_nbr': [1]*4,
                          'family': ['FOOD']*4, 'sales': [2.6, 0, -1, 8]}).to_csv(p/'train.csv', index=False)
            meta = ingest('kaggle', p/'train.csv', p/'raw', limit=3)
            self.assertEqual((meta['input_rows'], meta['rows']), (3, 1))
            row = pd.read_csv(p/'raw/transactions.csv').iloc[0]
            self.assertEqual((row.quantity, row.unit_price_cents), (3, 100))
            self.assertIn('invented', json.loads((p/'raw/manifest.json').read_text())['notes'])


if __name__ == '__main__':
    unittest.main()
