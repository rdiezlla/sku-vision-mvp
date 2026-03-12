$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { 'python' }
& $Python "$Root/scripts/setup_frontend.py" @Args
exit $LASTEXITCODE
