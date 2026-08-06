# Launch a fresh visible Grok Build PowerShell window, then start dictation.
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

public static class GrokWin {
    public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr hWnd);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    const int SW_RESTORE = 9;

    public static IntPtr WaitForWindow(int processId, int timeoutMs) {
        var deadline = Environment.TickCount + timeoutMs;
        do {
            IntPtr found = IntPtr.Zero;
            EnumWindows((hWnd, lParam) => {
                uint pid;
                GetWindowThreadProcessId(hWnd, out pid);
                if ((int)pid == processId && IsWindowVisible(hWnd)) {
                    found = hWnd;
                    return false;
                }
                return true;
            }, IntPtr.Zero);
            if (found != IntPtr.Zero) return found;
            System.Threading.Thread.Sleep(100);
        } while (Environment.TickCount - deadline < 0);
        return IntPtr.Zero;
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
        bool ok = SetForegroundWindow(hWnd) && GetForegroundWindow() == hWnd;

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

$PowerShellExe = Join-Path $PSHOME "powershell.exe"
$escapedGrokExe = $GrokExe.Replace("'", "''")
$bootstrap = @'
$Host.UI.RawUI.WindowTitle = 'Grok Build'
& '{0}'
'@ -f $escapedGrokExe
$encodedBootstrap = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($bootstrap))
$grokHostProcess = Start-Process -FilePath $PowerShellExe -ArgumentList @(
    '-NoExit',
    '-EncodedCommand', $encodedBootstrap
) -PassThru

$target = [GrokWin]::WaitForWindow($grokHostProcess.Id, 15000)
if ($target -eq [IntPtr]::Zero) {
    Write-Host "WARN: launched=True no PowerShell host window found"
    exit 2
}

$ok = [GrokWin]::ForceForeground($target)
if (-not $ok) {
    Write-Host "WARN: launched=True could not foreground hwnd=$target"
    exit 3
}
Write-Host "Focused hwnd=$target ok=$ok launched=True"
Start-Sleep -Milliseconds $SettleMs

if (-not $NoVoice) {
    Send-CtrlSpace
    Write-Host "Sent Ctrl+Space for voice dictation"
}
exit 0
