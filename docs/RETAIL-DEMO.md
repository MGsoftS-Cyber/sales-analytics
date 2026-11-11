# Retail data with pandas, Spark, Docker and Kubernetes

This is a small demonstration, not a claim of production-scale big data. Pandas reads Excel or chunked Kaggle CSV, normalizes the input, and writes the application's CSV contract. Spark validates, deduplicates, writes Parquet, and publishes summaries to PostgreSQL. Nginx and FastAPI serve the dashboard. Kubernetes runs on Docker through kind. Spark runs `local[2]` within one Job pod, not distributed executor pods.

See [the executed Windows/Kubernetes validation record](RETAIL-VALIDATION.md) for the live deployment results and remaining dataset prerequisites.

## Terminal deployment on Windows

Install and start Docker Desktop with Linux containers and WSL2 support. Install kind and kubectl or put them in `.tools/bin`. Docker Desktop can require administrator access, virtualization support and a reboot; downloaded CLI tools alone cannot create a working container engine.

Download the Kubernetes terminal tools using `powershell -ExecutionPolicy Bypass -File scripts/install-demo-tools.ps1` if needed.

From the project root:

```powershell
# Kubernetes in Docker: imports 100,000 source rows, then runs real Spark.
powershell -ExecutionPolicy Bypass -File scripts/deploy-retail.ps1
# Import all rows of Online Retail II instead:
powershell -ExecutionPolicy Bypass -File scripts/deploy-retail.ps1 -Source uci-ii -Limit 0
# Docker Compose alternative:
powershell -ExecutionPolicy Bypass -File scripts/deploy-retail.ps1 -Target Compose
```

The deployment script builds the Java 17/Python image, installs the pinned Spark and pandas dependencies, creates or reuses the `storescope` kind cluster, creates database credentials when absent, waits for the app, runs pandas ingestion followed by Spark, and forwards the dashboard to http://localhost:8080. Each run uses a new input directory and Job name. Snapshots replace existing analytics rather than appending. Avoid concurrent deployments, and allow roughly 6 GB free RAM for Docker. Input files and Parquet remain on the data volume.

Windows image imports can take several minutes. The script exports AMD64 archives to avoid Docker Desktop image-index issues and removes them after import. After the images are loaded, use `-UseLoadedImages` to import another snapshot without rebuilding or transferring images. Omit that switch after changing application code.

For an offline UCI import, pass `-InputFile` with a downloaded ZIP or XLSX. Kubernetes uploads it to the data volume using an init container. Imports default to 100,000 source rows; `-Limit 0` processes all sheets/rows. Excel ingestion loads one sheet into pandas; it is not a distributed Excel reader.

## Kaggle

Kaggle requires your own account credentials and acceptance of the competition rules. Configure credentials using Kaggle's official instructions; keep them outside this repository and container images. In a Python environment with the Kaggle CLI installed:

```powershell
python -m pip install kaggle
kaggle competitions download -c store-sales-time-series-forecasting -p data/downloads
powershell -ExecutionPolicy Bypass -File scripts/deploy-retail.ps1 -Source kaggle -InputFile data/downloads/store-sales-time-series-forecasting.zip
```

No account credentials are required for UCI. A Kaggle download is not silently substituted with another dataset.

## Data meaning

- UCI Online Retail and Online Retail II are separate snapshots. They overlap in dates and must not be concatenated as independent sales.
- UCI cancels, returns, invalid dates, missing dimensions and nonpositive quantities/prices are excluded. Missing customer IDs are allowed because customer identity is not used. Source line order generates unique IDs; identical source lines remain distinct sales.
- UCI prices are GBP. To fit the existing EUR dashboard, a fixed **illustrative** 1.17 EUR/GBP rate is applied and unit prices rounded to cents. This is not historical currency conversion. Countries become proxy stores; sequential store IDs map to artificial North/South/East/West buckets. All UCI products use the demo category Home.
- Kaggle has sales quantities, not revenue or unit prices. Weighted fractional quantities are rounded to whole units (pandas ties-to-even), zero/negative values are excluded, and **invented EUR 1/unit** produces demonstration revenue. Families become proxy products; categories use Grocery and regions use artificial buckets. Sale lines count imported store/family/day observations, not receipts.
- Each `manifest.json` includes source, SHA-256, read/retained/excluded counts, assumptions and dimension mappings. `/api/dataset` and the dashboard display the published snapshot's assumptions. Metadata and analytics publish in the same transaction.

## Attribution

UCI Online Retail: Chen, D. (2015), https://doi.org/10.24432/C5BW33.
UCI Online Retail II: Chen, D. (2012), https://doi.org/10.24432/C5CG6D.
Both UCI datasets use CC BY 4.0. Normalization and demonstration mappings modify the originals.
Kaggle Store Sales: https://www.kaggle.com/competitions/store-sales-time-series-forecasting/data. Follow the competition's dataset terms.

## Local terminal checks

```powershell
python -m pip install -r requirements.txt
python -m pipeline.ingest --source uci --limit 100000 --output data/retail
python -m pipeline.run --engine reference --input data/retail
python -m app.local
python -m unittest discover -v
```

The reference command validates application behavior without Java; it is not a Spark run. For real Spark use the deployment script or the Java 17 setup in README. Stop Compose with `docker compose down`. Stop port forwarding with Ctrl+C. Removing volumes or deleting the kind cluster also deletes the stored demo data.
