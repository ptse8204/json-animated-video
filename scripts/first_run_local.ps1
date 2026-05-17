param(
    [switch]$Help,
    [switch]$NoLaunch,
    [switch]$SkipInstall,
    [switch]$RunDemo,
    [string]$HostName = "",
    [int]$Port = 8766,
    [string]$VenvDir = ""
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host @"
Usage: .\scripts\first_run_local.ps1 [options]

Set up a local Python virtual environment, install MotionJSON in CPU/mock UI
mode, run provider diagnostics, and start the local UI unless disabled.

Options:
  -NoLaunch        Install and run diagnostics, but do not start the UI.
  -SkipInstall     Do not create a venv or install; use the current Python.
  -RunDemo         Also run the deterministic red-ball CLI demo.
  -HostName HOST   UI host. Default: 127.0.0.1.
  -Port PORT       UI port. Default: 8766.
  -VenvDir DIR     Virtual environment directory. Default: .venv.
  -Help            Show this help.

Environment:
  PYTHON_BIN       Python executable. Default: py -3 when available.
  VENV_DIR         Virtual environment directory. Default: .venv.
"@
}

if ($Help) {
    Show-Help
    exit 0
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

if ([string]::IsNullOrWhiteSpace($HostName)) {
    $HostName = if ($env:MOTIONJSON_UI_HOST) { $env:MOTIONJSON_UI_HOST } else { "127.0.0.1" }
}

if ([string]::IsNullOrWhiteSpace($VenvDir)) {
    $VenvDir = if ($env:VENV_DIR) { $env:VENV_DIR } else { ".venv" }
}

$Python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "py" }
$PythonArgs = if ($env:PYTHON_BIN) { @() } else { @("-3") }

Write-Host "Creating virtual environment in $VenvDir"
if (-not $SkipInstall) {
    & $Python @PythonArgs -m venv $VenvDir
    $VenvPython = Join-Path $Root (Join-Path $VenvDir "Scripts\python.exe")
    & $VenvPython -m pip install -U pip
    & $VenvPython -m pip install -e ".[ui]"
} else {
    $Candidate = Join-Path $Root (Join-Path $VenvDir "Scripts\python.exe")
    if (Test-Path $Candidate) {
        $VenvPython = $Candidate
    } elseif ($env:PYTHON_BIN) {
        $VenvPython = $env:PYTHON_BIN
    } else {
        $VenvPython = "python"
    }
}

Write-Host "Running provider diagnostics"
New-Item -ItemType Directory -Force -Path ".motionjson\storage" | Out-Null
& $VenvPython -m motionjson.cli backend diagnostics --json `
    --video examples\demo_red_ball.mp4 `
    --output-dir .motionjson\storage

if ($RunDemo) {
    & $VenvPython examples\make_demo_video.py --out examples\demo_red_ball.mp4
    & $VenvPython -m motionjson.cli extract examples\demo_red_ball.mp4 `
        --out out\demo_red_ball `
        --mask-provider threshold `
        --lower-hsv 0,80,80 `
        --upper-hsv 12,255,255 `
        --sample-fps 12 `
        --max-frames 12
    & $VenvPython -m motionjson.cli validate out\demo_red_ball
}

if (-not $NoLaunch) {
    Write-Host "Starting MotionJSON UI in CPU/mock mode"
    & $VenvPython -m motionjson.cli ui --no-open --mock --host $HostName --port $Port
} else {
    Write-Host "Setup complete. Start the UI with:"
    Write-Host "  $VenvPython -m motionjson.cli ui --no-open --mock --host $HostName --port $Port"
}
