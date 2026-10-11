#requires -Version 7.4
<#!
Starts FactTTL's native MCP tools on loopback and connects them to an existing
OpenAI Secure MCP Tunnel. The runtime API key is never put on the command line
or written as plaintext; when entered interactively it is protected with Windows
DPAPI for the current user.
!#>
[CmdletBinding()]
param(
    [string]$TunnelId = $env:CONTROL_PLANE_TUNNEL_ID,
    [string]$RuntimeArchive = '',
    [switch]$ValidateRuntimeOnly,
    [switch]$ReplaceSavedApiKey
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if (-not $IsWindows -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'Questo launcher richiede Windows x64.'
}

$factttlProject = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$factttlState = Join-Path $factttlProject '.factttl/mcp-tool'
$factttlNewsConfig = Join-Path $factttlProject '.factttl/news-model.json'
$factttlPythonEntry = Join-Path $factttlProject '.venv/Scripts/factttl-mcp.exe'
$factttlVerificationDb = '.factttl/verification.sqlite3'
$factttlRuntimeVersion = '0.0.15'
$factttlArchiveName = "tunnel-client-runtime-v$factttlRuntimeVersion-windows-amd64.zip"
$factttlArchiveSha256 = 'aa5ddb14dddd602fa59f3e6f4401aa8a79a218e341466226b7434127dff65dbc'
$factttlExeSha256 = 'a922d372d6be0649156fbc1c8a040597f1f4bb5b4356890151d7875602593b1a'
$factttlRuntimeDir = Join-Path $factttlState "tunnel-runtime-$factttlRuntimeVersion"
$factttlTunnelExe = Join-Path $factttlRuntimeDir 'tunnel-client-runtime.exe'
$factttlSecretFile = Join-Path $factttlState 'control-plane-api-key.dpapi'
$factttlMcpPidFile = Join-Path $factttlState 'factttl-mcp.pid'
$factttlTunnelPidFile = Join-Path $factttlState 'tunnel-client.pid'
$factttlLaunchState = Join-Path $factttlState 'launch-state.json'

New-Item -ItemType Directory -Path $factttlState -Force | Out-Null

function Find-FactTTLRuntimeArchive {
    if ($RuntimeArchive) {
        $candidate = [IO.Path]::GetFullPath($RuntimeArchive)
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw "ZIP runtime non trovata: $candidate" }
        return $candidate
    }
    # A later start does not depend on retaining the downloaded ZIP. The
    # installed executable is still checked against the pinned hash and version.
    if (Test-Path -LiteralPath $factttlTunnelExe -PathType Leaf) { return $null }
    $candidates = @(
        (Join-Path $factttlState $factttlArchiveName),
        (Join-Path ([Environment]::GetFolderPath('UserProfile')) "Downloads/$factttlArchiveName")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return [IO.Path]::GetFullPath($candidate) }
    }
    throw "Runtime OpenAI mancante. Scarica $factttlArchiveName dalle impostazioni Tunnel di OpenAI Platform oppure passalo con -RuntimeArchive."
}

function Read-ZipEntryText([IO.Compression.ZipArchiveEntry]$Entry) {
    $stream = $Entry.Open()
    $reader = [IO.StreamReader]::new($stream)
    try { return $reader.ReadToEnd() } finally { $reader.Dispose(); $stream.Dispose() }
}

