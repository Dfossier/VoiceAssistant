Write-Host "Killing Discord bot processes..."

# Get all python processes with direct_audio in command line
$processes = Get-WmiObject Win32_Process | Where-Object { 
    $_.Name -eq "python.exe" -and 
    $_.CommandLine -like "*direct_audio*" 
}

foreach ($process in $processes) {
    Write-Host "Killing PID $($process.ProcessId) - $($process.CommandLine)"
    try {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        $process.Terminate() | Out-Null
    } catch {
        Write-Host "Error killing PID $($process.ProcessId): $_"
    }
}

# Additional cleanup with taskkill
$discordPids = tasklist /fi "imagename eq python.exe" /fo csv | ConvertFrom-Csv | Where-Object { $_.CommandLine -like "*direct_audio*" } | Select-Object -ExpandProperty PID
foreach ($pid in $discordPids) {
    taskkill /F /PID $pid 2>$null
}

Write-Host "Discord bot cleanup complete."