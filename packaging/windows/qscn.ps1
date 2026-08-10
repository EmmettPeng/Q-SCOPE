[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'status', 'logs', 'update', 'backup', 'restore', 'doctor')]
    [string]$Command = 'start',
    [string]$Path
)

$ErrorActionPreference = 'Stop'
$PackageRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $PackageRoot 'compose.yml'
$EnvironmentFile = Join-Path $PackageRoot '.env'
$RedisImage = 'redis:7.2.4-alpine@sha256:c8bb255c3559b3e458766db810aa7b3c7af1235b204cfdb304e79ff388fe1a5a'

function Invoke-Compose {
    & docker compose --project-directory $PackageRoot -f $ComposeFile @args
    if ($LASTEXITCODE -ne 0) { throw "docker compose failed with exit code $LASTEXITCODE" }
}

function Get-QscnPort {
    $port = '8000'
    if (Test-Path $EnvironmentFile) {
        $line = Get-Content $EnvironmentFile | Where-Object { $_ -match '^QSCN_PORT=' } | Select-Object -First 1
        if ($line) { $port = ($line -split '=', 2)[1].Trim() }
    }
    if ($port -notmatch '^\d+$' -or [int]$port -lt 1 -or [int]$port -gt 65535) {
        throw 'QSCN_PORT in .env must be an integer from 1 to 65535.'
    }
    return [int]$port
}

function Test-QscnHost {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker Desktop is required: https://docs.docker.com/desktop/setup/install/windows-install/'
    }
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 is required.' }
    $osType = (& docker info --format '{{.OSType}}' 2>$null)
    if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is not running.' }
    if ($osType.Trim() -ne 'linux') { throw 'Switch Docker Desktop to Linux containers and try again.' }
    $architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    if ($architecture -ne 'X64') { throw "This release supports Windows x64; detected $architecture." }
    $memory = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
    if ($memory -lt 16GB) { Write-Warning '16 GB host memory is recommended.' }
    $driveName = (Get-Item $PackageRoot).PSDrive.Name
    $free = (Get-PSDrive -Name $driveName).Free
    if ($free -lt 40GB) { Write-Warning 'Less than 40 GB free disk space is available.' }
}

function Wait-QscnReady {
    $port = Get-QscnPort
    $uri = "http://127.0.0.1:$port/api/readiness"
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        try {
            $result = Invoke-RestMethod -Uri $uri -TimeoutSec 2
            if ($result.status -eq 'ready') {
                Write-Host "QSCN is ready at http://127.0.0.1:$port"
                return
            }
        } catch { }
        Start-Sleep -Seconds 1
    }
    Invoke-Compose ps
    Invoke-Compose logs --tail=100 app worker redis
    throw 'QSCN did not become ready within 120 seconds.'
}

function Start-Qscn {
    Test-QscnHost
    $port = Get-QscnPort
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    $existingApp = (& docker compose --project-directory $PackageRoot -f $ComposeFile ps -q app 2>$null)
    if ($listener -and -not $existingApp) { throw "Port $port is already in use. Change QSCN_PORT in .env." }
    Invoke-Compose pull
    Invoke-Compose up -d
    Wait-QscnReady
    if ($env:QSCN_NO_BROWSER -ne '1') { Start-Process "http://127.0.0.1:$port" }
}

function Backup-Qscn {
    Test-QscnHost
    $backupRoot = if ($Path) { $Path } else { Join-Path $PackageRoot 'backups' }
    $timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $target = Join-Path $backupRoot "qscn-$timestamp"
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Invoke-Compose stop app worker redis
    try {
        & docker run --rm -v 'qscn_qscn_v03_data:/source:ro' -v "${target}:/backup" $RedisImage sh -c 'tar -czf /backup/qscn-data.tar.gz -C /source .'
        if ($LASTEXITCODE -ne 0) { throw 'Application-data backup failed.' }
        & docker run --rm -v 'qscn_qscn_v03_redis:/source:ro' -v "${target}:/backup" $RedisImage sh -c 'tar -czf /backup/qscn-redis.tar.gz -C /source .'
        if ($LASTEXITCODE -ne 0) { throw 'Redis backup failed.' }
        Get-FileHash (Join-Path $target 'qscn-data.tar.gz'), (Join-Path $target 'qscn-redis.tar.gz') -Algorithm SHA256 |
            ForEach-Object { "{0}  {1}" -f $_.Hash.ToLowerInvariant(), (Split-Path $_.Path -Leaf) } |
            Set-Content -Encoding ascii (Join-Path $target 'SHA256SUMS')
    } finally {
        Invoke-Compose up -d
    }
    Write-Host "Backup written to $target"
}

function Restore-Qscn {
    Test-QscnHost
    if (-not $Path) { throw 'Usage: qscn.ps1 restore -Path C:\path\to\qscn-backup' }
    $source = (Resolve-Path $Path).Path
    if (-not (Test-Path (Join-Path $source 'qscn-data.tar.gz')) -or -not (Test-Path (Join-Path $source 'qscn-redis.tar.gz'))) {
        throw 'The selected directory is not a complete QSCN backup.'
    }
    $confirmation = Read-Host 'This replaces the current QSCN volumes. Type RESTORE to continue'
    if ($confirmation -ne 'RESTORE') { Write-Host 'Restore cancelled.'; return }
    Invoke-Compose down
    & docker volume create qscn_qscn_v03_data *> $null
    & docker volume create qscn_qscn_v03_redis *> $null
    & docker run --rm -v 'qscn_qscn_v03_data:/target' -v "${source}:/backup:ro" $RedisImage sh -c 'find /target -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -xzf /backup/qscn-data.tar.gz -C /target'
    if ($LASTEXITCODE -ne 0) { throw 'Application-data restore failed.' }
    & docker run --rm -v 'qscn_qscn_v03_redis:/target' -v "${source}:/backup:ro" $RedisImage sh -c 'find /target -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -xzf /backup/qscn-redis.tar.gz -C /target'
    if ($LASTEXITCODE -ne 0) { throw 'Redis restore failed.' }
    Invoke-Compose up -d
    Wait-QscnReady
}

switch ($Command) {
    'start'   { Start-Qscn }
    'stop'    { Invoke-Compose stop }
    'status'  { Invoke-Compose ps }
    'logs'    { Invoke-Compose logs --follow --tail=200 app worker redis }
    'update'  { Test-QscnHost; Invoke-Compose pull; Invoke-Compose up -d; Wait-QscnReady }
    'backup'  { Backup-Qscn }
    'restore' { Restore-Qscn }
    'doctor'  { Test-QscnHost; Write-Host 'Docker and host checks passed.' }
}
