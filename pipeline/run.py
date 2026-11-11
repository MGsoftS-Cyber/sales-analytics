import argparse, json, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from app.storage import initialize, publish, record_run

def run(input_path='data/raw', output='data/processed', engine='reference'):
    initialize();run_id=uuid.uuid4().hex;started=datetime.now(timezone.utc).isoformat();clock=time.perf_counter()
    dest=Path(output)/run_id;dest.mkdir(parents=True)
    count=bad=duplicates=published=0;spark=None
    try:
        manifest=Path(input_path)/'manifest.json'
        metadata=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
        metadata={k:v for k,v in metadata.items() if k not in ('stores','products')}
        if engine=='spark':
            from pipeline.spark import process
            rows,count,bad,duplicates,spark=process(input_path,dest)
        else:
            from pipeline.reference import process
            rows,count,bad,duplicates=process(input_path,dest/'reference')
        def counted():
            nonlocal published
            for row in rows: published+=1;yield row
        publish(counted(),run_id,datetime.now(timezone.utc).isoformat(),metadata)
        status='success';error=None
    except Exception as exc:
        status='failed';error=str(exc)
    finally:
        if spark: spark.stop()
    duration=round(time.perf_counter()-clock,3)
    record_run((run_id,started,status,engine,count,bad,duplicates,published,duration,error))
    result=dict(run_id=run_id,status=status,engine=engine,input_rows=count,rejected_rows=bad,duplicate_rows=duplicates,output_rows=published,duration_seconds=duration,error=error)
    (dest/'metrics.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    if status!='success': raise RuntimeError(error)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',dest='input_path',default='data/raw');p.add_argument('--output',default='data/processed');p.add_argument('--engine',choices=['reference','spark'],default='reference')
    run(**vars(p.parse_args()))
