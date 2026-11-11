# StoreScope — Multi-Store Sales Analytics

A complete portfolio application with synthetic sales, public retail dataset adapters using pandas, a real PySpark batch pipeline, transactional analytics storage, a web dashboard, and Docker Compose / local Kubernetes deployment files.

For UCI Online Retail, Online Retail II, or Kaggle Store Sales on Docker/Kubernetes, follow [the retail demonstration guide](docs/RETAIL-DEMO.md). On Windows with Docker running: `powershell -ExecutionPolicy Bypass -File scripts/deploy-retail.ps1`. Imported data uses explicit demonstration mappings displayed on the dashboard.

The dashboard includes revenue trends, regional comparisons, top stores, top products, date/region filters, and pipeline run history. The default generator creates fictional sales; public retail imports use the assumptions described in the retail demonstration guide. Money is stored as integer EUR cents. It counts sale lines, not customer orders or receipts.

## Start in two minutes — Python only

Python 3.11 or 3.12 is sufficient for the lightweight demonstration. No pip packages, Java, Docker, or database installation required for this mode.

Extract this folder and open a terminal **inside it**.

Ubuntu / Linux:

```bash
bash scripts/demo.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo.ps1
```

Or run these commands yourself:

```bash
python -m generator.generate --rows 10000
python -m pipeline.run --engine reference
python -m app.local
```

Use `python3` instead of `python` where appropriate. Open **http://localhost:8080**. Press Ctrl+C to stop the server. Re-running the pipeline replaces the analytics snapshot atomically; it does not add sales again.

The Python-only mode uses SQLite and the reference processing engine. It demonstrates application behavior; its measurements must not be presented as Spark benchmarks.

## Real Spark on your computer

Install Python 3.11 and Java 17; verify `java -version`. Create a virtual environment and install the pinned Python dependencies:

