param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$Version = "0.3.1",
    [string]$ArchLabel = "x64"
)

$ErrorActionPreference = "Stop"

$AssetName = "archagent-windows-$ArchLabel.zip"
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("archagent-fixture-" + [System.Guid]::NewGuid().ToString("N"))
$PayloadDir = Join-Path $TempRoot "payload"
$SourcePath = Join-Path $TempRoot "Program.cs"
$BinaryPath = Join-Path $PayloadDir "archagent.exe"
$ChecksumPath = Join-Path $OutputDir "SHA256SUMS"
$ArchivePath = Join-Path $OutputDir $AssetName

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
New-Item -ItemType Directory -Path $PayloadDir -Force | Out-Null

$Source = @"
using System;

public static class Program
{
    public static void Main(string[] args)
    {
        if (args.Length > 0 && (args[0] == "--version" || args[0] == "version"))
        {
            Console.WriteLine("$Version");
            return;
        }

        if (args.Length > 1 && args[0] == "completion")
        {
            switch (args[1])
            {
                case "bash":
                    Console.WriteLine("complete -W \"--version completion\" archagent");
                    return;
                case "zsh":
                    Console.WriteLine("#compdef archagent");
                    return;
                case "fish":
                    Console.WriteLine("complete -c archagent -l version");
                    return;
            }
        }

        Console.WriteLine("archagent fixture");
    }
}
"@

function Find-CSharpCompiler {
    $command = Get-Command csc.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

try {
    Set-Content -Path $SourcePath -Value $Source
    $CscPath = Find-CSharpCompiler
    if ($CscPath) {
        & $CscPath /nologo /target:exe /out:$BinaryPath $SourcePath | Out-Null
    } elseif (Get-Command dotnet -ErrorAction SilentlyContinue) {
        $ProjectPath = Join-Path $TempRoot "ArchAgentFixture.csproj"
        $Project = @"
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>disable</ImplicitUsings>
    <Nullable>disable</Nullable>
    <UseAppHost>true</UseAppHost>
  </PropertyGroup>
</Project>
"@
        Set-Content -Path $ProjectPath -Value $Project
        & dotnet publish $ProjectPath -c Release -r win-x64 --self-contained false -o $PayloadDir | Out-Null
    } else {
        throw "Neither csc.exe nor dotnet is available to generate Windows fixture binaries"
    }
    Compress-Archive -Path $BinaryPath -DestinationPath $ArchivePath -Force
    $Checksum = (Get-FileHash $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -Path $ChecksumPath -Value "$Checksum  $AssetName"
} finally {
    Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
