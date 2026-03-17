param(
    [string]$OutputDir = "backups"
)

if (-not $env:DATABASE_URL) {
    Write-Error "DATABASE_URL is required"
    exit 1
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$output = Join-Path $OutputDir "neuronyx_$timestamp.sql"

pg_dump $env:DATABASE_URL | Set-Content $output
Write-Output "Backup written to $output"