function Install-FactTTLTunnelRuntime([string]$ArchivePath) {
    if ([string]::IsNullOrWhiteSpace($ArchivePath)) {
        $installedHash = (Get-FileHash -LiteralPath $factttlTunnelExe -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($installedHash -ne $factttlExeSha256) { throw 'Runtime tunnel installata non valida; fornisci nuovamente la ZIP ufficiale con -RuntimeArchive.' }
        $installedVersion = (& $factttlTunnelExe --version 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $installedVersion -notmatch '^0\.0\.15\b.*\bflavor=runtime\b') { throw 'Versione della runtime tunnel installata diversa da quella validata.' }
        return
    }
    $archiveHash = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($archiveHash -ne $factttlArchiveSha256) {
        throw "SHA256 della ZIP runtime non riconosciuto per la versione $factttlRuntimeVersion. Il file non viene estratto né eseguito."
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $expectedEntries = @(
        'tunnel-client-runtime.exe', 'LICENSE', 'NOTICE',
        "tunnel-client-runtime-v$factttlRuntimeVersion-windows-amd64-licenses.txt",
        "tunnel-client-runtime-v$factttlRuntimeVersion-windows-amd64.spdx.json"
    )
    $zip = [IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        $actualEntries = @($zip.Entries | ForEach-Object FullName)
        if ($actualEntries.Count -ne $expectedEntries.Count -or @($actualEntries | Where-Object { $_ -notin $expectedEntries }).Count -ne 0) {
            throw 'La ZIP runtime non contiene esattamente i file attesi; installazione interrotta.'
        }
        if (($zip.Entries | Measure-Object -Property Length -Sum).Sum -gt 64MB) { throw 'La ZIP runtime supera il limite di dimensione previsto.' }
        if ((Read-ZipEntryText $zip.GetEntry('NOTICE')) -notmatch 'Copyright 2026 OpenAI') { throw 'NOTICE della runtime non riconosciuto.' }
        $spdx = Read-ZipEntryText $zip.GetEntry("tunnel-client-runtime-v$factttlRuntimeVersion-windows-amd64.spdx.json") | ConvertFrom-Json
        if ($spdx.name -ne 'tunnel-client-runtime') { throw 'Manifesto SPDX della runtime non riconosciuto.' }

        if (-not (Test-Path -LiteralPath $factttlTunnelExe -PathType Leaf)) {
            New-Item -ItemType Directory -Path $factttlRuntimeDir -Force | Out-Null
            $installPrefix = [IO.Path]::GetFullPath($factttlRuntimeDir) + [IO.Path]::DirectorySeparatorChar
            foreach ($entry in $zip.Entries) {
                $destination = [IO.Path]::GetFullPath((Join-Path $factttlRuntimeDir $entry.FullName))
                if (-not $destination.StartsWith($installPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Percorso non valido dentro la ZIP runtime; estrazione interrotta.' }
                $entryStream = $entry.Open()
                $destinationStream = [IO.File]::Create($destination)
                try { $entryStream.CopyTo($destinationStream) } finally { $destinationStream.Dispose(); $entryStream.Dispose() }
            }
        }
    } finally { $zip.Dispose() }

    $exeHash = (Get-FileHash -LiteralPath $factttlTunnelExe -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($exeHash -ne $factttlExeSha256) { throw 'Eseguibile tunnel estratto non valido; non viene avviato.' }
    $versionOutput = (& $factttlTunnelExe --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch '^0\.0\.15\b.*\bflavor=runtime\b') { throw 'Versione della runtime tunnel diversa da quella validata.' }
}

function Test-ManagedProcess([string]$PidFile, [string]$ExpectedPath) {
    if (-not (Test-Path -LiteralPath $PidFile -PathType Leaf)) { return $false }
    try { $pidValue = [int](Get-Content -LiteralPath $PidFile -Raw) } catch { return $false }
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if (-not $process) { return $false }
    try { return [IO.Path]::GetFullPath($process.Path) -eq [IO.Path]::GetFullPath($ExpectedPath) } catch { return $false }
}

function Test-TcpPort([int]$Port) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.ConnectAsync('127.0.0.1', $Port)
        return $connect.Wait(300) -and $client.Connected
    } catch { return $false } finally { $client.Dispose() }
}

function Wait-TcpPort([int]$Port, [Diagnostics.Process]$Process, [string]$FailureMessage) {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if (Test-TcpPort $Port) { return }
        $Process.Refresh()
        if ($Process.HasExited) { throw $FailureMessage }
        Start-Sleep -Milliseconds 250
    }
    throw $FailureMessage
}

function Test-FactTTLMcp {
    $headers = @{ Accept = 'application/json, text/event-stream' }
    $body = @{ jsonrpc = '2.0'; id = 1; method = 'initialize'; params = @{ protocolVersion = '2025-06-18'; capabilities = @{}; clientInfo = @{ name = 'factttl-launcher'; version = '1.0' } } } | ConvertTo-Json -Depth 5 -Compress
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/mcp' -Method Post -ContentType 'application/json' -Headers $headers -Body $body -TimeoutSec 5 -SkipHttpErrorCheck
        if ($response.StatusCode -ne 200 -or $response.Content -notmatch '"name"\s*:\s*"FactTTL"') { return $false }
        $sessionId = @($response.Headers['Mcp-Session-Id'])[0]
        if ([string]::IsNullOrWhiteSpace($sessionId)) { return $false }
        $sessionHeaders = @{ Accept = 'application/json, text/event-stream'; 'Mcp-Session-Id' = $sessionId }
        $initialized = @{ jsonrpc = '2.0'; method = 'notifications/initialized' } | ConvertTo-Json -Compress
        $notification = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/mcp' -Method Post -ContentType 'application/json' -Headers $sessionHeaders -Body $initialized -TimeoutSec 5 -SkipHttpErrorCheck
        if ($notification.StatusCode -notin @(200, 202)) { return $false }
        $toolsRequest = @{ jsonrpc = '2.0'; id = 2; method = 'tools/list'; params = @{} } | ConvertTo-Json -Compress
        $tools = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/mcp' -Method Post -ContentType 'application/json' -Headers $sessionHeaders -Body $toolsRequest -TimeoutSec 5 -SkipHttpErrorCheck
        return $tools.StatusCode -eq 200 -and
            $tools.Content -match '"name"\s*:\s*"verify_answer"' -and
            $tools.Content -match '"name"\s*:\s*"verify_recommendations"'
    } catch { return $false }
}

function Test-LaunchStateMatches {
    if (-not (Test-Path -LiteralPath $factttlLaunchState -PathType Leaf)) { return $false }
    try { $saved = Get-Content -LiteralPath $factttlLaunchState -Raw | ConvertFrom-Json } catch { return $false }
    try {
        $recordedMcpPid = [int](Get-Content -LiteralPath $factttlMcpPidFile -Raw)
        $recordedTunnelPid = [int](Get-Content -LiteralPath $factttlTunnelPidFile -Raw)
    } catch { return $false }
    return [string]$saved.tunnel_id -eq $TunnelId -and
        [string]$saved.mcp_url -eq 'http://127.0.0.1:8000/mcp' -and
        [string]$saved.tunnel_runtime_version -eq $factttlRuntimeVersion -and
        $saved.verification_enabled -eq $true -and
        [string]$saved.verification_db -eq $factttlVerificationDb -and
        [string]$saved.news_model -eq $newsModel -and
        [string]$saved.inference_profile -eq $newsProfile -and
        [string]$saved.news_discovery -eq $newsDiscovery -and
        [int]$saved.mcp_pid -eq $recordedMcpPid -and
        [int]$saved.tunnel_pid -eq $recordedTunnelPid
}

function Stop-OwnedService([int]$Port, [string]$PidFile, [string]$ExpectedPath, [string]$Label) {
    $listening = Test-TcpPort $Port
    $owned = Test-ManagedProcess $PidFile $ExpectedPath
    if ($listening -and -not $owned) {
        throw "La porta $Port è occupata da un processo $Label non gestito da questo launcher."
    }
    if (-not $owned) { return }
    $ownedPid = [int](Get-Content -LiteralPath $PidFile -Raw)
    Stop-Process -Id $ownedPid -Force
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if (-not (Test-TcpPort $Port)) { return }
        Start-Sleep -Milliseconds 250
    }
    throw "Il processo $Label verificato è stato arrestato, ma la porta $Port è ancora occupata."
}

