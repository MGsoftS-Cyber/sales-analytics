param(
    [ValidateSet('uci', 'uci-ii', 'kaggle')][string]$Source = 'uci',
    [ValidateRange(0, 100000000)][int]$Limit = 100000,
    [string]$InputFile,
    [ValidateSet('Kubernetes', 'Compose')][string]$Target = 'Kubernetes',
    [switch]$UseLoadedImages
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (Test-Path .tools/bin) { $env:PATH = "$(Join-Path (Get-Location) '.tools/bin');$env:PATH" }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $dockerBin = Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin'
    if (Test-Path "$dockerBin/docker.exe") { $env:PATH = "$dockerBin;$env:PATH" }
}
function Run([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe failed with exit code $LASTEXITCODE" }
}
Get-Command docker -ErrorAction Stop | Out-Null
Run docker @('info', '--format', '{{.OSType}}')
if ($Source -eq 'kaggle' -and -not $InputFile) { throw 'Pass -InputFile with your downloaded Kaggle train.csv or competition ZIP.' }
if ($InputFile) { $InputFile = (Resolve-Path -LiteralPath $InputFile).Path }
$snapshot = "/data/retail-$(Get-Date -Format yyyyMMddHHmmss)-$([guid]::NewGuid().ToString('N').Substring(0,6))"
if ($Target -eq 'Compose') {
    if (-not (Test-Path .env)) {
        "POSTGRES_PASSWORD=$([guid]::NewGuid().ToString('N'))" | Set-Content .env -Encoding ascii
    }
    $env:SALES_INPUT = $snapshot
    Run docker @('compose', 'up', '-d', '--build', '--wait')
    $argsList = @('compose', 'run', '--rm')
    if ($InputFile) { $argsList += @('--volume', "${InputFile}:/input/source:ro") }
    $argsList += @('ingest', 'python', '-m', 'pipeline.ingest', '--source', $Source, '--output', $snapshot, '--limit', "$Limit")
    if ($InputFile) {
        # Preserve extension so the importer selects ZIP versus CSV/Excel correctly.
        $argsList = $argsList -replace '/input/source:ro', "/input/source$([IO.Path]::GetExtension($InputFile)):ro"
        $argsList += @('--input', "/input/source$([IO.Path]::GetExtension($InputFile))")
    }
    Run docker $argsList
    Run docker @('compose', 'run', '--rm', 'pipeline')
    Write-Host 'Dashboard: http://localhost:8080'
    exit
}
foreach ($tool in 'kind', 'kubectl') { Get-Command $tool -ErrorAction Stop | Out-Null }
if (-not $UseLoadedImages) {
    Run docker @('build', '--provenance=false', '-t', 'storescope-app:1.0.0', '-f', 'infra/docker/Dockerfile', '.')
    Run docker @('build', '--provenance=false', '-t', 'storescope-web:1.0.0', '-f', 'infra/docker/frontend.Dockerfile', '.')
}
$clusters = & kind get clusters
if ($LASTEXITCODE -ne 0) { throw 'Cannot list kind clusters' }
if ($clusters -notcontains 'storescope') {
    if ($UseLoadedImages) { throw '-UseLoadedImages requires an existing storescope cluster with application images loaded.' }
    Run kind @('create', 'cluster', '--name', 'storescope', '--config', 'infra/kubernetes/kind.yaml')
}
# Export only the local node's platform. Docker Desktop's containerd store can
# retain indexes with absent platforms; an explicit archive also avoids piping
# large Spark images between Docker CLI processes on Windows.
if (-not $UseLoadedImages) {
New-Item -ItemType Directory -Force .tools/images | Out-Null
foreach ($image in 'storescope-app:1.0.0', 'storescope-web:1.0.0') {
    $archive = Join-Path (Get-Location) ".tools/images/$($image.Replace(':','-')).tar"
    Run docker @('image', 'save', '--platform', 'linux/amd64', '-o', $archive, $image)
    Run kind @('load', 'image-archive', $archive, '--name', 'storescope')
    Remove-Item -LiteralPath $archive
}
}
# Every kubectl call explicitly targets this demo cluster.
function K([string[]]$Arguments) { Run kubectl (@('--context', 'kind-storescope', '-n', 'storescope') + $Arguments) }
K @('apply', '-f', 'infra/kubernetes/app.yaml')
$secretName = & kubectl --context kind-storescope -n storescope get secret database --ignore-not-found -o name
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the database Secret' }
if (-not $secretName) {
    $password = [guid]::NewGuid().ToString('N')
    K @('create', 'secret', 'generic', 'database', "--from-literal=password=$password", "--from-literal=url=postgresql://analytics:${password}@db:5432/analytics")
}
K @('rollout', 'restart', 'deployment/api', 'deployment/dashboard')
foreach ($resource in 'statefulset/db', 'deployment/api', 'deployment/dashboard') { K @('rollout', 'status', $resource, '--timeout=300s') }
$job = "ingest-$([guid]::NewGuid().ToString('N').Substring(0,8))"
$manifest = Get-Content infra/kubernetes/retail.yaml -Raw
$manifest = $manifest.Replace('name: ingest-retail', "name: $job").Replace('/data/retail', $snapshot).Replace('--source, uci,', "--source, $Source,").Replace("'100000'", "'$Limit'")
if ($InputFile) {
    # An init container waits while kubectl cp uploads the local file into the PVC.
    $ext = [IO.Path]::GetExtension($InputFile)
    $upload = "/data/upload-$job$ext"
    $manifest = $manifest.Replace("--limit, '$Limit']", "--limit, '$Limit', --input, $upload]")
    $init = "      initContainers:`n      - name: upload`n        image: storescope-app:1.0.0`n        command: [sh, -c, 'until test -f $upload.ready; do sleep 2; done']`n        volumeMounts:`n        - name: data`n          mountPath: /data`n"
    $manifest = $manifest.Replace('      containers:', $init + '      containers:')
}
$manifest | & kubectl --context kind-storescope -n storescope apply -f -
if ($LASTEXITCODE -ne 0) { throw 'Cannot create ingestion Job' }
if ($InputFile) {
    K @('wait', '--for=jsonpath={.status.initContainerStatuses[0].state.running}', 'pod', '-l', "job-name=$job", '--timeout=180s')
    $pod = & kubectl --context kind-storescope -n storescope get pods -l "job-name=$job" -o 'jsonpath={.items[0].metadata.name}'
    Push-Location ([IO.Path]::GetDirectoryName($InputFile))
    try { K @('cp', "./$([IO.Path]::GetFileName($InputFile))", "${pod}:$upload", '-c', 'upload') }
    finally { Pop-Location }
    K @('exec', $pod, '-c', 'upload', '--', 'touch', "$upload.ready")
}
K @('wait', '--for=condition=complete', "job/$job", '--timeout=1200s')
K @('logs', "job/$job")
$process = Get-Content infra/kubernetes/pipeline.yaml -Raw
$process = $process.Replace('name: process-sales', "name: process-$job").Replace('/data/raw', $snapshot)
$process | & kubectl --context kind-storescope -n storescope apply -f -
if ($LASTEXITCODE -ne 0) { throw 'Cannot create Spark Job' }
K @('wait', '--for=condition=complete', "job/process-$job", '--timeout=1200s')
K @('logs', "job/process-$job")
Write-Host 'Dashboard: http://localhost:8080 (keep this terminal open)'
K @('port-forward', 'service/dashboard', '8080:80')
