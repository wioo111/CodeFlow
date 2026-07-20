$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$templateNames = @('research_football', 'research_inventory')

foreach ($templateName in $templateNames) {
    $templateRoot = Join-Path $repositoryRoot "project_templates\$templateName"
    $cleanRoot = Join-Path $templateRoot 'clean'
    $outputPath = Join-Path $templateRoot "$templateName-demo.zip"
    if (Test-Path -LiteralPath $outputPath) {
        Remove-Item -LiteralPath $outputPath -Force
    }
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $cleanRoot,
        $outputPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $true
    )
    Write-Output $outputPath
}
