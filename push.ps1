# Auto-bump version and push to GitHub
# Usage: .\push.ps1 "commit message"

param(
    [Parameter(Mandatory=$true)]
    [string]$Message
)

$ManifestPath = "custom_components\librus_apix\manifest.json"

# Read manifest
$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

# Parse version and increment patch
$version = $manifest.version
$parts = $version -split '\.'
$parts[2] = [string]([int]$parts[2] + 1)
$newVersion = $parts -join '.'

# Update manifest.json
$manifest.version = $newVersion
$manifest | ConvertTo-Json -Depth 10 | Set-Content $ManifestPath -Encoding UTF8

Write-Host "Version bumped: $version -> $newVersion" -ForegroundColor Green

# Stage, commit and push
git add $ManifestPath
git add -A
git commit -m "${Message} (v$newVersion)"
git push origin main
