# Unified speak entrypoint for voice-computer.
# Default: xAI Grok TTS (Carina) via Grok Build OAuth (~/.grok/auth.json).
# Fallback: Windows SAPI if xAI fails or -Local is set.
#
# Usage:
#   .\speak.ps1 -Text "Done."
#   .\speak.ps1 -Text "On it." -Voice carina
#   .\speak.ps1 -Text "..." -Local          # force SAPI
#   .\speak.ps1 -ListVoices
#   .\speak.ps1 -AuthStatus

param(
    [Parameter(Mandatory = $false)]
    [string]$Text = "",

    [Parameter(Mandatory = $false)]
    [string]$Voice = "carina",

    [Parameter(Mandatory = $false)]
    [int]$Rate = 0,

    [switch]$ListVoices,
    [switch]$AuthStatus,
    [switch]$Local,
    [switch]$NoAutoTags,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Scripts = $PSScriptRoot
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { $Python = "C:\Python314\python.exe" }
$SpeakXai = Join-Path $Scripts "speak_xai.py"

function Invoke-Sapi {
    param([string]$Msg, [string]$VoiceName = "", [int]$SpeechRate = 0)
    Add-Type -AssemblyName System.Speech | Out-Null
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    if ($SpeechRate -lt -10) { $SpeechRate = -10 }
    if ($SpeechRate -gt 10) { $SpeechRate = 10 }
    $synth.Rate = $SpeechRate
    if ($VoiceName) {
        $match = $synth.GetInstalledVoices() |
            Where-Object { $_.Enabled -and $_.VoiceInfo.Name -like "*$VoiceName*" } |
            Select-Object -First 1
        if ($match) { $synth.SelectVoice($match.VoiceInfo.Name) }
    }
    try { $synth.SetOutputToDefaultAudioDevice() } catch {}
    $synth.Speak($Msg)
    $synth.Dispose()
}

if ($AuthStatus) {
    if (Test-Path $SpeakXai) {
        & $Python -u $SpeakXai --auth-status
        exit $LASTEXITCODE
    }
    Write-Host "speak_xai.py missing"
    exit 1
}

if ($ListVoices -and -not $Local) {
    if (Test-Path $SpeakXai) {
        & $Python -u $SpeakXai --list-voices
        if ($LASTEXITCODE -eq 0) { exit 0 }
    }
    # fall through to SAPI list
}

if ($ListVoices) {
    Add-Type -AssemblyName System.Speech | Out-Null
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synth.GetInstalledVoices() | ForEach-Object {
        $i = $_.VoiceInfo
        [PSCustomObject]@{ Name = $i.Name; Culture = $i.Culture.Name; Gender = $i.Gender; Enabled = $_.Enabled }
    } | Format-Table -AutoSize
    $synth.Dispose()
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Text)) {
    Write-Error "Pass -Text `"something to say`""
    exit 2
}

if (-not $Local -and (Test-Path $SpeakXai) -and (Test-Path $Python)) {
    $args = @("-u", $SpeakXai, "--voice", $Voice, "--text", $Text)
    if ($NoAutoTags) { $args += "--no-auto-tags" }
    if ($DryRun) { $args += "--dry-run" }
    & $Python @args
    if ($LASTEXITCODE -eq 0) { exit 0 }
    Write-Warning "xAI TTS failed (exit $LASTEXITCODE); falling back to Windows SAPI"
}

# SAPI fallback — strip simple speech tags
$plain = $Text -replace '\[(?:pause|long-pause|laugh|sigh|breath|chuckle)\]', ' '
$plain = $plain -replace '</?[^>]+>', ' '
$plain = $plain -replace '\s+', ' '
$plain = $plain.Trim()
if (-not $plain) { exit 0 }
Invoke-Sapi -Msg $plain -VoiceName "" -SpeechRate $Rate
exit 0
