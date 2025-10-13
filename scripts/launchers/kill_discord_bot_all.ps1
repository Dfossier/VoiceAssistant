# PowerShell script to kill all Discord bot processes
Write-Host "Stopping all Discord bot processes..." -ForegroundColor Yellow

# Kill by process name patterns
$pythonProcs = Get-Process | Where-Object {$_.ProcessName -like "*python*"}
$killedCount = 0

foreach ($proc in $pythonProcs) {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
        if ($cmdLine -like "*direct_audio_bot*" -or $cmdLine -like "*discord*bot*") {
            Write-Host "Killing PID $($proc.Id): $cmdLine" -ForegroundColor Red
            Stop-Process -Id $proc.Id -Force
            $killedCount++
        }
    } catch {
        # Process might have already ended
    }
}

# Also kill any hanging cmd windows
$cmdProcs = Get-Process | Where-Object {$_.ProcessName -eq "cmd"}
foreach ($proc in $cmdProcs) {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
        if ($cmdLine -like "*bot_venv_windows*") {
            Write-Host "Killing cmd.exe PID $($proc.Id)" -ForegroundColor Red
            Stop-Process -Id $proc.Id -Force
            $killedCount++
        }
    } catch {
        # Process might have already ended
    }
}

Write-Host "Killed $killedCount Discord bot related processes" -ForegroundColor Green