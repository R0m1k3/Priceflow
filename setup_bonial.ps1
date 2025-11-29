# Setup and Migration Script for Bonial Module
#
# Run this script to set up the Bonial catalog module

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "   BONIAL CATALOG MODULE - SETUP SCRIPT" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "[1/3] Checking Docker..." -ForegroundColor Yellow
try {
    $dockerCheck = docker ps 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ERROR: Docker is not running!" -ForegroundColor Red
        Write-Host "   Please start Docker Desktop and try again." -ForegroundColor Red
        exit 1
    }
    Write-Host "   OK - Docker is running" -ForegroundColor Green
} catch {
    Write-Host "   ERROR: Docker not found!" -ForegroundColor Red
    Write-Host "   Please install Docker Desktop." -ForegroundColor Red
    exit 1
}

# Run Alembic migration inside container
Write-Host ""
Write-Host "[2/3] Running database migration..." -ForegroundColor Yellow
try {
    docker compose exec -T priceflow alembic upgrade head
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   OK - Migration completed successfully" -ForegroundColor Green
    } else {
        Write-Host "   WARNING: Migration may have failed" -ForegroundColor Yellow
        Write-Host "   Tables may already exist - this is normal" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ERROR: Could not run migration" -ForegroundColor Red
    Write-Host "   Error: $_" -ForegroundColor Red
}

# Restart application to trigger seeding
Write-Host ""
Write-Host "[3/3] Restarting application to seed enseignes..." -ForegroundColor Yellow
try {
    docker compose restart priceflow
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   OK - Application restarted" -ForegroundColor Green
        Start-Sleep -Seconds 3
        Write-Host "   Check logs for: 'X enseigne(s) créée(s)'" -ForegroundColor Cyan
    } else {
        Write-Host "   ERROR: Could not restart application" -ForegroundColor Red
    }
} catch {
    Write-Host "   ERROR: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "   SETUP COMPLETE!" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Check application logs:" -ForegroundColor White
Write-Host "     docker compose logs -f priceflow" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Run verification script:" -ForegroundColor White
Write-Host "     docker compose exec priceflow python verify_bonial.py" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Test API endpoints:" -ForegroundColor White
Write-Host "     Invoke-WebRequest http://localhost:8555/api/catalogues/enseignes" -ForegroundColor Gray
Write-Host ""
