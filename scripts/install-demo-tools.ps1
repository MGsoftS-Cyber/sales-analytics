# Run from PowerShell. Docker Desktop must be installed and running separately.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force .tools/bin | Out-Null
$downloads = @{
    'kind.exe' = 'https://kind.sigs.k8s.io/dl/v0.33.0/kind-windows-amd64'
    'kubectl.exe' = 'https://dl.k8s.io/release/v1.35.0/bin/windows/amd64/kubectl.exe'
}
foreach ($name in $downloads.Keys) {
    & curl.exe -fL --connect-timeout 20 --max-time 300 $downloads[$name] -o ".tools/bin/$name"
    if ($LASTEXITCODE -ne 0) { throw "Download failed: $name" }
}
& .tools/bin/kind.exe version
& .tools/bin/kubectl.exe version --client
Write-Host 'Tools downloaded to .tools/bin. The deployment script adds this folder to its PATH.'
Write-Host 'The Docker image installs Java 17, Spark 3.5.5 and pandas 2.2.3 during docker build.'
