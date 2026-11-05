$env:Path += ";C:\Program Files\Tesseract-OCR"
$env:TESSDATA_PREFIX = "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tessdata"
Write-Host "=== Arteria ===" -ForegroundColor Cyan

Write-Host "`n[1/3] Installing backend dependencies..." -ForegroundColor Yellow
Set-Location backend
pip install -r requirements.txt
if (-not $?) { exit 1 }

Write-Host "`n[2/3] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location ../frontend
npm install
if (-not $?) { exit 1 }

Write-Host "`n[3/3] Starting servers..." -ForegroundColor Yellow
$backend = Start-Process powershell -ArgumentList "-NoExit -Command cd $(Resolve-Path ../backend); python main.py" -PassThru
$frontend = Start-Process powershell -ArgumentList "-NoExit -Command cd $(Resolve-Path .); npm run dev" -PassThru

Write-Host "`nBackend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host "`nNOTE: The s2t and Seis projects also use port 3000." -ForegroundColor Yellow
Write-Host "      If you get port conflicts, change the port in frontend/vite.config.js" -ForegroundColor Yellow
Write-Host "`nPress any key to stop both servers..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
