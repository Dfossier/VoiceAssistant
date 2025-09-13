# Find and kill Discord bot processes

Write-Host "Searching for Python and Discord-related processes..." -ForegroundColor Yellow

# Method 1: Look for all Python processes
Write-Host "`nMethod 1: All Python processes:" -ForegroundColor Cyan
Get-Process | Where-Object {$_.ProcessName -match "python|py"} | Format-Table Id, ProcessName, MainWindowTitle, Path -AutoSize

# Method 2: Look for processes with Discord in the command line
Write-Host "`nMethod 2: Processes with 'discord' or 'bot' in command line:" -ForegroundColor Cyan
Get-WmiObject Win32_Process | Where-Object {$_.CommandLine -match "discord|bot\.py"} | Select-Object ProcessId, Name, CommandLine | Format-Table -AutoSize

# Method 3: Check who's using common ports
Write-Host "`nMethod 3: Checking port usage (8000 for backend, Discord uses random ports):" -ForegroundColor Cyan
netstat -ano | Select-String ":8000|DISCORD" | ForEach-Object {
    $parts = $_ -split '\s+'
    $pid = $parts[-1]
    if ($pid -match '^\d+$') {
        try {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Port in use by: PID $pid - $($proc.ProcessName)" -ForegroundColor Green
            }
        } catch {}
    }
}

# Method 4: Look for Python processes by checking loaded modules
Write-Host "`nMethod 4: Python processes with discord.py loaded:" -ForegroundColor Cyan
Get-Process | Where-Object {$_.ProcessName -match "python"} | ForEach-Object {
    $pid = $_.Id
    $modules = Get-Process -Id $pid | Select-Object -ExpandProperty Modules -ErrorAction SilentlyContinue
    if ($modules -match "discord") {
        Write-Host "Found Discord bot: PID $pid - $($_.ProcessName)" -ForegroundColor Red
        $_ | Format-Table Id, ProcessName, MainWindowTitle -AutoSize
    }
}

# Method 5: Check for orphaned console windows
Write-Host "`nMethod 5: Console windows that might be running the bot:" -ForegroundColor Cyan
Get-Process | Where-Object {$_.ProcessName -match "cmd|powershell|conhost|WindowsTerminal"} | Format-Table Id, ProcessName, MainWindowTitle -AutoSize

Write-Host "`n=== TO KILL A PROCESS ===" -ForegroundColor Yellow
Write-Host "Once you identify the Discord bot process, use one of these commands:" -ForegroundColor White
Write-Host "1. Stop-Process -Id <PID> -Force" -ForegroundColor Green
Write-Host "2. taskkill /F /PID <PID>" -ForegroundColor Green
Write-Host "3. To kill all Python processes: Get-Process python* | Stop-Process -Force" -ForegroundColor Red

Write-Host "`n=== INTERACTIVE KILL ===" -ForegroundColor Yellow
$response = Read-Host "Do you want to list all Python processes and select which to kill? (y/n)"
if ($response -eq 'y') {
    $pythonProcs = Get-Process | Where-Object {$_.ProcessName -match "python|py"}
    if ($pythonProcs) {
        Write-Host "`nPython processes found:" -ForegroundColor Cyan
        $i = 0
        $pythonProcs | ForEach-Object {
            Write-Host "[$i] PID: $($_.Id) - $($_.ProcessName) - $($_.MainWindowTitle)" -ForegroundColor White
            $i++
        }
        $selection = Read-Host "`nEnter the number(s) to kill (comma-separated) or 'all' to kill all"
        if ($selection -eq 'all') {
            $pythonProcs | Stop-Process -Force
            Write-Host "All Python processes killed!" -ForegroundColor Green
        } else {
            $indices = $selection -split ',' | ForEach-Object { [int]$_.Trim() }
            foreach ($index in $indices) {
                if ($index -ge 0 -and $index -lt $pythonProcs.Count) {
                    $proc = $pythonProcs[$index]
                    Stop-Process -Id $proc.Id -Force
                    Write-Host "Killed process: PID $($proc.Id)" -ForegroundColor Green
                }
            }
        }
    } else {
        Write-Host "No Python processes found!" -ForegroundColor Red
    }
}