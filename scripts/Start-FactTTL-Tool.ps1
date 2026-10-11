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
$factttlVenvPython = Join-Path $factttlProject '.venv/Scripts/python.exe'
$factttlVenvConfig = Join-Path $factttlProject '.venv/pyvenv.cfg'
$factttlVerificationDb = '.factttl/verification.sqlite3'
$factttlRuntimeVersion = '0.0.15'
$factttlArchiveName = "tunnel-client-runtime-v$factttlRuntimeVersion-windows-amd64.zip"
$factttlArchiveSha256 = 'aa5ddb14dddd602fa59f3e6f4401aa8a79a218e341466226b7434127dff65dbc'
$factttlExeSha256 = 'a922d372d6be0649156fbc1c8a040597f1f4bb5b4356890151d7875602593b1a'
$factttlRuntimeDir = Join-Path $factttlState "tunnel-runtime-$factttlRuntimeVersion"
$factttlTunnelExe = Join-Path $factttlRuntimeDir 'tunnel-client-runtime.exe'
$factttlSecretFile = Join-Path $factttlState 'control-plane-api-key.dpapi'
$factttlMcpPidFile = Join-Path $factttlState 'factttl-mcp.pid'
$factttlMcpOwnerFile = Join-Path $factttlState 'factttl-mcp.owner.json'
$factttlTunnelPidFile = Join-Path $factttlState 'tunnel-client.pid'
$factttlLaunchState = Join-Path $factttlState 'launch-state.json'

New-Item -ItemType Directory -Path $factttlState -Force | Out-Null

function Get-FactTTLMcpRuntimePaths {
    $paths = @($factttlVenvPython)
    if (Test-Path -LiteralPath $factttlVenvConfig -PathType Leaf) {
        foreach ($line in Get-Content -LiteralPath $factttlVenvConfig) {
            if ($line -match '^\s*(home|executable)\s*=\s*(.+?)\s*$') {
                $configured = $Matches[2]
                $candidate = if ($Matches[1] -eq 'home') { Join-Path $configured 'python.exe' } else { $configured }
                if (Test-Path -LiteralPath $candidate -PathType Leaf) { $paths += $candidate }
            }
        }
    }
    return @($paths | ForEach-Object { [IO.Path]::GetFullPath($_) } | Select-Object -Unique)
}

$factttlMcpRuntimePaths = @(Get-FactTTLMcpRuntimePaths)

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

function Get-LoopbackListenerPid([int]$Port) {
    $owners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object LocalAddress -EQ '127.0.0.1' |
        Select-Object -ExpandProperty OwningProcess -Unique)
    if ($owners.Count -ne 1) { return $null }
    return [int]$owners[0]
}

function Test-ManagedListener([int]$Port, [string]$PidFile, [string[]]$ExpectedPaths) {
    if (-not (Test-Path -LiteralPath $PidFile -PathType Leaf)) { return $false }
    try { $pidValue = [int](Get-Content -LiteralPath $PidFile -Raw) } catch { return $false }
    $listenerPid = Get-LoopbackListenerPid $Port
    if ($null -eq $listenerPid -or $listenerPid -ne $pidValue) { return $false }
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if (-not $process) { return $false }
    try {
        $processPath = [IO.Path]::GetFullPath($process.Path)
        return @($ExpectedPaths | Where-Object { $processPath -eq [IO.Path]::GetFullPath($_) }).Count -eq 1
    } catch { return $false }
}

function Get-ProcessIdentity([int]$ProcessId) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if (-not $process -or [string]::IsNullOrWhiteSpace([string]$process.CommandLine)) { return $null }
    $commandLine = [string]$process.CommandLine
    $commandHash = [Convert]::ToHexString(
        [Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($commandLine))
    ).ToLowerInvariant()
    return [ordered]@{
        pid = $ProcessId
        created_utc_ticks = ([DateTime]$process.CreationDate).ToUniversalTime().Ticks
        command_line_sha256 = $commandHash
    }
}

