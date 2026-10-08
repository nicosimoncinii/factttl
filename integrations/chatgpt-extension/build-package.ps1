param(
    [ValidateSet('Firefox', 'Chromium')]
    [string]$Browser = 'Firefox',
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$sourceDirectory = [IO.Path]::GetFullPath($PSScriptRoot)
$projectDirectory = [IO.Path]::GetFullPath((Join-Path $sourceDirectory '../..'))
$manifest = Get-Content -LiteralPath (Join-Path $sourceDirectory 'manifest.json') -Raw | ConvertFrom-Json -AsHashtable
$runtimeFiles = @('amazon-url.js', 'background.js', 'item-ui.js', 'memory.js', 'correction.js', 'merchant.js', 'content.js', 'content.css', 'options.html', 'options.js', 'options.css')
foreach ($runtimeFile in $runtimeFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceDirectory $runtimeFile) -PathType Leaf)) {
        throw "Missing runtime file: $runtimeFile"
    }
}

if ($Browser -eq 'Firefox') {
    $manifest.Remove('key')
    $manifest.Remove('minimum_chrome_version')
    $manifest.background.Remove('service_worker')
    $suffix = 'xpi'
} else {
    $manifest.Remove('browser_specific_settings')
    $manifest.background.Remove('scripts')
    $suffix = 'zip'
}

if (-not $OutputPath) {
    $OutputPath = Join-Path $projectDirectory "dist/FactTTL-$Browser-$($manifest.version)-local.$suffix"
}
$packagePath = [IO.Path]::GetFullPath($OutputPath)
$allowedPrefix = $projectDirectory.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $packagePath.StartsWith($allowedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Package output must stay inside the project directory.'
}
if (Test-Path -LiteralPath $packagePath) {
    throw "Package already exists: $packagePath. Choose a new -OutputPath."
}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($packagePath)) | Out-Null
Add-Type -AssemblyName System.IO.Compression
$archive = [IO.Compression.ZipFile]::Open($packagePath, [IO.Compression.ZipArchiveMode]::Create)
try {
    $entry = $archive.CreateEntry('manifest.json')
    $writer = [IO.StreamWriter]::new($entry.Open(), [Text.UTF8Encoding]::new($false))
    try { $writer.Write(($manifest | ConvertTo-Json -Depth 20)) }
    finally { $writer.Dispose() }
    foreach ($runtimeFile in $runtimeFiles) {
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive, (Join-Path $sourceDirectory $runtimeFile), $runtimeFile
        ) | Out-Null
    }
    foreach ($document in @('README.md', 'DISTRIBUTION.md')) {
        $documentPath = Join-Path $sourceDirectory $document
        if (Test-Path -LiteralPath $documentPath -PathType Leaf) {
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $documentPath, $document) | Out-Null
        }
    }
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, (Join-Path $projectDirectory 'LICENSE'), 'LICENSE') | Out-Null
} finally { $archive.Dispose() }
Write-Output "Created unsigned local test package: $packagePath"
Write-Output 'No tokens, local configuration, demo scripts, or tests are included.'
