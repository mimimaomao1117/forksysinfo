# Generate English narration for build_video.py using an installed Windows voice.
param([string]$WorkDirectory = "$PSScriptRoot/../work/video")
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$timeline = Get-Content -LiteralPath "$PSScriptRoot/../media/video_timeline.json" -Raw -Encoding utf8 | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $WorkDirectory | Out-Null
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice($timeline.voice)
$synth.Rate = 0
$synth.Volume = 100
$index = 0
try {
    foreach ($chapter in $timeline.chapters) {
        foreach ($cue in $chapter.cues) {
            $target = Join-Path $WorkDirectory ('speech_{0:00}.wav' -f $index)
            $synth.SetOutputToWaveFile($target)
            $spoken = if ($cue.speech) { $cue.speech } else { $cue.text }
            $synth.Speak([string]$spoken)
            $synth.SetOutputToNull()
            $index++
        }
    }
} finally {
    $synth.Dispose()
}
Write-Output "Generated $index English narration cues in $WorkDirectory"