function Test-FactTTLMcpCommandLine([int]$ProcessId) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if (-not $process) { return $false }
    $commandLine = [string]$process.CommandLine
    $required = @(
        [IO.Path]::GetFullPath($factttlPythonEntry),
        '--transport streamable-http', '--host 127.0.0.1', '--port 8000',
        '--enable-verification', "--verification-db $factttlVerificationDb"
    )
    return @($required | Where-Object { $commandLine.IndexOf($_, [StringComparison]::OrdinalIgnoreCase) -lt 0 }).Count -eq 0
}

function Write-FactTTLMcpOwnerIdentity([int]$ProcessId) {
    if (-not (Test-FactTTLMcpCommandLine $ProcessId)) { throw 'Il processo MCP non ha la riga di comando FactTTL attesa.' }
    $identity = Get-ProcessIdentity $ProcessId
    if ($null -eq $identity) { throw 'Impossibile registrare identita del processo MCP.' }
    $temporary = "$factttlMcpOwnerFile.tmp"
    $identity | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination $factttlMcpOwnerFile -Force
}

function Test-ManagedMcpListener {
    if (-not (Test-ManagedListener 8000 $factttlMcpPidFile $factttlMcpRuntimePaths)) { return $false }
    if (-not (Test-Path -LiteralPath $factttlMcpOwnerFile -PathType Leaf)) { return $false }
    try { $recorded = Get-Content -LiteralPath $factttlMcpOwnerFile -Raw | ConvertFrom-Json } catch { return $false }
    $listenerPid = Get-LoopbackListenerPid 8000
    if ($null -eq $listenerPid -or [int]$recorded.pid -ne $listenerPid) { return $false }
    if (-not (Test-FactTTLMcpCommandLine $listenerPid)) { return $false }
    $actual = Get-ProcessIdentity $listenerPid
    return $null -ne $actual -and
        [long]$recorded.created_utc_ticks -eq [long]$actual.created_utc_ticks -and
        [string]$recorded.command_line_sha256 -eq [string]$actual.command_line_sha256
}

function Test-TcpPort([int]$Port) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.ConnectAsync('127.0.0.1', $Port)
        return $connect.Wait(300) -and $client.Connected
    } catch { return $false } finally { $client.Dispose() }
}

