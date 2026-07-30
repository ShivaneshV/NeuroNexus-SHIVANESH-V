# PaperPilot Server Bootstrapper
# This script ensures environment configuration, checks keys, and starts both backend and frontend.

Clear-Host

Write-Host "=========================================" -ForegroundColor Magenta
Write-Host "   PaperPilot: Autonomous Research Agent  " -ForegroundColor Magenta
Write-Host "=========================================" -ForegroundColor Magenta

# 1. Environment Setup & Secure Key Prompts
if (-not (Test-Path .env)) {
    Write-Host "[*] No .env configuration detected." -ForegroundColor Yellow
    Write-Host "Please configure your OpenAI API Key to proceed." -ForegroundColor Yellow
    
    # Prompt for key securely (typing masked)
    $secureKey = Read-Host "Enter OPENAI_API_KEY" -AsSecureString
    if ($secureKey -eq $null -or $secureKey.Length -eq 0) {
        Write-Host "[!] API Key is required to run LLM synthesizers." -ForegroundColor Red
        Exit
    }
    
    # Extract plain-text representation to write to .env safely
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    $plainKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    
    # Save variables
    Add-Content -Path .env -Value "OPENAI_API_KEY=$plainKey"
    Add-Content -Path .env -Value "BACKEND_PORT=8000"
    Add-Content -Path .env -Value "HOST=127.0.0.1"
    
    # Clean secrets from memory variables
    Clear-Variable secureKey, BSTR, plainKey
    Write-Host "[+] Saved credentials to .env file." -ForegroundColor Green
}

# 2. Launch FastAPI Backend in a new window
Write-Host "[*] Launching FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Title 'PaperPilot Backend (FastAPI)'; cd backend; uvicorn main:app --reload --port 8000"

# 3. Launch Next.js Frontend in a new window
Write-Host "[*] Launching Next.js Frontend on http://localhost:3000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Title 'PaperPilot Frontend (Next.js)'; cd frontend; npm run dev"

Write-Host "=========================================" -ForegroundColor Green
Write-Host " Both servers launched in separate windows!" -ForegroundColor Green
Write-Host " - Backend API: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host " - Frontend UI: http://localhost:3000" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
