param(
    [string]$Blender = $env:BLENDER_PATH,
    [ValidateSet('none','bedroom','kitchen','desk','overview','all')][string]$Render='all',
    [int]$Resolution=1600,
    [int]$Samples=96
)
$ErrorActionPreference='Stop'
if (-not $Blender) {
    $taskBlenderCommand=Get-Command blender -ErrorAction SilentlyContinue
    if ($taskBlenderCommand) { $Blender=$taskBlenderCommand.Source }
}
if (-not $Blender -or -not (Test-Path -LiteralPath $Blender)) { throw 'Set BLENDER_PATH or pass -Blender with the path to Blender 4.5 LTS.' }
$taskProjectRoot=Split-Path $PSScriptRoot -Parent
Push-Location $taskProjectRoot
try {
    & $Blender --background --python-exit-code 1 --python scripts/build_scene.py -- --render $Render --resolution $Resolution --samples $Samples
    if ($LASTEXITCODE -ne 0) { throw 'Blender build failed.' }
    New-Item -ItemType Directory -Force -Path demo/public/renders | Out-Null
    Copy-Item -Path renders/*.jpg -Destination demo/public/renders -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath scene/scene-manifest.json -Destination demo/public/scene-manifest.json
} finally { Pop-Location }
