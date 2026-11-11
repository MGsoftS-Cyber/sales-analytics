# Validation record

For the newer pandas/public-retail deployment executed on Windows with Docker and Kubernetes on 6 November 2026, see [Retail validation](RETAIL-VALIDATION.md). The record below describes the original creation environment.

Validated in the creation environment on 3 November 2026.

## Completed checks

- Six integration test methods passed: exact financial totals and filters; repeat-run idempotency; rollback of failed publications; failed pipeline run history and preservation of published data; deterministic generation and overwrite protection; invalid filters/dates and conflicting duplicate detection. Some of these are combined in a single test method.
- A seventh test ran real PySpark 3.5.5 with Java and compared its results with the reference engine: daily totals, input counts, rejection counts, duplicate counts, and aggregate row counts matched.
- Both the standard-library local server and the FastAPI/Uvicorn server answered all nine API endpoints successfully over HTTP.
- Python source compilation and Node JavaScript syntax validation passed.
- Compose, Kubernetes, kind and GitHub Actions YAML files parsed successfully. Parsing does not establish deployment success.
- A 10,000-row local reference demonstration produced 73 rejected rows, 98 removed duplicates, 9,829 unique valid sale lines, 29,472 units and EUR 4,257,709.12 revenue across 200 stores.

## Not executed here

- Docker builds, PostgreSQL runtime integration, Nginx proxy startup, kind cluster deployment, pod scaling and CronJob execution: Docker and kubectl were unavailable in this environment. CI definitions and setup commands are included for these checks.
- Automated visual browser inspection: no browser executable was available and downloading one did not produce a usable browser. The frontend's JavaScript was syntax-checked, and the data API was exercised over HTTP; visual layout is not claimed as tested.
- Distributed Spark executor pods: not implemented in this release. The Spark path runs in local execution mode, including inside its Kubernetes Job.

## Benchmark data

`benchmarks/example-results.csv` contains measured Spark processing durations from this session, if present. These are single-run illustrations on the creation environment, including Spark startup, SQLite snapshot publication, and output writes. They are not predictions for your PC or evidence of multi-machine scaling. Use the benchmark runner on your own hardware and record resource settings before making comparisons.
