# Stop background hey-computer wake listener(s).
$ErrorActionPreference = "SilentlyContinue"
$LogDir = Join-Path $env:USERPROFILE ".grok\skills\voice-computer\logs"
$pidFile = Join-Path $LogDir "wake.pid"
$stopped = 0

if (Test-Path $pidFile) {
    # $PID is a built-in, read-only PowerShell variable.  Use a distinct name
    # so the pid file's listener process, rather than this helper, is stopped.
    $listenerPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($listenerPid) {
        Stop-Process -Id ([int]$listenerPid) -Force -ErrorAction SilentlyContinue
        $stopped++
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*wake_listener.py*" } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
        $stopped++
        Write-Host "Stopped pid=$($_.ProcessId)"
    }

if ($stopped -eq 0) { Write-Host "No wake_listener processes found." }
else { Write-Host "Stopped $stopped process(es)." }
