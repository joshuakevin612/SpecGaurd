# SpecGuard Backend Setup Script
# Creates a virtual environment and installs dependencies

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SpecGuard Backend - Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "Checking Python installation..." -ForegroundColor Yellow

try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Found: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] Python not found! Please install Python 3.11+ and try again." -ForegroundColor Red
    pause
    exit
}

Write-Host ""

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Yellow

if (Test-Path "venv") {
    Write-Host "[OK] Virtual environment already exists, skipping creation" -ForegroundColor Green
}
else {
    python -m venv venv
    Write-Host "[OK] Virtual environment created" -ForegroundColor Green
}

Write-Host ""

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
Write-Host "[OK] Virtual environment activated" -ForegroundColor Green

Write-Host ""

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
Write-Host "(This may take 1-2 minutes)" -ForegroundColor Gray

pip install -r requirements.txt

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "[OK] Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Virtual environment is now active." -ForegroundColor Cyan
Write-Host ""
Write-Host "Next, to start the backend server, run:" -ForegroundColor White
Write-Host "  uvicorn backend.main:app --reload" -ForegroundColor Yellow
Write-Host ""
Write-Host "Or use the run.ps1 script for quick start." -ForegroundColor Cyan
Write-Host ""

pause