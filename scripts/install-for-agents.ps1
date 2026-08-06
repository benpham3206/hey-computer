# Install voice-computer skill so Grok, Codex, and generic agent harnesses can find it.
# Creates directory junctions (Windows) from shared homes → canonical ~/.grok/skills/voice-computer
#
#   powershell -File install-for-agents.ps1
#   powershell -File install-for-agents.ps1 -Uninstall

param([switch]$Uninstall)

$ErrorActionPreference = "Stop"
$Canonical = Join-Path $env:USERPROFILE ".grok\skills\voice-computer"
if (-not (Test-Path (Join-Path $Canonical "SKILL.md"))) {
    throw "Canonical skill missing: $Canonical"
}

$targets = @(
    (Join-Path $env:USERPROFILE ".agents\skills\voice-computer"),
    (Join-Path $env:USERPROFILE ".codex\skills\voice-computer"),
    (Join-Path $env:USERPROFILE ".claude\skills\voice-computer")
)

function Ensure-Parent($path) {
    $parent = Split-Path $path -Parent
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
}

foreach ($t in $targets) {
    Ensure-Parent $t
    if (Test-Path $t) {
        $item = Get-Item $t -Force
        if ($Uninstall) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                cmd /c rmdir "$t"
                Write-Host "Removed junction: $t"
            } else {
                Write-Host "Skip (not a junction, left in place): $t"
            }
            continue
        }
        # already exists
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Write-Host "Already linked: $t"
            continue
        }
        Write-Host "Exists as real folder (not replacing): $t"
        continue
    }
    if ($Uninstall) { continue }
    # mklink /J
    cmd /c mklink /J "$t" "$Canonical" | Out-Host
    Write-Host "Linked: $t -> $Canonical"
}

# Codex AGENTS.md pointer (append once)
$agentsMd = Join-Path $env:USERPROFILE ".codex\AGENTS.md"
$marker = "<!-- voice-computer-skill -->"
$blurb = @"

$marker
## voice-computer skill

Hands-free desktop control skill shared with Grok Build.

- Path: ``~/.codex/skills/voice-computer`` (junction → ``~/.grok/skills/voice-computer``)
- Wake debug: ``python -u ~/.codex/skills/voice-computer/scripts/wake_debug.py``
- Pipeline status: ``python -u ~/.codex/skills/voice-computer/scripts/pipeline_status.py``
- Speak (Carina, Grok OAuth): ``python -u ~/.codex/skills/voice-computer/scripts/speak_xai.py --text "..."``
- When user says hey computer / voice control / CUA voice: load ``SKILL.md`` and follow the ACK → CUA → SPEAK loop.
$marker

"@

if (-not $Uninstall) {
    if (Test-Path $agentsMd) {
        $cur = Get-Content $agentsMd -Raw -ErrorAction SilentlyContinue
        if ($cur -notmatch [regex]::Escape($marker)) {
            Add-Content -Path $agentsMd -Value $blurb
            Write-Host "Appended skill pointer to $agentsMd"
        } else {
            Write-Host "AGENTS.md already has voice-computer pointer"
        }
    } else {
        Set-Content -Path $agentsMd -Value "# Codex agent notes`n$blurb" -Encoding utf8
        Write-Host "Created $agentsMd"
    }
}

Write-Host "Done. Canonical: $Canonical"
