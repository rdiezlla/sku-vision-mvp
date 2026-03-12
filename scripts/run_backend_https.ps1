$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { 'python' }
& $Python "$Root/scripts/run_backend.py" --https --port 8443 @Args
exit $LASTEXITCODE
