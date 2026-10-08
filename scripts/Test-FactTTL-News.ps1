#requires -Version 7.4
[CmdletBinding()]
param([ValidateSet('cpu','balanced','extended')][string]$InferenceProfile='balanced')
$ErrorActionPreference='Stop'
$factttlDiagnostic = [ordered]@{ profile=$InferenceProfile; context_tokens=8192; ram_gb=$null; free_ram_gb=$null; cpu=$null; runtime_ready=$false; installed_models=@(); loaded_models=@(); recommendation='16 GB RAM recommended; run a representative local check before relying on latency.' }
if ($InferenceProfile -eq 'extended') { $factttlDiagnostic.context_tokens=32768 }
try {
    $factttlSystem=Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    $factttlDiagnostic.ram_gb=[Math]::Round($factttlSystem.TotalVisibleMemorySize/1MB,1)
    $factttlDiagnostic.free_ram_gb=[Math]::Round($factttlSystem.FreePhysicalMemory/1MB,1)
    $factttlDiagnostic.cpu=(Get-CimInstance Win32_Processor -ErrorAction Stop | Select-Object -First 1).Name
} catch { $factttlDiagnostic.hardware_query='unavailable; no elevated permissions required' }
try {
    $factttlVersion=Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 3
    $factttlDiagnostic.runtime_ready=[bool]$factttlVersion.version
    $factttlDiagnostic.runtime_version=$factttlVersion.version
    $factttlTags=Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 3
    $factttlDiagnostic.installed_models=@($factttlTags.models | Select-Object name,size)
    $factttlLoaded=Invoke-RestMethod http://127.0.0.1:11434/api/ps -TimeoutSec 3
    $factttlDiagnostic.loaded_models=@($factttlLoaded.models | Select-Object name,size,size_vram)
} catch { $factttlDiagnostic.runtime_error='Local runtime unavailable; no model downloaded or started by diagnostics.' }
$factttlDiagnostic | ConvertTo-Json -Depth 5
