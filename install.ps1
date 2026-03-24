param(
    [string]$Version = $env:ARCHAGENT_VERSION,
    [string]$InstallDir = $env:ARCHAGENT_INSTALL_DIR,
    [string]$BaseUrl = $env:ARCHAGENT_RELEASE_BASE_URL,
    [switch]$DryRun,
    [switch]$PrintAssetUrl,
    [switch]$SkipPathUpdate,
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

function Resolve-BoolEnv {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    switch ($Value.ToLowerInvariant()) {
        "1" { return $true }
        "true" { return $true }
        "yes" { return $true }
        "on" { return $true }
        default { return $false }
    }
}

$Owner = "ArchAstro"
$Repo = "archagents"
$BinaryName = "archagent.exe"

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = "latest"
}

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = Join-Path $env:LOCALAPPDATA "ArchAgent\bin"
}

if (-not $SkipPathUpdate.IsPresent) {
    $SkipPathUpdate = [System.Management.Automation.SwitchParameter](Resolve-BoolEnv $env:ARCHAGENT_INSTALL_SKIP_PATH_UPDATE)
}

if (-not $SkipVerify.IsPresent) {
    $SkipVerify = [System.Management.Automation.SwitchParameter](Resolve-BoolEnv $env:ARCHAGENT_INSTALL_SKIP_VERIFY)
}

switch ($env:PROCESSOR_ARCHITECTURE.ToLowerInvariant()) {
    "amd64" { $ArchLabel = "x64" }
    "arm64" { $ArchLabel = "arm64" }
    default { throw "Unsupported architecture: $env:PROCESSOR_ARCHITECTURE" }
}

$ResolvedVersion = $Version
if ($ResolvedVersion -ne "latest" -and -not $ResolvedVersion.StartsWith("v")) {
    $ResolvedVersion = "v$ResolvedVersion"
}

$AssetName = "archagent-windows-$ArchLabel.zip"
if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    if ($Version -eq "latest") {
        $ResolvedBaseUrl = "https://github.com/$Owner/$Repo/releases/latest/download"
    } else {
        $ResolvedBaseUrl = "https://github.com/$Owner/$Repo/releases/download/$ResolvedVersion"
    }
} else {
    $ResolvedBaseUrl = $BaseUrl.TrimEnd('/')
}

$AssetUrl = "$ResolvedBaseUrl/$AssetName"
$ChecksumUrl = "$ResolvedBaseUrl/SHA256SUMS"
$TargetPath = Join-Path $InstallDir $BinaryName

if ($PrintAssetUrl) {
    Write-Output $AssetUrl
    exit 0
}

if ($DryRun) {
    @(
        "version=$Version"
        "arch=$ArchLabel"
        "asset=$AssetName"
        "release_base_url=$ResolvedBaseUrl"
        "asset_url=$AssetUrl"
        "checksum_url=$ChecksumUrl"
        "install_dir=$InstallDir"
        "target_path=$TargetPath"
        "skip_path_update=$($SkipPathUpdate.IsPresent)"
        "skip_verify=$($SkipVerify.IsPresent)"
    ) | Write-Output
    exit 0
}

$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("archagent-install-" + [System.Guid]::NewGuid().ToString("N"))
$ArchivePath = Join-Path $TempRoot $AssetName
$ChecksumPath = Join-Path $TempRoot "SHA256SUMS"
$ExtractDir = Join-Path $TempRoot "extract"

New-Item -ItemType Directory -Path $TempRoot | Out-Null
New-Item -ItemType Directory -Path $ExtractDir | Out-Null
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

try {
    Write-Host "Downloading $AssetName"
    Invoke-WebRequest $AssetUrl -OutFile $ArchivePath

    try {
        Invoke-WebRequest $ChecksumUrl -OutFile $ChecksumPath
        $ExpectedLine = Select-String -Path $ChecksumPath -Pattern ([Regex]::Escape($AssetName) + '$') | Select-Object -First 1
        if ($ExpectedLine) {
            $ExpectedHash = ($ExpectedLine.Line -split '\s+')[0]
            $ActualHash = (Get-FileHash $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($ActualHash -ne $ExpectedHash.ToLowerInvariant()) {
                throw "Checksum mismatch for $AssetName"
            }
        } else {
            Write-Host "SHA256SUMS did not include $AssetName; continuing without checksum verification"
        }
    } catch {
        Write-Host "SHA256SUMS not available for this release; continuing without checksum verification"
    }

    Expand-Archive -Path $ArchivePath -DestinationPath $ExtractDir -Force
    $Binary = Get-ChildItem -Path $ExtractDir -Recurse -File | Where-Object { $_.Name -eq $BinaryName } | Select-Object -First 1
    if (-not $Binary) {
        $Binary = Get-ChildItem -Path $ExtractDir -Recurse -File | Select-Object -First 1
    }
    if (-not $Binary) {
        throw "No binary found in $AssetName"
    }

    Copy-Item $Binary.FullName $TargetPath -Force

    if (-not $SkipPathUpdate.IsPresent) {
        $CurrentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $PathEntries = @()
        if ($CurrentUserPath) {
            $PathEntries = $CurrentUserPath -split ';' | Where-Object { $_ }
        }
        if ($PathEntries -notcontains $InstallDir) {
            $NewPath = if ($CurrentUserPath) { "$CurrentUserPath;$InstallDir" } else { $InstallDir }
            [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
            Write-Host "Added $InstallDir to the user Path"
            $env:Path = "$env:Path;$InstallDir"
        }
    }

    if (-not $SkipVerify.IsPresent) {
        Write-Host "Verifying installation"
        & $TargetPath --version
    }

    Write-Host "Installed archagent to $TargetPath"
} finally {
    Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
