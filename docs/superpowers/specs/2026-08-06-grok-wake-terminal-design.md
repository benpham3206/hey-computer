# Fresh Grok terminal per wake

## Goal

Every recognized `hey computer` wake starts Grok Build dictation reliably, regardless of whether a PowerShell or Grok process already exists or is minimized.

## Design

`activate_grok.ps1` will always create a new visible `powershell.exe` window. Its command sets the console title to `Grok Build` and runs the resolved `grok.exe` with `-NoExit` so the host window persists. The script waits for the newly launched PowerShell process to expose its visible top-level console window, explicitly restores and foregrounds that exact HWND, waits for the settle delay, then sends `Ctrl+Space`.

It will not scan for or reuse existing `grok.exe`, PowerShell, or Windows Terminal windows. A hidden `grok.exe` console is therefore never a candidate. If the new window cannot be discovered or foregrounded, the script exits nonzero and does not send the dictation hotkey.

## Evidence and tests

Unit-level contract tests will assert the fresh-PowerShell launch, exact child-process window lookup, and no hotkey on failure. A live CUA window snapshot after a test activation will verify that a visible `Grok Build` PowerShell window exists; listener events will record the returned HWND.
