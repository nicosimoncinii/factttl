param(
    [string]$ExtensionOrigin = '',
    [string]$NewsModel = '',
    [switch]$DisableNews,
    [ValidateSet('cpu', 'balanced', 'extended')][string]$InferenceProfile = '',
    [ValidateSet('disabled', 'bing')][string]$NewsDiscovery = ''
)

$ErrorActionPreference = 'Stop'
$factttlProject = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$factttlPython = Join-Path $factttlProject '.venv/Scripts/python.exe'
$factttlState = Join-Path $factttlProject '.factttl'
$factttlConfig = Join-Path $factttlState 'extension-config.json'
$factttlNewsConfig = Join-Path $factttlState 'news-model.json'
if (Test-Path -LiteralPath $factttlNewsConfig) {
    $factttlSavedNews = Get-Content -LiteralPath $factttlNewsConfig -Raw | ConvertFrom-Json
    if (-not $NewsModel -and -not $DisableNews) { $NewsModel = $factttlSavedNews.model }
    if (-not $InferenceProfile) { $InferenceProfile = $factttlSavedNews.inference_profile }
    if (-not $NewsDiscovery) { $NewsDiscovery = $factttlSavedNews.news_discovery }
}
if ($NewsModel -and ($NewsModel -notmatch '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$' -or $NewsModel -match '(?i)cloud|://')) {
    throw 'Nome del modello locale non valido.'
}
if (-not $InferenceProfile) { $InferenceProfile = 'balanced' }
if ($InferenceProfile -notin @('cpu', 'balanced', 'extended')) { throw 'Profilo locale non valido.' }
if (-not $NewsDiscovery) { $NewsDiscovery = 'disabled' }
if ($NewsDiscovery -notin @('disabled', 'bing')) { throw 'Provider ricerca notizie non valido.' }
if ($DisableNews) {
    # Disabling news includes the external search path, not only local inference.
    $NewsModel = ''
    $NewsDiscovery = 'disabled'
}
if (-not $ExtensionOrigin -and (Test-Path -LiteralPath $factttlConfig)) {
    $factttlPreviousSettings = Get-Content -LiteralPath $factttlConfig -Raw | ConvertFrom-Json
    $ExtensionOrigin = $factttlPreviousSettings.allowed_origin
}
if (-not $ExtensionOrigin) { $ExtensionOrigin = 'chrome-extension://nfnnmjcbjidblifbdfkhbdiidgcjbiem' }
if ($ExtensionOrigin -notmatch '^(chrome-extension://[a-p]{32}|moz-extension://[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$') {
    throw 'Origine estensione non valida: usa quella mostrata nelle opzioni FactTTL.'
}
if (-not (Test-Path -LiteralPath $factttlPython)) {
    throw 'Ambiente Python mancante: prepara .venv come indicato nel README.'
}
New-Item -ItemType Directory -Path $factttlState -Force | Out-Null
@{model = $NewsModel; inference_profile = $InferenceProfile; news_discovery = $NewsDiscovery} | ConvertTo-Json | Set-Content -LiteralPath $factttlNewsConfig
if ($NewsModel -and (Test-Path -LiteralPath (Join-Path $factttlState 'runtime/installed.json'))) {
    & (Join-Path $PSScriptRoot 'Setup-FactTTL-News.ps1') -StartOnly -InferenceProfile $InferenceProfile
}

function Test-FactTTLBridge {
    if (-not (Test-Path -LiteralPath $factttlConfig)) { return $false }
    try {
        $factttlSettings = Get-Content -LiteralPath $factttlConfig -Raw | ConvertFrom-Json
        if ($factttlSettings.allowed_origin -ne $ExtensionOrigin) { return $false }
        $factttlHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2 -Headers @{
            Authorization = 'Bearer ' + $factttlSettings.token
            'X-FactTTL-Origin' = $factttlSettings.allowed_origin
        }
        return $factttlHealth.status -eq 'ready' -and $factttlHealth.service -eq 'FactTTL'
    } catch { return $false }
}

if (Test-FactTTLBridge) {
    $factttlCurrentSettings = Get-Content -LiteralPath $factttlConfig -Raw | ConvertFrom-Json
    $factttlCurrentHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -Headers @{
        Authorization = 'Bearer ' + $factttlCurrentSettings.token
        'X-FactTTL-Origin' = $factttlCurrentSettings.allowed_origin
    }
    if ([string]$factttlCurrentHealth.news_engine.model -ne $NewsModel -or ($NewsModel -and [string]$factttlCurrentHealth.news_engine.inference_profile -ne $InferenceProfile) -or [string]$factttlCurrentHealth.news_engine.discovery_provider -ne $NewsDiscovery) {
        throw 'Configurazione salvata. Riavvia il servizio FactTTL già attivo per applicarla.'
    }
} else {
    $factttlArguments = @('-m', 'factttl.browser_bridge', '--extension-origin', $ExtensionOrigin)
    if ($NewsModel) { $factttlArguments += @('--news-model', $NewsModel) }
    $factttlProcess = Start-Process -FilePath $factttlPython -ArgumentList $factttlArguments -Environment @{ FACTTTL_NEWS_PROFILE = $InferenceProfile; FACTTTL_NEWS_DISCOVERY = $NewsDiscovery } -WorkingDirectory $factttlProject -WindowStyle Hidden -RedirectStandardOutput (Join-Path $factttlState 'browser.out.log') -RedirectStandardError (Join-Path $factttlState 'browser.err.log') -PassThru
    $factttlProcess.Id | Set-Content -LiteralPath (Join-Path $factttlState 'browser.pid')
    for ($factttlAttempt = 0; $factttlAttempt -lt 20; $factttlAttempt++) {
        if (Test-FactTTLBridge) { break }
        if ($factttlProcess.HasExited) { throw 'Avvio non riuscito: controlla .factttl/browser.err.log.' }
        Start-Sleep -Milliseconds 250
    }
    if (-not (Test-FactTTLBridge)) { throw 'Il servizio locale non risponde sulla porta 8765.' }
}

Write-Host 'FactTTL pronto: il servizio locale resta attivo in background.'
$factttlPackage = if ($ExtensionOrigin.StartsWith('moz-extension://')) { 'integrations/firefox-extension' } else { 'integrations/chatgpt-extension' }
Write-Host ('Estensione da caricare: ' + (Join-Path $factttlProject $factttlPackage))
Write-Host ('Configurazione da importare nelle opzioni: ' + $factttlConfig)
Write-Host "In ChatGPT attiva FactTTL con l'interruttore della chat."
