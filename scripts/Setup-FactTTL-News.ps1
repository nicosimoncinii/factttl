#requires -Version 7.4
<#!
Downloads a pinned official standalone Ollama runtime and the explicitly selected
local model into this project. No registry, PATH, Windows service or cloud setup.
Use -StartOnly after installation to restart the same loopback daemon.
!#>
[CmdletBinding()]
param(
    [ValidateSet('qwen3:4b')]
    [string]$Model = 'qwen3:4b',
    [switch]$StartOnly
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$factttlProject = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$factttlRuntime = Join-Path $factttlProject '.factttl/runtime'
$factttlVersion = '0.40.0'
$factttlArchive = Join-Path $factttlRuntime "ollama-windows-amd64-$factttlVersion.zip"
$factttlInstall = Join-Path $factttlRuntime "ollama-$factttlVersion"
$factttlExe = Join-Path $factttlInstall 'ollama.exe'
$factttlArchiveHash = '3623e256762ca89bd6fa99b0cc4106401919ce9df926411673e632e3ea287bb5'
$factttlSource = "https://github.com/ollama/ollama/releases/download/v$factttlVersion/ollama-windows-amd64.zip"
$factttlModels = Join-Path $factttlRuntime 'models'
$factttlProfile = Join-Path $factttlRuntime 'profile'
$factttlTmp = Join-Path $factttlRuntime 'tmp'
$factttlPidFile = Join-Path $factttlRuntime 'ollama.pid'
$factttlStateFile = Join-Path $factttlRuntime 'installed.json'

if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw 'Questo script standalone richiede Windows x64.'
}
foreach ($factttlDirectory in @($factttlRuntime, $factttlModels, $factttlProfile, $factttlTmp)) {
    New-Item -ItemType Directory -Path $factttlDirectory -Force | Out-Null
}

function Test-FactTTLOllama {
    try {
        $factttlResponse = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
        return [bool]$factttlResponse.version
    } catch { return $false }
}