function Wait-ManagedListener([int]$Port, [string[]]$ExpectedPaths, [string]$FailureMessage) {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $listenerPid = Get-LoopbackListenerPid $Port
        if ($null -ne $listenerPid) {
            $listener = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
            if (-not $listener) { throw $FailureMessage }
            try { $listenerPath = [IO.Path]::GetFullPath($listener.Path) } catch { throw $FailureMessage }
            if (@($ExpectedPaths | Where-Object { $listenerPath -eq [IO.Path]::GetFullPath($_) }).Count -ne 1) {
                throw "La porta $Port è stata aperta da un eseguibile inatteso."
            }
            return $listenerPid
        }
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

function Stop-OwnedService([int]$Port, [string]$PidFile, [string[]]$ExpectedPaths, [string]$Label, [switch]$Mcp) {
    $listening = Test-TcpPort $Port
    $owned = if ($Mcp) { Test-ManagedMcpListener } else { Test-ManagedListener $Port $PidFile $ExpectedPaths }
    if ($listening -and -not $owned) {
        throw "La porta $Port è occupata da un processo $Label non gestito da questo launcher."
    }
    # A stale PID file is never authority to terminate a same-path process: it
    # must still be the current owner of this exact loopback listener.
    if (-not $owned) { return }
    $ownedPid = [int](Get-Content -LiteralPath $PidFile -Raw)
    Stop-Process -Id $ownedPid -Force
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if (-not (Test-TcpPort $Port)) {
            Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
            if ($Mcp) { Remove-Item -LiteralPath $factttlMcpOwnerFile -Force -ErrorAction SilentlyContinue }
            return
        }
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

function Get-TunnelControlPlaneHealth {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:18080/health/control-plane' -TimeoutSec 3 -SkipHttpErrorCheck
        if ($response.StatusCode -ne 200) { return $null }
        $health = $response.Content | ConvertFrom-Json
        if ([int]$health.schema_version -ne 1 -or [string]$health.component -ne 'control-plane') { return $null }
        return $health
    } catch { return $null }
}

function Wait-TunnelAuthenticated([Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $health = Get-TunnelControlPlaneHealth
        if ($null -ne $health) {
            if ([string]$health.status -eq 'ok') { return }
            $httpStatus = if ($null -ne $health.details) { [int]$health.details.http_status } else { 0 }
            if ([string]$health.status -eq 'degraded' -and $httpStatus -in @(401, 403)) {
                throw 'La runtime API key non è autorizzata per questo tunnel (401/403).'
            }
        }
        $Process.Refresh()
        if ($Process.HasExited) { break }
        Start-Sleep -Seconds 1
    }
    throw 'Il tunnel locale è vivo, ma non ha confermato un poll autenticato al control plane OpenAI.'
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

$hasExistingService = (Test-TcpPort 8000) -or (Test-TcpPort 18080)
$launchStateMatches = Test-LaunchStateMatches
if ($hasExistingService -and (-not $launchStateMatches -or $ReplaceSavedApiKey)) {
    # Stop the tunnel first so it cannot dispatch requests while MCP restarts.
    Stop-OwnedService 18080 $factttlTunnelPidFile @($factttlTunnelExe) 'tunnel'
    Stop-OwnedService 8000 $factttlMcpPidFile $factttlMcpRuntimePaths 'MCP' -Mcp
}

& (Join-Path $PSScriptRoot 'Setup-FactTTL-News.ps1') -StartOnly -Model $newsModel -InferenceProfile $newsProfile
if ($LASTEXITCODE -ne 0) { throw 'Il motore notizie locale non è pronto.' }

if (Test-TcpPort 8000) {
    if (-not (Test-ManagedMcpListener) -or -not (Test-FactTTLMcp)) { throw 'La porta 8000 è già occupata da un processo non gestito da questo launcher.' }
    $mcpProcess = Get-Process -Id ([int](Get-Content -LiteralPath $factttlMcpPidFile -Raw))
    $startedMcp = $false
} else {
    $mcpEnvironment = @{ FACTTTL_NEWS_MODEL = $newsModel; FACTTTL_NEWS_PROFILE = $newsProfile; FACTTTL_NEWS_DISCOVERY = $newsDiscovery }
    $mcpArguments = @('--transport', 'streamable-http', '--host', '127.0.0.1', '--port', '8000', '--enable-verification', '--verification-db', $factttlVerificationDb)
    $mcpLauncher = Start-Process -FilePath $factttlPythonEntry -ArgumentList $mcpArguments -Environment $mcpEnvironment -WorkingDirectory $factttlProject -WindowStyle Hidden -RedirectStandardOutput (Join-Path $factttlState 'factttl-mcp.out.log') -RedirectStandardError (Join-Path $factttlState 'factttl-mcp.err.log') -PassThru
    $startedMcp = $true
    try {
        $mcpListenerPid = Wait-ManagedListener 8000 $factttlMcpRuntimePaths 'FactTTL MCP non si è avviato: controlla .factttl/mcp-tool/factttl-mcp.err.log.'
        $mcpListenerPid | Set-Content -LiteralPath $factttlMcpPidFile -Encoding ascii
        Write-FactTTLMcpOwnerIdentity $mcpListenerPid
        $mcpProcess = Get-Process -Id $mcpListenerPid -ErrorAction Stop
        if (-not (Test-FactTTLMcp)) { throw 'La porta 8000 risponde ma non come server MCP FactTTL.' }
    } catch {
        try { Stop-OwnedService 8000 $factttlMcpPidFile $factttlMcpRuntimePaths 'MCP' -Mcp }
        finally {
            $mcpLauncher.Refresh()
            if (-not $mcpLauncher.HasExited) { Stop-Process -Id $mcpLauncher.Id -Force }
        }
        throw
    }
}

if (Test-TcpPort 18080) {
    if (-not (Test-ManagedListener 18080 $factttlTunnelPidFile @($factttlTunnelExe))) { throw 'La porta health 18080 è già occupata da un processo non gestito da questo launcher.' }
    if (-not (Test-TunnelEndpoint 'readyz')) { throw 'Il tunnel già avviato non è pronto; controlla .factttl/mcp-tool/tunnel-client.err.log.' }
    $tunnelProcess = Get-Process -Id ([int](Get-Content -LiteralPath $factttlTunnelPidFile -Raw))
    try { Wait-TunnelAuthenticated $tunnelProcess }
    catch {
        Stop-OwnedService 18080 $factttlTunnelPidFile @($factttlTunnelExe) 'tunnel'
        Remove-Item -LiteralPath $factttlLaunchState, $factttlTunnelPidFile -Force -ErrorAction SilentlyContinue
        throw
    }
} else {
    $tunnelLauncher = $null
    try {
        $controlPlaneApiKey = Get-ControlPlaneApiKey
        try {
            $tunnelArguments = @('run', '--control-plane.tunnel-id', $TunnelId, '--control-plane.api-key', 'env:CONTROL_PLANE_API_KEY', '--mcp.server-url', 'url=http://127.0.0.1:8000/mcp', '--mcp.startup-wait-timeout', '15s', '--health.listen-addr', '127.0.0.1:18080')
            $tunnelLauncher = Start-Process -FilePath $factttlTunnelExe -ArgumentList $tunnelArguments -Environment @{ CONTROL_PLANE_API_KEY = $controlPlaneApiKey } -WorkingDirectory $factttlProject -WindowStyle Hidden -RedirectStandardOutput (Join-Path $factttlState 'tunnel-client.out.log') -RedirectStandardError (Join-Path $factttlState 'tunnel-client.err.log') -PassThru
        } finally { $controlPlaneApiKey = $null }
        $tunnelListenerPid = Wait-ManagedListener 18080 @($factttlTunnelExe) 'Il client tunnel non si è avviato: controlla .factttl/mcp-tool/tunnel-client.err.log.'
        $tunnelListenerPid | Set-Content -LiteralPath $factttlTunnelPidFile -Encoding ascii
        $tunnelProcess = Get-Process -Id $tunnelListenerPid -ErrorAction Stop
        if (-not (Test-TunnelEndpoint 'healthz')) { throw 'Il client tunnel non supera /healthz.' }
        $ready = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if (Test-TunnelEndpoint 'readyz') { $ready = $true; break }
            $tunnelProcess.Refresh()
            if ($tunnelProcess.HasExited) { break }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) { throw 'Il tunnel non è pronto. Verifica runtime API key, tunnel ID, permessi Tunnels Read + Use e associazione al workspace.' }
        # /readyz confirms local startup only. The structured control-plane
        # component is the evidence that OpenAI accepted at least one poll.
        Wait-TunnelAuthenticated $tunnelProcess
    } catch {
        try { Stop-OwnedService 18080 $factttlTunnelPidFile @($factttlTunnelExe) 'tunnel' }
        finally {
            if ($null -ne $tunnelLauncher) {
                $tunnelLauncher.Refresh()
                if (-not $tunnelLauncher.HasExited) { Stop-Process -Id $tunnelLauncher.Id -Force }
            }
            if ($startedMcp) { Stop-OwnedService 8000 $factttlMcpPidFile $factttlMcpRuntimePaths 'MCP' -Mcp }
        }
        throw
    }
}

[ordered]@{
    tunnel_id = $TunnelId; mcp_url = 'http://127.0.0.1:8000/mcp'; tunnel_runtime_version = $factttlRuntimeVersion; tunnel_health = 'http://127.0.0.1:18080/healthz'; tunnel_readiness = 'http://127.0.0.1:18080/readyz'; tunnel_diagnostics = 'http://127.0.0.1:18080/health?details=true'; verification_enabled = $true; verification_db = $factttlVerificationDb; news_model = $newsModel; inference_profile = $newsProfile; news_discovery = $newsDiscovery; mcp_pid = $mcpProcess.Id; tunnel_pid = $tunnelProcess.Id
} | ConvertTo-Json | Set-Content -LiteralPath $factttlLaunchState -Encoding utf8

Write-Host 'FactTTL MCP è pronto tramite Secure MCP Tunnel.'
Write-Host 'MCP locale: http://127.0.0.1:8000/mcp'
Write-Host 'Readiness tunnel: http://127.0.0.1:18080/readyz'
Write-Host 'Diagnostica tunnel: http://127.0.0.1:18080/health?details=true'
Write-Host 'In ChatGPT aggiorna gli strumenti della app FactTTL e avvia una nuova chat.'
