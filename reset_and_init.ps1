# Complete reset and fresh install script (PowerShell)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "CTF Platform - Complete Reset & Fresh Install" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "WARNING: This will DELETE ALL DATA!" -ForegroundColor Red
Write-Host "Press Ctrl+C to cancel, or Enter to continue..."
Read-Host

Write-Host ""
Write-Host "Stopping containers..." -ForegroundColor Yellow
docker-compose down -v

Write-Host ""
Write-Host "Removing old data..." -ForegroundColor Yellow
if (Test-Path ".data") {
    Remove-Item -Recurse -Force .data\mysql\* -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force .data\uploads\* -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force .data\logs\* -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force .data\redis\* -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Building fresh containers..." -ForegroundColor Yellow
docker-compose build --no-cache

Write-Host ""
Write-Host "Starting containers..." -ForegroundColor Yellow
docker-compose up -d

Write-Host ""
Write-Host "Waiting for database to be ready (30 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

Write-Host ""
Write-Host "Checking database health..." -ForegroundColor Yellow
docker-compose exec db mysql -u root -proot_password -e "SELECT 1;" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Database is ready" -ForegroundColor Green
} else {
    Write-Host "Database is not ready. Waiting another 15 seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
}

Write-Host ""
Write-Host "Initializing database..." -ForegroundColor Yellow
docker-compose exec -T ctf python init_db.py

Write-Host ""
Write-Host "Fresh installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Default Admin Credentials:" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Username: admin" -ForegroundColor White
Write-Host "Password: admin123" -ForegroundColor White
Write-Host ""
Write-Host "Sample User Credentials:" -ForegroundColor Cyan
Write-Host "Username: alice, bob, charlie, dave, eve, frank" -ForegroundColor White
Write-Host "Password: password123" -ForegroundColor White
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Access your CTF platform at:" -ForegroundColor Cyan
Write-Host "http://localhost:8000" -ForegroundColor White
Write-Host "or" -ForegroundColor White
Write-Host "http://0.0.0.0:8000" -ForegroundColor White
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Note: All tables including hints, settings, and team requirements are created automatically!" -ForegroundColor Yellow
Write-Host ""
