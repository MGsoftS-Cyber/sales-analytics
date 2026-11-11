$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Test-Path 'data/raw')) {
    python -m generator.generate --rows 10000
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
python -m pipeline.run --engine reference
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m app.local
