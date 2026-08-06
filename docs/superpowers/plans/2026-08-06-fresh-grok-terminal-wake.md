# Fresh Grok Terminal Wake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start dictation in a new, visible PowerShell-hosted Grok Build window for every wake.

**Architecture:** `activate_grok.ps1` launches a new titled PowerShell host, discovers only that child process's window, foregrounds it, then sends `Ctrl+Space`. The listener retains the HWND for its existing safety gate.

**Tech Stack:** Windows PowerShell 5.1, Win32 user32 P/Invoke, Python unittest, CUA Driver.

## Global Constraints

- Every wake opens a fresh visible PowerShell window titled `Grok Build`.
- Do not reuse or target existing `grok.exe`, PowerShell, or Windows Terminal windows.
- Do not send `Ctrl+Space` unless the newly launched window is visible and foregrounded.

---

### Task 1: Fresh-terminal activation contract

**Files:**
- Modify: `scripts/activate_grok.ps1`
- Create: `tests/test_activate_grok_contract.py`

**Interfaces:** Produces `Focused hwnd=<integer> ok=True launched=True` only after exact child-window foregrounding; nonzero exit otherwise.

- [ ] Write failing tests that require `Start-Process` PowerShell launch, `Grok Build` title, `-NoExit`, and no existing-window reuse.
- [ ] Run `python -m unittest tests/test_activate_grok_contract.py -v` and observe failure.
- [ ] Implement `WaitForWindow($host.Id, 15000)`, fail closed when absent or not foregrounded, then send `Ctrl+Space`.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Commit `scripts/activate_grok.ps1` and its contract test.

### Task 2: Live verification and documentation

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`

**Interfaces:** Documents that each `hey computer` wake opens a new visible PowerShell-hosted Grok Build window.

- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\activate_grok.ps1`.
- [ ] Verify with `cua-driver call list_windows` that a non-minimized PowerShell window titled `Grok Build` exists.
- [ ] Update both docs with the exact behavior.
- [ ] Run `python -m unittest discover -s tests -v; git diff --check`.
- [ ] Commit documentation and push `main` to `origin`.
