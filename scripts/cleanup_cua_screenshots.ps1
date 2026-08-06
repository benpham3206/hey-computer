param(
    [string]$Root = (Join-Path $env:USERPROFILE '.cua-driver\screenshots'),
    [ValidateRange(1, 3650)][int]$Days = 7,
    [switch]$Apply,
    [switch]$InstallTask
)

$ErrorActionPreference = 'Stop'
$TaskName = 'CuaScreenshotRetention'
$allowedExtensions = @('.png', '.jpg', '.jpeg', '.webp')
$resolvedRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\')

if ([IO.Path]::GetFileName($resolvedRoot) -ne 'screenshots') {
    throw "Refusing cleanup root not named screenshots: $resolvedRoot"
}

if ($InstallTask) {
    New-Item -ItemType Directory -Force -Path $resolvedRoot | Out-Null
    $arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" -Root `"$resolvedRoot`" -Days $Days -Apply"
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
    $trigger = New-ScheduledTaskTrigger -Daily -At '3:00 AM'
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedRoot -PathType Container)) {
    [ordered]@{ root = $resolvedRoot; cutoff_days = $Days; matched = 0; deleted = 0 } | ConvertTo-Json -Compress
    exit 0
}

$cutoff = (Get-Date).AddDays(-$Days)
$matches = @(
    Get-ChildItem -LiteralPath $resolvedRoot -Recurse -File -ErrorAction Stop |
        Where-Object { $allowedExtensions -contains $_.Extension.ToLowerInvariant() -and $_.LastWriteTime -lt $cutoff }
)

$deleted = 0
if ($Apply) {
    foreach ($file in $matches) {
        $candidate = [IO.Path]::GetFullPath($file.FullName)
        if (-not $candidate.StartsWith($resolvedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw "Resolved file escaped cleanup root: $candidate"
        }
        [IO.File]::Delete($candidate)
        $deleted++
    }
}

[ordered]@{
    root = $resolvedRoot
    cutoff_days = $Days
    matched = $matches.Count
    deleted = $deleted
} | ConvertTo-Json -Compress