```bash
python -m venv .venv
# Linux: source .venv/bin/activate
# Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Linux:

```bash
export SPARK_LOCAL_IP=127.0.0.1
export PYSPARK_SUBMIT_ARGS='--master local[2] --driver-memory 1g --conf spark.sql.shuffle.partitions=4 pyspark-shell'
python -m pipeline.run --engine spark
python -m app.local
```

PowerShell:

```powershell
$env:SPARK_LOCAL_IP='127.0.0.1'
$env:PYSPARK_SUBMIT_ARGS='--master local[2] --driver-memory 1g --conf spark.sql.shuffle.partitions=4 pyspark-shell'
python -m pipeline.run --engine spark
python -m app.local
```

Native Windows Spark can require additional Hadoop/OS setup. Docker Desktop with WSL2 and the Compose route below provides a Linux execution path.

## Docker Compose — PostgreSQL + FastAPI + Nginx + Spark

Requires Docker Engine / Docker Desktop and the Compose plugin. Run from the repository root:

```bash
cp .env.example .env
# Edit POSTGRES_PASSWORD in .env; use URL-safe alphanumeric characters.
docker compose up -d --build --wait
docker compose run --rm generator
docker compose run --rm pipeline
```

PowerShell uses `Copy-Item .env.example .env` in place of `cp`.

Open **http://localhost:8080**. Nginx serves the dashboard and proxies `/api/` to FastAPI. PostgreSQL is on the internal Compose network. The pipeline runs Spark in `local[2]` mode inside its container.

```bash
docker compose logs api
docker compose logs dashboard
docker compose run --rm pipeline
```

The last command safely reprocesses the same immutable input. The generator deliberately refuses an existing output directory. To generate a different dataset, use another folder and point the pipeline at it:

```bash
docker compose run --rm generator python -m generator.generate --rows 1000000 --output /data/raw-million
docker compose run --rm pipeline python -m pipeline.run --engine spark --input /data/raw-million --output /data/processed
```

Stop with `docker compose down`. Volumes preserve the database and data. `docker compose down -v` deletes those demo volumes and their data.

## Kubernetes — one local kind cluster

Install Docker, kind, and kubectl. These manifests target a single-node local cluster with a default dynamic storage provisioner, such as kind's standard local storage. They do not configure a cloud load balancer or external storage.

```bash
docker build -t storescope-app:1.0.0 -f infra/docker/Dockerfile .
docker build -t storescope-web:1.0.0 -f infra/docker/frontend.Dockerfile .
kind create cluster --name storescope --config infra/kubernetes/kind.yaml
kind load docker-image storescope-app:1.0.0 storescope-web:1.0.0 --name storescope
kubectl create namespace storescope
kubectl -n storescope create secret generic database --from-literal=password=ChangeThisDemo123 --from-literal=url=postgresql://analytics:ChangeThisDemo123@db:5432/analytics
kubectl apply -f infra/kubernetes/app.yaml
kubectl -n storescope rollout status statefulset/db --timeout=180s
kubectl -n storescope rollout status deployment/api --timeout=180s
kubectl -n storescope rollout status deployment/dashboard --timeout=180s
kubectl apply -f infra/kubernetes/generator.yaml
kubectl -n storescope wait --for=condition=complete job/generate-sales --timeout=300s
kubectl apply -f infra/kubernetes/pipeline.yaml
kubectl -n storescope wait --for=condition=complete job/process-sales --timeout=600s
kubectl -n storescope port-forward service/dashboard 8080:80
```

Open **http://localhost:8080**. Run the following in a second terminal:

```bash
kubectl -n storescope logs job/process-sales
kubectl -n storescope scale deployment/api --replicas=2
kubectl -n storescope get pods
kubectl -n storescope delete pod -l app=api
kubectl -n storescope get pods -w
```

To run processing again, delete just the completed Job object and recreate it. The dataset and database volumes stay in place:

```bash
kubectl -n storescope delete job process-sales
kubectl apply -f infra/kubernetes/pipeline.yaml
```

A CronJob is included but suspended by default:

```bash
kubectl apply -f infra/kubernetes/cronjob.yaml
kubectl -n storescope patch cronjob daily-sales -p '{"spec":{"suspend":false}}'
```

The schedule is 02:00 UTC. It reprocesses the current input snapshot; this version does not automatically ingest a new day's sales. Do not run a manual Job concurrently with the CronJob if you want unambiguous snapshot order. For a safe retry demonstration, create a separate Job copied from the pipeline manifest with an input path that does not exist; observe the failed attempts and confirm that the previous dashboard snapshot remains available.

The Spark Job uses two local threads in one pod. **This release does not deploy distributed Spark driver/executor pods.** Kubernetes runs the application and schedules the batch; Spark performs actual transformations and Parquet writes. Multiple API replicas share one analytics database. A local kind cluster still shares the CPU and memory of your PC.

Remove the demonstration cluster with `kind delete cluster --name storescope`; this deletes cluster-local data.

## Tests and measurements

```bash
python -m unittest discover -v
node --check frontend/app.js
python -m benchmarks.run --engine reference --sizes 10000 100000
# With Java and PySpark installed:
python -m benchmarks.run --engine spark --sizes 10000 100000 1000000 --output data/spark-benchmarks.csv
```

The Spark parity test skips if PySpark is absent. CI includes a Spark job and a separate Compose smoke test. Benchmark CSVs contain actual measured processing time and input size. Record your CPU, RAM, storage, master setting, and dependency versions alongside any published graph. Startup time is included; one trial is not a statistically reliable comparison.

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Database connectivity |
| `GET /api/filters` | Date bounds and supported regions |
| `GET /api/overview` | Revenue, units, sale lines, active stores, snapshot update |
| `GET /api/trends` | Daily totals |
| `GET /api/regions` | Regional totals |
| `GET /api/categories` | Category totals |
| `GET /api/stores` | Top 20 stores |
| `GET /api/products` | Top 20 products |
| `GET /api/runs` | Latest 50 pipeline runs |

Analytics endpoints accept `start=YYYY-MM-DD`, `end=YYYY-MM-DD`, and `region=North`. Run history ignores these filters. API documentation is available through FastAPI at `/docs` on port 8000 (use port forwarding to access it in containers).

## Project map

| Folder | Responsibility |
|---|---|
| `app/` | FastAPI, dependency-free preview server, analytics queries and storage |
| `generator/` | Deterministic streaming synthetic CSV generation |
| `pipeline/` | Reference and Spark engines plus publication orchestration |
| `frontend/` | Responsive HTML/CSS/JavaScript dashboard, SVG charts, no external assets |
| `infra/docker/` | Backend image, web image and Nginx proxy |
| `infra/kubernetes/` | Stateful database, API/web Deployments, Services, PVCs, Jobs, CronJob |
| `tests/` | Correctness, retry, failure rollback, validation and Spark parity |
| `benchmarks/` | Reproducible measurement runner |
| `docs/` | Architecture, data semantics and validation record |
| `.github/workflows/` | Automated Python, JavaScript, Spark and container checks |

## Scope

This is a local portfolio application. It uses batch snapshot replacement, one currency, embedded product/store dimensions in generated rows, and a deliberately small API. It has no user accounts, profit calculation, refunds, live streaming, forecasting, or multi-tenant access. Do not expose the unauthenticated demo directly as a public business service. The UI uses native JavaScript rather than React to keep setup and delivery self-contained.

Use the Spark path to demonstrate data engineering; label reference mode clearly. See `docs/ARCHITECTURE.md` and `docs/VALIDATION.md` for implementation details and actual validation status.
