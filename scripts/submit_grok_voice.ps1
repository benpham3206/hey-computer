param(
    [switch]$DryRun,
    [string]$ForegroundTitle = "",
    [long]$ExpectedHwnd = 0,
    [long]$ForegroundHwnd = 0
)

$ErrorActionPreference = "Stop"

if (-not $DryRun) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class VoiceSubmitWindow {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    public static string ForegroundTitle() {
        var b = new StringBuilder(1024);
        GetWindowText(GetForegroundWindow(), b, b.Capacity);
        return b.ToString();
    }
    public static long ForegroundHwnd() { return GetForegroundWindow().ToInt64(); }
}
"@
    $ForegroundTitle = [VoiceSubmitWindow]::ForegroundTitle()
    $ForegroundHwnd = [VoiceSubmitWindow]::ForegroundHwnd()
}

$eligible = if ($ExpectedHwnd -ne 0) {
    $ForegroundHwnd -eq $ExpectedHwnd
} else {
    $ForegroundTitle -match '(?i)grok(?: build)?'
}
$actions = [System.Collections.ArrayList]::new()
if ($eligible) {
    [void]$actions.Add('ctrl+space')
    [void]$actions.Add('enter')
}
$result = [ordered]@{
    eligible = $eligible
    actions = $actions
}

if (-not $eligible) {
    $result | ConvertTo-Json -Compress
    exit 3
}

if (-not $DryRun) {
    $shell = New-Object -ComObject WScript.Shell
    $shell.SendKeys('^{ }')
    Start-Sleep -Milliseconds 900
    $stillEligible = if ($ExpectedHwnd -ne 0) {
        [VoiceSubmitWindow]::ForegroundHwnd() -eq $ExpectedHwnd
    } else {
        [VoiceSubmitWindow]::ForegroundTitle() -match '(?i)grok(?: build)?'
    }
    if (-not $stillEligible) {
        [ordered]@{ eligible = $false; actions = @('ctrl+space') } | ConvertTo-Json -Compress
        exit 4
    }
    $shell.SendKeys('{ENTER}')
}

$result | ConvertTo-Json -Compress
exit 0