if (-not (Test-Path -LiteralPath $factttlExe)) {
    if ($StartOnly) { throw 'Runtime locale mancante: esegui prima lo script senza -StartOnly.' }
    $factttlDiskRoot = [IO.Path]::GetPathRoot($factttlProject)
    $factttlDisk = [IO.DriveInfo]::new($factttlDiskRoot)
    if ($factttlDisk.AvailableFreeSpace -lt 10GB) { throw 'Servono almeno 10GB liberi per runtime, archivio e modello.' }
    if (-not (Test-Path -LiteralPath $factttlArchive)) {
        Write-Host 'Scarico Ollama standalone ufficiale v0.40.0 (circa 1.47 GB).'
        Invoke-WebRequest -Uri $factttlSource -OutFile $factttlArchive -TimeoutSec 1800
    }
    $factttlActualHash = (Get-FileHash -LiteralPath $factttlArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($factttlActualHash -ne $factttlArchiveHash) {
        throw 'Hash del download non valido: il file non viene estratto né eseguito.'
    }
    Write-Host 'SHA256 ufficiale verificato. Estraggo nella cartella del progetto.'
    # Validate every destination before any extraction; a future archive must
    # never write above the explicitly named project-local runtime directory.
    $factttlZip = [IO.Compression.ZipFile]::OpenRead($factttlArchive)
    try {
        $factttlInstallPrefix = [IO.Path]::GetFullPath($factttlInstall) + [IO.Path]::DirectorySeparatorChar
        foreach ($factttlEntry in $factttlZip.Entries) {
            $factttlDestination = [IO.Path]::GetFullPath((Join-Path $factttlInstall $factttlEntry.FullName))
            if (-not $factttlDestination.StartsWith($factttlInstallPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Percorso non valido dentro archivio: estrazione interrotta.'
            }
        }
    } finally { $factttlZip.Dispose() }
    Expand-Archive -LiteralPath $factttlArchive -DestinationPath $factttlInstall -Force
    if (-not (Test-Path -LiteralPath $factttlExe)) { throw 'Archivio ufficiale privo del CLI atteso.' }
    # The verified archive is redundant after extraction. Remove only this
    # explicitly named file inside the project, preserving binaries and models.
    $factttlArchivePath = [IO.Path]::GetFullPath($factttlArchive)
    $factttlRuntimePrefix = [IO.Path]::GetFullPath($factttlRuntime) + [IO.Path]::DirectorySeparatorChar
    if (-not $factttlArchivePath.StartsWith($factttlRuntimePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Percorso archivio fuori dal runtime: pulizia interrotta.'
    }
    Remove-Item -LiteralPath $factttlArchivePath
}

if (Test-FactTTLOllama) {
    if (-not (Test-Path -LiteralPath $factttlPidFile)) {
        throw 'Porta 11434 già occupata da un Ollama esterno: non ne modifico la configurazione.'
    }
    $factttlRecordedPid = [int](Get-Content -LiteralPath $factttlPidFile -Raw)
    $factttlOwnedProcess = Get-Process -Id $factttlRecordedPid -ErrorAction SilentlyContinue
    if (-not $factttlOwnedProcess -or $factttlOwnedProcess.Path -ne $factttlExe) {
        throw 'La porta 11434 risponde ma non appartiene al runtime locale registrato.'
    }
} else {
    Write-Host 'Avvio Ollama locale in background, cloud disabilitato.'
    $factttlEnvironment = @{
        OLLAMA_HOST = '127.0.0.1:11434'
        OLLAMA_MODELS = $factttlModels
        OLLAMA_NO_CLOUD = '1'
        OLLAMA_NOHISTORY = '1'
        OLLAMA_CONTEXT_LENGTH = '32768'
        OLLAMA_NUM_PARALLEL = '1'
        OLLAMA_MAX_LOADED_MODELS = '1'
        OLLAMA_FLASH_ATTENTION = '1'
        OLLAMA_KV_CACHE_TYPE = 'q8_0'
        OLLAMA_DEBUG_LOG_REQUESTS = '0'
        USERPROFILE = $factttlProfile
        TEMP = $factttlTmp
        TMP = $factttlTmp
    }
    $factttlDaemon = Start-Process -FilePath $factttlExe -ArgumentList @('serve') -Environment $factttlEnvironment -WorkingDirectory $factttlRuntime -WindowStyle Hidden -RedirectStandardOutput (Join-Path $factttlRuntime 'ollama.out.log') -RedirectStandardError (Join-Path $factttlRuntime 'ollama.err.log') -PassThru
    $factttlDaemon.Id | Set-Content -LiteralPath $factttlPidFile
    for ($factttlAttempt = 0; $factttlAttempt -lt 40; $factttlAttempt++) {
        if (Test-FactTTLOllama) { break }
        if ($factttlDaemon.HasExited) { throw 'Ollama non si è avviato: controlla il log locale senza pubblicarlo.' }
        Start-Sleep -Milliseconds 250
    }
    if (-not (Test-FactTTLOllama)) { throw 'Runtime locale non pronto sulla porta 11434.' }
}

$factttlExisting = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
if (-not (@($factttlExisting.models | Where-Object name -EQ $Model).Count)) {
    if ($StartOnly) { throw 'Modello locale mancante: esegui prima il setup completo.' }
    Write-Host 'Scarico il modello locale qwen3:4b (circa 2.5 GB, Apache 2.0).'
    $factttlPullLog = Join-Path $factttlRuntime 'model-pull.out.log'
    $factttlPullErr = Join-Path $factttlRuntime 'model-pull.err.log'
    $factttlPull = Start-Process -FilePath $factttlExe -ArgumentList @('pull', $Model) -Environment @{ OLLAMA_HOST='127.0.0.1:11434'; OLLAMA_NO_CLOUD='1'; USERPROFILE=$factttlProfile } -WorkingDirectory $factttlRuntime -WindowStyle Hidden -RedirectStandardOutput $factttlPullLog -RedirectStandardError $factttlPullErr -PassThru
    $factttlDownloadDeadline = [DateTime]::UtcNow.AddMinutes(30)
    $factttlLastProgress = [DateTime]::UtcNow
    while (-not $factttlPull.HasExited) {
        if ([DateTime]::UtcNow -gt $factttlDownloadDeadline) {
            Stop-Process -Id $factttlPull.Id
            throw 'Download del modello oltre 30 min: dati parziali conservati per riprendere.'
        }
        if (([DateTime]::UtcNow - $factttlLastProgress).TotalSeconds -ge 20) {
            Write-Host 'Download del modello in corso; il CLI verifica i digest dei file.'
            $factttlLastProgress = [DateTime]::UtcNow
        }
        Start-Sleep -Seconds 1
        $factttlPull.Refresh()
    }
    if ($factttlPull.ExitCode -ne 0) { throw 'Download modello non riuscito: controlla model-pull.err.log.' }
}

$factttlMetadata = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/show' -Method Post -ContentType 'application/json' -Body (@{model=$Model} | ConvertTo-Json) -TimeoutSec 10
if ($factttlMetadata.remote_host -or $factttlMetadata.remote_model -or $factttlMetadata.details.format -ne 'gguf') {
    throw 'Il modello non è confermato come GGUF locale: setup non confermato.'
}
@{ runtime_version=$factttlVersion; runtime_archive_sha256=$factttlArchiveHash; model=$Model; model_storage=$factttlModels; executable=$factttlExe; endpoint='http://127.0.0.1:11434'; cloud_disabled=$true } | ConvertTo-Json | Set-Content -LiteralPath $factttlStateFile -Encoding utf8
Write-Host 'Motore locale pronto: qwen3:4b. Configura FactTTL con --news-model qwen3:4b.'
