# Script to manually clean up catalogs and trigger scraping
# Usage: ./scripts/manual_cleanup_and_scrape.ps1

$BaseUrl = "http://localhost:8555/api"
$Username = "admin"
$Password = "admin"

Write-Host "1. Logging in as $Username..." -ForegroundColor Cyan
try {
    $LoginBody = @{
        username = $Username
        password = $Password
    } | ConvertTo-Json

    $LoginResponse = Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/login" -Body $LoginBody -ContentType "application/json"
    $Token = $LoginResponse.token
    Write-Host "   Success! Token received." -ForegroundColor Green
}
catch {
    Write-Host "   Login failed. Please check if the server is running." -ForegroundColor Red
    Write-Error $_
    exit
}

$Headers = @{
    Authorization = "Bearer $Token"
}

Write-Host "`n2. Running Cleanup (Deleting invalid catalogs)..." -ForegroundColor Cyan
try {
    $CleanupResponse = Invoke-RestMethod -Method Post -Uri "$BaseUrl/catalogues/admin/cleanup" -Headers $Headers
    Write-Host "   $($CleanupResponse.message)" -ForegroundColor Green
}
catch {
    Write-Host "   Cleanup failed." -ForegroundColor Red
    Write-Error $_
}

Write-Host "`n3. Triggering Scraping for Gifi (ID: 1)..." -ForegroundColor Cyan
try {
    $ScrapeResponse = Invoke-RestMethod -Method Post -Uri "$BaseUrl/catalogues/admin/scraping/trigger?enseigne_id=1" -Headers $Headers
    Write-Host "   $($ScrapeResponse.message)" -ForegroundColor Green
    Write-Host "   Check logs at: $BaseUrl/catalogues/admin/scraping/logs" -ForegroundColor Yellow
}
catch {
    Write-Host "   Scraping trigger failed." -ForegroundColor Red
    Write-Error $_
}

Write-Host "`nDone." -ForegroundColor Cyan
