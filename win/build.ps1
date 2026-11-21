# Builds Holosii.exe next to server.py:  powershell -ExecutionPolicy Bypass -File win\build.ps1
# Needs the .NET 8 SDK (winget install Microsoft.DotNet.SDK.8). The exe needs the .NET 8 Desktop Runtime
# and the WebView2 Runtime (built into Windows 11; on Windows 10 install it from Microsoft).
# -SelfContained bundles the .NET runtime into the exe (bigger, but nothing else to install).
param([switch]$SelfContained)
$ErrorActionPreference = "Stop"
$win = $PSScriptRoot
$root = Split-Path $win -Parent
$out = Join-Path ([IO.Path]::GetTempPath()) ("holosii_build_" + [guid]::NewGuid().ToString("N"))

$sc = if ($SelfContained) { "true" } else { "false" }
dotnet publish (Join-Path $win "Holosii.csproj") -c Release -o $out --self-contained $sc
if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed" }

# the old build goes to the Holosii trash folder (nothing is deleted for good)
$exe = Join-Path $root "Holosii.exe"
if (Test-Path $exe) {
  $trash = Join-Path $env:LOCALAPPDATA "Holosii\Trash\Holosii_app_old"
  New-Item -ItemType Directory -Force $trash | Out-Null
  Move-Item $exe (Join-Path $trash ("Holosii_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".exe"))
}
Copy-Item (Join-Path $out "Holosii.exe") $exe
Remove-Item -Recurse -Force $out
Write-Host "Done: $exe"
