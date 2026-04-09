$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "Anchor-Backend\Zenmode_api")
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
