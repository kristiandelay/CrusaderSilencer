param([string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8', [switch]$Automation)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$ProjectFile = Join-Path $ProjectRoot 'src\CrusaderSilencer.uproject'
$Editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$EditorArgs = @('"' + $ProjectFile + '"', '/Game/Maps/L_TraversalGym', '-NoHotReload', '-Multiprocess')
if ($Automation) {
    $BridgeFile = Join-Path $PSScriptRoot 'EditorBridge.py'
    $EditorArgs += '-ExecutePythonScript="' + $BridgeFile + '"'
}
Start-Process -FilePath $Editor -ArgumentList $EditorArgs -PassThru | Select-Object Id,ProcessName
