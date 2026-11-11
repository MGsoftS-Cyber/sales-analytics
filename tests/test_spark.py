import importlib.util,os,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
from generator.generate import generate
from pipeline.run import run
from app.service import response

@unittest.skipUnless(importlib.util.find_spec('pyspark') and shutil.which('java'),'PySpark and Java are required')
class SparkParity(unittest.TestCase):
    def test_matches_reference(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);generate(500,20,42,str(p/'raw'))
            with patch.dict(os.environ,{'DATABASE_URL':'','SQLITE_PATH':str(p/'db.sqlite'),'SPARK_LOCAL_IP':'127.0.0.1','PYSPARK_SUBMIT_ARGS':'--master local[2] --conf spark.sql.shuffle.partitions=2 pyspark-shell'}):
                reference=run(str(p/'raw'),str(p/'out'),'reference');expected=response('/api/trends',{})
                spark=run(str(p/'raw'),str(p/'out'),'spark')
                self.assertEqual(response('/api/trends',{}),expected)
                for field in ['input_rows','rejected_rows','duplicate_rows','output_rows']:self.assertEqual(reference[field],spark[field])