function Test-TunnelEndpoint([string]$Path) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:18080/$Path" -TimeoutSec 3 -SkipHttpErrorCheck
        return $response.StatusCode -eq 200
    } catch { return $false }
}

function Get-ControlPlaneApiKey {
    if (-not $ReplaceSavedApiKey -and -not [string]::IsNullOrWhiteSpace($env:CONTROL_PLANE_API_KEY)) { return $env:CONTROL_PLANE_API_KEY }
    if (-not $ReplaceSavedApiKey -and (Test-Path -LiteralPath $factttlSecretFile -PathType Leaf)) {
        try { $secure = Get-Content -LiteralPath $factttlSecretFile -Raw | ConvertTo-SecureString }
        catch { throw 'Chiave DPAPI non leggibile per questo utente Windows. Usa -ReplaceSavedApiKey.' }
    } else {
        $secure = Read-Host 'Incolla la runtime API key OpenAI (input nascosto)' -AsSecureString
        if ($secure.Length -lt 20) { throw 'Runtime API key assente o troppo corta.' }
        $secure | ConvertFrom-SecureString | Set-Content -LiteralPath $factttlSecretFile -Encoding ascii
    }
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

$runtimeArchivePath = Find-FactTTLRuntimeArchive
Install-FactTTLTunnelRuntime $runtimeArchivePath
if ($ValidateRuntimeOnly) {
    Write-Host "Runtime OpenAI $factttlRuntimeVersion validata e pronta: $factttlTunnelExe"
    return
}

if ($TunnelId -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$' -or $TunnelId -match '(?i)example|replace|your|<|>|0{16,}') {
    throw 'Tunnel ID mancante o non valido. Passa il tunnel_id reale di OpenAI Platform con -TunnelId; non usare un valore di esempio.'
}
if (-not (Test-Path -LiteralPath $factttlPythonEntry -PathType Leaf)) { throw 'Entrypoint MCP mancante: installa prima FactTTL con extra MCP nella .venv.' }
if (-not (Test-Path -LiteralPath $factttlNewsConfig -PathType Leaf)) { throw 'Configurazione .factttl/news-model.json mancante.' }

$news = Get-Content -LiteralPath $factttlNewsConfig -Raw | ConvertFrom-Json
$newsModel = [string]$news.model
$newsProfile = [string]$news.inference_profile
$newsDiscovery = [string]$news.news_discovery
if ($newsModel -notmatch '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$' -or $newsModel -match '(?i)cloud|://') { throw 'Modello locale non valido in .factttl/news-model.json.' }
if ($newsProfile -notin @('cpu', 'balanced', 'extended')) { throw 'Profilo locale non valido in .factttl/news-model.json.' }
if ($newsDiscovery -notin @('disabled', 'bing')) { throw 'Provider discovery non valido in .factttl/news-model.json.' }

$hasExistingService = (Test-TcpPort 8000) -or (Test-TcpPort 18080) -or
    (Test-ManagedProcess $factttlMcpPidFile $factttlPythonEntry) -or
    (Test-ManagedProcess $factttlTunnelPidFile $factttlTunnelExe)
if ($hasExistingService -and -not (Test-LaunchStateMatches)) {
    # Stop the tunnel first so it cannot dispatch requests while MCP restarts.
    Stop-OwnedService 18080 $factttlTunnelPidFile $factttlTunnelExe 'tunnel'
    Stop-OwnedService 8000 $factttlMcpPidFile $factttlPythonEntry 'MCP'
}
# A matching state cannot make a non-listening process reusable. Clean up only
# the exact PID-file-owned executable before starting its replacement.
if (-not (Test-TcpPort 18080) -and (Test-ManagedProcess $factttlTunnelPidFile $factttlTunnelExe)) {
    Stop-OwnedService 18080 $factttlTunnelPidFile $factttlTunnelExe 'tunnel'
}
if (-not (Test-TcpPort 8000) -and (Test-ManagedProcess $factttlMcpPidFile $factttlPythonEntry)) {
    Stop-OwnedService 8000 $factttlMcpPidFile $factttlPythonEntry 'MCP'
}

& (Join-Path $PSScriptRoot 'Setup-FactTTL-News.ps1') -StartOnly -Model $newsModel -InferenceProfile $newsProfile
if ($LASTEXITCODE -ne 0) { throw 'Il motore notizie locale non è pronto.' }

if (Test-TcpPort 8000) {
    if (-not (Test-ManagedProcess $factttlMcpPidFile $factttlPythonEntry) -or -not (Test-FactTTLMcp)) { throw 'La porta 8000 è già occupata da un processo non gestito da questo launcher.' }
    $mcpProcess = Get-Process -Id ([int](Get-Content -LiteralPath $factttlMcpPidFile -Raw))
    $startedMcp = $false
} else {
    $mcpEnvironment = @{ FACTTTL_NEWS_MODEL = $newsModel; FACTTTL_NEWS_PROFILE = $newsProfile; FACTTTL_NEWS_DISCOVERY = $newsDiscovery }
    $mcpArguments = @('--transport', 'streamable-http', '--host', '127.0.0.1', '--port', '8000', '--enable-verification', '--verification-db', $factttlVerificationDb)
    $mcpProcess = Start-Process -FilePath $factttlPythonEntry -ArgumentList $mcpArguments -Environment $mcpEnvironment -WorkingDirectory $factttlProject -WindowStyle Hidden -RedirectStandardOutput (Join-Path $factttlState 'factttl-mcp.out.log') -RedirectStandardError (Join-Path $factttlState 'factttl-mcp.err.log') -PassThru
    $mcpProcess.Id | Set-Content -LiteralPath $factttlMcpPidFile -Encoding ascii
    $startedMcp = $true
    try {
        Wait-TcpPort 8000 $mcpProcess 'FactTTL MCP non si è avviato: controlla .factttl/mcp-tool/factttl-mcp.err.log.'
        if (-not (Test-FactTTLMcp)) { throw 'La porta 8000 risponde ma non come server MCP FactTTL.' }
    } catch {
        if (-not $mcpProcess.HasExited) { Stop-Process -Id $mcpProcess.Id -Force }
        throw
    }
}

if (Test-TcpPort 18080) {
    if (-not (Test-ManagedProcess $factttlTunnelPidFile $factttlTunnelExe)) { throw 'La porta health 18080 è già occupata da un processo non gestito da questo launcher.' }
    if (-not (Test-TunnelEndpoint 'readyz')) { throw 'Il tunnel già avviato non è pronto; controlla .factttl/mcp-tool/tunnel-client.err.log.' }
    $tunnelProcess = Get-Process -Id ([int](Get-Content -LiteralPath $factttlTunnelPidFile -Raw))
} else {
    $controlPlaneApiKey = Get-ControlPlaneApiKey
    try {
        $tunnelArguments = @('run', '--control-plane.tunnel-id', $TunnelId, '--control-plane.api-key', 'env:CONTROL_PLANE_API_KEY', '--mcp.server-url', 'url=http://127.0.0.1:8000/mcp', '--mcp.startup-wait-timeout', '15s', '--health.listen-addr', '127.0.0.1:18080')
        $tunnelProcess = Start-Process -FilePath $factttlTunnelExe -ArgumentList $tunnelArguments -Environment @{ CONTROL_PLANE_API_KEY = $controlPlaneApiKey } -WorkingDirectory $factttlProject -WindowStyle Hidden -RedirectStandardOutput (Join-Path $factttlState 'tunnel-client.out.log') -RedirectStandardError (Join-Path $factttlState 'tunnel-client.err.log') -PassThru
        $tunnelProcess.Id | Set-Content -LiteralPath $factttlTunnelPidFile -Encoding ascii
    } finally { $controlPlaneApiKey = $null }
    try {
        Wait-TcpPort 18080 $tunnelProcess 'Il client tunnel non si è avviato: controlla .factttl/mcp-tool/tunnel-client.err.log.'
        if (-not (Test-TunnelEndpoint 'healthz')) { throw 'Il client tunnel non supera /healthz.' }
        $ready = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if (Test-TunnelEndpoint 'readyz') { $ready = $true; break }
            $tunnelProcess.Refresh()
            if ($tunnelProcess.HasExited) { break }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) { throw 'Il tunnel non è pronto. Verifica runtime API key, tunnel ID, permessi Tunnels Read + Use e associazione al workspace.' }
    } catch {
        if (-not $tunnelProcess.HasExited) { Stop-Process -Id $tunnelProcess.Id -Force }
        if ($startedMcp -and -not $mcpProcess.HasExited) { Stop-Process -Id $mcpProcess.Id -Force }
        throw
    }
}

[ordered]@{
    tunnel_id = $TunnelId; mcp_url = 'http://127.0.0.1:8000/mcp'; tunnel_runtime_version = $factttlRuntimeVersion; tunnel_health = 'http://127.0.0.1:18080/healthz'; tunnel_readiness = 'http://127.0.0.1:18080/readyz'; tunnel_ui = 'http://127.0.0.1:18080/ui'; verification_enabled = $true; verification_db = $factttlVerificationDb; news_model = $newsModel; inference_profile = $newsProfile; news_discovery = $newsDiscovery; mcp_pid = $mcpProcess.Id; tunnel_pid = $tunnelProcess.Id
} | ConvertTo-Json | Set-Content -LiteralPath $factttlLaunchState -Encoding utf8

Write-Host 'FactTTL MCP è pronto tramite Secure MCP Tunnel.'
Write-Host 'MCP locale: http://127.0.0.1:8000/mcp'
Write-Host 'Readiness tunnel: http://127.0.0.1:18080/readyz'
Write-Host 'Stato locale tunnel: http://127.0.0.1:18080/ui'
Write-Host 'In ChatGPT aggiorna gli strumenti della app FactTTL e avvia una nuova chat.'
