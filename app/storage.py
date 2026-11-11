import os, sqlite3, json
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def connect():
    url = os.getenv('DATABASE_URL', '')
    if url.startswith(('postgresql://', 'postgres://')):
        import psycopg
        db = psycopg.connect(url)
    else:
        path = Path(os.getenv('SQLITE_PATH', 'data/analytics.db'))
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=30)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def execute(db, sql, values=()):
    if not isinstance(db, sqlite3.Connection):
        sql = sql.replace('?', '%s')
    return db.execute(sql, values)

def initialize():
    with connect() as db:
        for sql in [
            'CREATE TABLE IF NOT EXISTS daily_sales (day TEXT NOT NULL, store_id TEXT NOT NULL, region TEXT NOT NULL, product_id TEXT NOT NULL, category TEXT NOT NULL, revenue_cents BIGINT NOT NULL, units BIGINT NOT NULL, lines BIGINT NOT NULL, PRIMARY KEY(day,store_id,product_id))',
            'CREATE TABLE IF NOT EXISTS pipeline_runs (run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, status TEXT NOT NULL, engine TEXT NOT NULL, input_rows BIGINT NOT NULL, rejected_rows BIGINT NOT NULL, duplicate_rows BIGINT NOT NULL, output_rows BIGINT NOT NULL, duration_seconds DOUBLE PRECISION NOT NULL, error TEXT)',
            'CREATE TABLE IF NOT EXISTS snapshot_meta (singleton INTEGER PRIMARY KEY, run_id TEXT NOT NULL, published_at TEXT NOT NULL)',
            'CREATE INDEX IF NOT EXISTS sales_day ON daily_sales(day)',
            'CREATE TABLE IF NOT EXISTS dataset_meta (singleton INTEGER PRIMARY KEY, metadata TEXT NOT NULL)',
        ]:
            db.execute(sql)

def record_run(run):
    with connect() as db:
        execute(db, 'INSERT INTO pipeline_runs VALUES (?,?,?,?,?,?,?,?,?,?)', run)

def publish(rows, run_id, timestamp, metadata=None):
    # Whole snapshot replacement is atomic: readers see old or new totals.
    # Serialize PostgreSQL writers; SQLite serializes writes automatically.
    with connect() as db:
        if not isinstance(db, sqlite3.Connection):
            db.execute('LOCK TABLE daily_sales, snapshot_meta, dataset_meta IN EXCLUSIVE MODE')
        db.execute('DELETE FROM daily_sales')
        for row in rows:
            execute(db, 'INSERT INTO daily_sales VALUES (?,?,?,?,?,?,?,?)', row)
        db.execute('DELETE FROM snapshot_meta')
        execute(db, 'INSERT INTO snapshot_meta VALUES (1,?,?)', (run_id, timestamp))
        db.execute('DELETE FROM dataset_meta')
        execute(db, 'INSERT INTO dataset_meta VALUES (1,?)', (json.dumps(metadata or {}),))

def query(sql, values=()):
    with connect() as db:
        cur = execute(db, sql, values)
        names = [item[0] for item in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]
