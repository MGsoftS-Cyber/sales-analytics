# Retail demonstration validation — 6 November 2026

Executed from Windows PowerShell in this workspace. Docker Desktop's Linux engine was started from the existing per-user installation. Project-local Python 3.11.9, pandas 2.2.3, Spark/PySpark 3.5.5, kind 0.33.0 and kubectl 1.35.0 were downloaded through terminal commands. Java 17 is installed in the backend Docker image.

## Live deployment

- Dedicated kind cluster: `storescope`, Kubernetes 1.35.0, one Docker node.
- Namespace: `storescope`. PostgreSQL, API and dashboard pods all Ready, with zero restarts at final verification.
- UCI ingestion Job `ingest-48cb560a`: Complete; 22 seconds wall time. Reads the verified downloaded ZIP through a PVC upload init container.
- Spark Job `process-ingest-48cb560a`: Complete; application processing duration 58.773 seconds, Job wall time 63 seconds. Runs `local[2]` in one pod, not distributed executors.
- PostgreSQL snapshot run ID: `4f8701d2963f48f19338b361335e074b`.
- Dashboard: http://localhost:8080 through an active Kubernetes port-forward.

UCI input archive SHA-256: `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`.

The importer read 10,000 source rows, retained 9,854 and excluded 146. Spark accepted all 9,854 normalized rows and published 4,920 grouped rows. Dashboard totals matched the independent reference run exactly: 90,121 units, 9,854 sale lines, 15 country proxy stores and 21,550,058 EUR cents using the documented illustrative currency conversion. These are demonstration results, not historical EUR financial statements or a scale benchmark.

## Checks completed

- Eight local integration tests passed, including source conversion, cancellations, multiple Excel sheets, Kaggle fractional units, import limits, atomic snapshot metadata, repeat processing and failure preservation.
- The real Java/Spark Docker parity test passed: Spark and reference results matched for totals, input/rejection/duplicate counts and aggregate row counts.
- The Kubernetes dashboard returned HTTP 200 for HTML, JavaScript, CSS and all ten API endpoints. Exact financial/unit totals, source metadata, successful Spark run history and trend totals were asserted through HTTP.
- PowerShell scripts parsed, JavaScript syntax passed, and Compose plus Kubernetes YAML parsed.
- Docker backend/web builds succeeded. Platform-specific image archives loaded into kind successfully; Windows imports took several minutes. Build provenance is disabled and temporary archives are removed by the deployment script.

## Limits and remaining external prerequisites

- Online Retail II download repeatedly timed out; incomplete archives were removed. Its adapter was tested with a multi-sheet fixture, not the complete remote dataset.
- No Kaggle credential file or environment credentials were available. Kaggle downloading was not performed; its CSV adapter was tested with a fixture. A user-authenticated competition download is required.
- Docker Compose configuration was parsed but its full runtime path was not executed in this session.
- Browser visual layout inspection was not performed. HTTP/static asset and JavaScript checks passed.

## Reconnect or import another snapshot

Keep Docker Desktop running. If port forwarding ends:

```powershell
.tools/bin/kubectl.exe --context kind-storescope -n storescope port-forward service/dashboard 8080:80
```

To import another snapshot with the images already loaded:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy-retail.ps1 -UseLoadedImages -Source uci -InputFile data/downloads/uci.zip -Limit 100000
```

Use the full deployment without `-UseLoadedImages` after changing application code. See [the retail guide](RETAIL-DEMO.md) for all sources and data assumptions.
