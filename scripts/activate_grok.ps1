# Focus an existing Grok Build window, or launch one, then start voice dictation.
param(
    [switch]$NoVoice,
    [int]$SettleMs = 900
)

$ErrorActionPreference = "Stop"

$GrokExe = Join-Path $env:USERPROFILE ".grok\bin\grok.exe"
if (-not (Test-Path $GrokExe)) {
    $cmd = Get-Command grok -ErrorAction SilentlyContinue
    if ($cmd) { $GrokExe = $cmd.Source }
}
if (-not (Test-Path $GrokExe)) {
    Write-Error "grok.exe not found"
    exit 1
}

Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
using System.Diagnostics;

public static class GrokWin {
    public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] static extern int GetWindowText(IntPtr hWnd, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern int GetWindowTextLength(IntPtr hWnd);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr hWnd);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    const int SW_RESTORE = 9;

    public static List<IntPtr> FindCandidates() {
        var hits = new List<IntPtr>();
        EnumWindows((hWnd, lParam) => {
            if (!IsWindowVisible(hWnd)) return true;
            int len = GetWindowTextLength(hWnd);
            if (len <= 0) return true;
            var sb = new StringBuilder(len + 1);
            GetWindowText(hWnd, sb, sb.Capacity);
            string title = sb.ToString();
            uint pid;
            GetWindowThreadProcessId(hWnd, out pid);
            string proc = "";
            try { proc = Process.GetProcessById((int)pid).ProcessName; } catch {}

            bool titleHit =
                title.IndexOf("grok", StringComparison.OrdinalIgnoreCase) >= 0 ||
                title.IndexOf("Grok Build", StringComparison.OrdinalIgnoreCase) >= 0;
            bool procHit = proc.Equals("grok", StringComparison.OrdinalIgnoreCase);

            // Windows Terminal tabs: title often set to "Grok Build" by our launcher
            if (titleHit || procHit) hits.Add(hWnd);
            return true;
        }, IntPtr.Zero);
        return hits;
    }

    public static bool ForceForeground(IntPtr hWnd) {
        if (hWnd == IntPtr.Zero) return false;
        if (IsIconic(hWnd)) ShowWindow(hWnd, SW_RESTORE);

        IntPtr fg = GetForegroundWindow();
        uint cur = GetCurrentThreadId();
        uint fgThread = 0, targetThread = 0, dummy;
        if (fg != IntPtr.Zero) fgThread = GetWindowThreadProcessId(fg, out dummy);
        targetThread = GetWindowThreadProcessId(hWnd, out dummy);

        if (fgThread != 0 && fgThread != cur) AttachThreadInput(cur, fgThread, true);
        if (targetThread != 0 && targetThread != cur) AttachThreadInput(cur, targetThread, true);

        BringWindowToTop(hWnd);
        bool ok = SetForegroundWindow(hWnd);

        if (fgThread != 0 && fgThread != cur) AttachThreadInput(cur, fgThread, false);
        if (targetThread != 0 && targetThread != cur) AttachThreadInput(cur, targetThread, false);
        return ok;
    }
}
"@

function Send-CtrlSpace {
    $wshell = New-Object -ComObject WScript.Shell
    Start-Sleep -Milliseconds 150
    $wshell.SendKeys("^{ }")
}

$hwnds = [GrokWin]::FindCandidates()
$launched = $false

if ($hwnds.Count -eq 0) {
    $wt = Get-Command wt.exe -ErrorAction SilentlyContinue
    if ($wt) {
        Start-Process -FilePath $wt.Source -ArgumentList @(
            "-w", "0",
            "new-tab",
            "--title", "Grok Build",
            $GrokExe
        ) | Out-Null
    } else {
        Start-Process -FilePath $GrokExe | Out-Null
    }
    $launched = $true
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 350
        $hwnds = [GrokWin]::FindCandidates()
        if ($hwnds.Count -gt 0) { break }
    }
}

if ($hwnds.Count -eq 0) {
    Write-Host "WARN: launched=$launched no Grok window found"
    if (-not $NoVoice) { Send-CtrlSpace }
    exit 2
}

$target = $hwnds[0]
$ok = [GrokWin]::ForceForeground($target)
Write-Host "Focused hwnd=$target ok=$ok launched=$launched"
Start-Sleep -Milliseconds $SettleMs

if (-not $NoVoice) {
    Send-CtrlSpace
    Write-Host "Sent Ctrl+Space for voice dictation"
}
exit 0
