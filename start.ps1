$Host.UI.RawUI.WindowTitle = "DEVIL CHAT - Private Ephemeral P2P"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Check if Python is installed
try {
    $null = python --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Python not found" }
} catch {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host "                     [!] PYTHON NOT FOUND [!]" -ForegroundColor Red
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Python 3 is required to run DEVIL CHAT, but was not found on your PATH."
    Write-Host "Please install Python 3 from https://www.python.org/downloads/"
    Write-Host "Make sure to check the box: 'Add python.exe to PATH' during installation."
    Write-Host ""
    Read-Host "Press ENTER to exit"
    exit 1
}

# Run DEVIL CHAT
python "$PSScriptRoot\devil_chat.py"
