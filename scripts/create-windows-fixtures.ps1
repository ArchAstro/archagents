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

try {
    Add-Type -TypeDefinition $Source -OutputAssembly $BinaryPath -OutputType ConsoleApplication | Out-Null
    Compress-Archive -Path $BinaryPath -DestinationPath $ArchivePath -Force
    $Checksum = (Get-FileHash $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -Path $ChecksumPath -Value "$Checksum  $AssetName"
} finally {
    Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
