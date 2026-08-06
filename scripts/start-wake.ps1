# Start the "hey computer" wake listener in the background (or foreground with -Foreground).
param(
    [switch]$Foreground,
    [switch]$InstallStartup,
    [switch]$UninstallStartup,
    [double]$Threshold = 0.4,
    [double]$Cooldown = 4
)


$ErrorActionPreference = "Stop"
$SkillRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
# scripts/ is under voice-computer/scripts — skill root is parent of scripts
$SkillRoot = Split-Path $PSScriptRoot -Parent
$Listener = Join-Path $PSScriptRoot "wake_listener.py"
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { $Python = "C:\Python314\python.exe" }
if (-not (Test-Path $Python)) { throw "python not found" }
if (-not (Test-Path $Listener)) { throw "Missing $Listener" }

$TaskName = "GrokHeyComputerWake"
$LogDir = Join-Path $env:USERPROFILE ".grok\skills\voice-computer\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$OutLog = Join-Path $LogDir "wake_out.log"
$ErrLog = Join-Path $LogDir "wake_err.log"

if ($UninstallStartup) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName"
    exit 0
}

if ($InstallStartup) {
    $arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`""
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "Installed logon task: $TaskName"
    Write-Host "Starting now…"
}

# Kill prior listeners for this skill
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*wake_listener.py*" } |
    ForEach-Object {
        Write-Host "Stopping old wake_listener pid=$($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

$pyArgs = @(
    "-u",
    $Listener,
    "--threshold", "$Threshold",
    "--cooldown", "$Cooldown"
)

if ($Foreground) {
    & $Python @pyArgs
    exit $LASTEXITCODE
}

$p = Start-Process -FilePath $Python -ArgumentList $pyArgs `
    -WindowStyle Hidden `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru

Write-Host "Wake listener started pid=$($p.Id)"
Write-Host "  Say: hey computer"
Write-Host "  Logs: $OutLog"
Write-Host "  Stop:  Get-Process -Id $($p.Id) | Stop-Process"
Write-Host "  Or:    powershell -File `"$PSCommandPath`" -UninstallStartup  # if installed"
# Also write pid file
Set-Content -Path (Join-Path $LogDir "wake.pid") -Value $p.Id
