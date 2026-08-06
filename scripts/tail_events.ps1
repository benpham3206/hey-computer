# Tail voice-computer event log (wake hits, listener start/stop, etc.)
#   powershell -File tail_events.ps1
#   powershell -File tail_events.ps1 -Last 30

param([int]$Last = 20)

$Log = Join-Path $env:USERPROFILE ".grok\skills\voice-computer\logs\events.jsonl"
if (-not (Test-Path $Log)) {
    Write-Host "No events yet: $Log"
    Write-Host "Run: python -u ...\scripts\wake_debug.py"
    exit 0
}

Write-Host "Tailing $Log (Ctrl+C to stop)`n"
Get-Content $Log -Tail $Last -Wait | ForEach-Object {
    try {
        $o = $_ | ConvertFrom-Json
        $ts = if ($o.ts) { $o.ts.Substring(0, [Math]::Min(19, $o.ts.Length)) } else { "?" }
        $kind = $o.kind
        $extra = @()
        if ($null -ne $o.score) { $extra += "score=$($o.score)" }
        if ($null -ne $o.threshold) { $extra += "thr=$($o.threshold)" }
        if ($o.msg) { $extra += $o.msg }
        $suffix = if ($extra.Count) { "  " + ($extra -join " ") } else { "" }
        $color = switch ($kind) {
            "wake" { "Green" }
            "debug_start" { "Cyan" }
            "listener_start" { "Cyan" }
            default { "Gray" }
        }
        Write-Host "[$ts] $kind$suffix" -ForegroundColor $color
    } catch {
        Write-Host $_
    }
}
