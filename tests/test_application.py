import csv, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from generator.generate import generate, FIELDS
from pipeline.run import run
from app.storage import query, publish
from app.service import response

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'SQLITE_PATH':str(self.path/'test.db'),'DATABASE_URL':''});self.env.start()
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def fixture(self):
        raw=self.path/'raw';raw.mkdir()
        good=['LINE-1','2026-01-01','STORE-001','North','PROD-001','Home','2','2500','500']
        other=['LINE-2','2026-01-02','STORE-002','South','PROD-002','Sport','1','1000','0']
        invalid=['LINE-3','2026-01-03','STORE-003','West','PROD-003','Home','-1','100','0']
        with (raw/'sales.csv').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(FIELDS);w.writerows([good,good,other,invalid])
        return raw
    def test_exact_totals_filters_and_retry(self):
        raw=self.fixture();a=run(str(raw),str(self.path/'out'));b=run(str(raw),str(self.path/'out'))
        self.assertEqual((a['input_rows'],a['duplicate_rows'],a['rejected_rows']),(4,1,1))
        totals=response('/api/overview',{});self.assertEqual(totals['revenue_cents'],5500);self.assertEqual(totals['units'],3);self.assertEqual(totals['sale_lines'],2)
        self.assertEqual(response('/api/overview',{'region':'North'})['revenue_cents'],4500)
        self.assertEqual(response('/api/overview',{'start':'2026-01-02'})['revenue_cents'],1000)
        self.assertEqual(len(response('/api/runs',{})),2)
        self.assertNotEqual(a['run_id'],b['run_id'])
    def test_failed_publish_preserves_snapshot(self):
        raw=self.fixture();run(str(raw),str(self.path/'out'))
        def broken():yield ('2026-01-01','S','North','P','Home',1,1,1);raise RuntimeError('injected failure')
        with self.assertRaises(RuntimeError):publish(broken(),'bad','now')
        self.assertEqual(response('/api/overview',{})['revenue_cents'],5500)
    def test_failed_pipeline_preserves_snapshot_and_records_error(self):
        raw=self.fixture();run(str(raw),str(self.path/'out'))
        with self.assertRaises(RuntimeError):run(str(self.path/'missing'),str(self.path/'out'))
        self.assertEqual(response('/api/overview',{})['revenue_cents'],5500)
        self.assertEqual(response('/api/runs',{})[0]['status'],'failed')
    def test_sql_injection_and_dates_rejected(self):
        with self.assertRaises(ValueError):response('/api/stores',{'region':"North' OR 1=1 --"})
        with self.assertRaises(ValueError):response('/api/overview',{'start':'invalid'})
        with self.assertRaises(ValueError):response('/api/overview',{'start':'2026-02-01','end':'2026-01-01'})
    def test_generation_is_deterministic_and_does_not_overwrite(self):
        a=self.path/'a';b=self.path/'b';generate(500,10,42,str(a));generate(500,10,42,str(b))
        self.assertEqual((a/'transactions.csv').read_bytes(),(b/'transactions.csv').read_bytes())
        with self.assertRaises(FileExistsError):generate(output=str(a))
    def test_conflicting_duplicates_fail(self):
        raw=self.fixture()
        with (raw/'sales.csv').open('a',newline='') as f:csv.writer(f).writerow(['LINE-1','2026-01-01','STORE-001','North','PROD-001','Home','3','2500','0'])
        with self.assertRaises(RuntimeError):run(str(raw),str(self.path/'out'))
        self.assertEqual(query('SELECT COUNT(*) AS n FROM daily_sales')[0]['n'],0)

if __name__=='__main__':unittest.main()
