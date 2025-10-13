# Enable WSL2 Mirrored Networking Mode (Simple Version)
# Run this as Administrator in PowerShell

Write-Host "Enabling WSL2 Mirrored Networking Mode..."

# Enable mirrored networking
try {
    # Shutdown WSL
    wsl --shutdown
    
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
    Write-Host "Updated $wslconfigPath"
    
    # Restart WSL
    Write-Host "Restarting WSL..."
    wsl --shutdown
    
    Write-Host "SUCCESS: Mirrored networking enabled!"
    Write-Host "Run 'wsl' to start WSL with mirrored networking"
    Write-Host "Windows localhost (127.0.0.1) now connects to WSL localhost"
    
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    Write-Host "Make sure you're running as Administrator"
}
