[CmdletBinding()]
param(
    [string]$IdfPath = $env:IDF_PATH,
    [string]$PythonPath,
    [string]$BuildDirectory = 'build-native-screen',
    [switch]$SkipValidation
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskEspressif = Join-Path $env:USERPROFILE '.espressif'

if (-not $IdfPath) {
    $taskFrameworks = Join-Path $taskEspressif 'frameworks'
    $taskCandidates = @(Get-ChildItem -LiteralPath $taskFrameworks -Directory |
        Where-Object { $_.Name -match '^esp-idf-v5\.5\.' } |
        Sort-Object { [version]($_.Name -replace '^esp-idf-v', '') } -Descending)
    if ($taskCandidates.Count -eq 0) {
        throw 'ESP-IDF 5.5.x was not found. Supply -IdfPath with its installation directory.'
    }
    $IdfPath = $taskCandidates[0].FullName
}

$IdfPath = (Resolve-Path -LiteralPath $IdfPath).Path
$taskExport = Join-Path $IdfPath 'export.ps1'
if (-not (Test-Path -LiteralPath $taskExport -PathType Leaf)) {
    throw "Missing ESP-IDF environment script: $taskExport"
}

if (-not $PythonPath) {
    $taskEnvironments = Join-Path $taskEspressif 'python_env'
    $taskPythonCandidates = @(Get-ChildItem -LiteralPath $taskEnvironments -Directory |
        Where-Object { $_.Name -like 'idf5.5_*' } |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName 'Scripts\python.exe' } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
    if ($taskPythonCandidates.Count -eq 0) {
        throw 'ESP-IDF Python environment was not found. Supply -PythonPath with its python.exe.'
    }
    $PythonPath = $taskPythonCandidates[0]
}

$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
$env:Path = (Split-Path -Parent $PythonPath) + ';' + $env:Path
$env:PYTHONUTF8 = '1'
. $taskExport
if (-not $?) { throw 'ESP-IDF environment activation failed.' }

Push-Location (Join-Path $taskRoot 'firmware')
try {
    & $PythonPath (Join-Path $IdfPath 'tools\idf.py') -B $BuildDirectory '-DIDF_TARGET=esp32s3' build
    if ($LASTEXITCODE -ne 0) { throw "Firmware build failed with exit code $LASTEXITCODE." }
    if (-not $SkipValidation) {
        & $PythonPath 'tools\validate_build.py' $BuildDirectory
        if ($LASTEXITCODE -ne 0) { throw "Firmware validation failed with exit code $LASTEXITCODE." }
    }
}
finally {
    Pop-Location
}


