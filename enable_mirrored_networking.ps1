# Enable WSL2 Mirrored Networking Mode
# Run this as Administrator in PowerShell

Write-Host "Enabling WSL2 Mirrored Networking Mode..." -ForegroundColor Blue

# Check Windows version (requires Windows 11 22H2+)
$osInfo = Get-ComputerInfo
$windowsVersion = $osInfo.WindowsProductName
Write-Host "Windows Version: $windowsVersion" -ForegroundColor Yellow

# Enable mirrored networking
try {
    wsl --shutdown
    wsl --update
    wsl --version
    
    # Create or update .wslconfig
    $wslconfigPath = "$env:USERPROFILE\.wslconfig"
    
    $wslconfig = @"
[wsl2]
networkingMode=mirrored
dnsTunneling=true
firewall=true
autoProxy=true
"@
    
    $wslconfig | Out-File -FilePath $wslconfigPath -Encoding UTF8 -Force
    Write-Host "Updated $wslconfigPath" -ForegroundColor Green
    
    Write-Host "Restarting WSL..." -ForegroundColor Yellow
    wsl --shutdown
    
    Write-Host "Mirrored networking enabled!" -ForegroundColor Green
    Write-Host "Run 'wsl' to start WSL with mirrored networking" -ForegroundColor Cyan
    Write-Host "Windows localhost (127.0.0.1) now connects to WSL localhost" -ForegroundColor Cyan
    
} catch {
    Write-Host "Error enabling mirrored networking: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Make sure you're running as Administrator" -ForegroundColor Yellow
}
