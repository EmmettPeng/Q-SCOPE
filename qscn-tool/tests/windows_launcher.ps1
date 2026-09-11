$ErrorActionPreference = 'Stop'
$env:QSCN_LAUNCHER_LIBRARY_ONLY = '1'
. (Join-Path $PSScriptRoot '..\packaging\windows\qscn.ps1')

function Assert-ThrowsLike {
    param([scriptblock]$Action, [string]$Pattern)
    try {
        & $Action
    } catch {
        if ($_.Exception.Message -notlike $Pattern) {
            throw "Expected '$Pattern', received '$($_.Exception.Message)'"
        }
        return
    }
    throw "Expected an exception matching '$Pattern'."
}

$script:DockerMode = 'linux'
function docker {
    $command = "$args"
    if ($command -like 'compose version*') { $global:LASTEXITCODE = 0; return }
    if ($command -like 'info*') {
        if ($script:DockerMode -eq 'stopped') { $global:LASTEXITCODE = 1; return }
        $global:LASTEXITCODE = 0
        $script:DockerMode
        return
    }
    $global:LASTEXITCODE = 0
}

Test-QscnHost
$script:DockerMode = 'windows'
Assert-ThrowsLike { Test-QscnHost } '*WSL 2 Linux-container backend*'
$script:DockerMode = 'stopped'
Assert-ThrowsLike { Test-QscnHost } '*Docker Desktop is not running*'

function Get-QscnPort { 65431 }
function Invoke-RestMethod { param($Uri, $TimeoutSec) throw 'not ready' }
function Invoke-Compose { }
$env:QSCN_READY_ATTEMPTS = '1'
Assert-ThrowsLike { Wait-QscnReady } '*after 1 readiness attempts*'

function Test-QscnHost { }
function Get-NetTCPConnection {
    param($LocalPort, $State, $ErrorAction)
    [pscustomobject]@{ LocalPort = 65431 }
}
function docker { $global:LASTEXITCODE = 0 }
Assert-ThrowsLike { Start-Qscn } '*Port 65431 is already in use*'

Write-Host 'Windows launcher tests passed.'
