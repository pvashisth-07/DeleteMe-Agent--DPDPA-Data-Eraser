param(
    [Parameter(Position=0)]
    [string]$Target = "test"
)

$PYTHON = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
$PYTEST = if (Test-Path ".venv\Scripts\pytest.exe") { ".venv\Scripts\pytest.exe" } else { "pytest" }

switch ($Target) {
    "install" {
        & uv pip install -p $PYTHON -r requirements.txt
    }
    "test" {
        & $PYTEST tests
    }
    "lint" {
        & $PYTHON -m compileall agents shared mcp scripts
    }
    "preflight" {
        & $PYTHON scripts/preflight.py
    }
    "demo" {
        & $PYTHON scripts/demo.py
    }
    default {
        Write-Host "Usage: .\make.ps1 [install|test|lint|preflight|demo]"
    }
}
