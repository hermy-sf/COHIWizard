# build_installer.ps1  -  builds installer\Output\COHIWizard_Setup_<version>.exe
#
#   powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1
#   powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1 -Version 2.3 -Branch cohiwizard_v2.3
#
# Downloads the official Python nuget package (python.org build, no installer,
# nothing registered in Windows) once into installer\build\ and runs ISCC.
param(
    [string]$Version = "2.3",
    [string]$Branch = "cohiwizard_v2.3"
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$PyVersion = "3.10.11"
$PySha256 = "7C6F99B160A36A7E09492DFCFF2B0A3A60BB5229CA44CDCC3ECB32871A6144D0"
$build = Join-Path $here "build"
$pkg = Join-Path $build "python.$PyVersion.nupkg"
$pydir = Join-Path $build "python"
New-Item -ItemType Directory -Force $build | Out-Null

if (-not (Test-Path (Join-Path $pydir "python.exe"))) {
    if (-not (Test-Path $pkg)) {
        Write-Host "downloading Python $PyVersion (nuget) ..."
        Invoke-WebRequest -UseBasicParsing "https://www.nuget.org/api/v2/package/python/$PyVersion" -OutFile $pkg
    }
    $sha = (Get-FileHash $pkg -Algorithm SHA256).Hash
    if ($sha -ne $PySha256) {
        Remove-Item $pkg
        throw "SHA256 mismatch of $pkg ($sha)"
    }
    $tmp = Join-Path $build "unpack"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Copy-Item $pkg "$tmp.zip"
    Expand-Archive "$tmp.zip" $tmp
    Remove-Item "$tmp.zip"
    if (Test-Path $pydir) { Remove-Item -Recurse -Force $pydir }
    Move-Item (Join-Path $tmp "tools") $pydir
    Remove-Item -Recurse -Force $tmp
}

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 (ISCC.exe) not found" }

& $iscc /Qp "/DAppVersion=$Version" "/DBranch=$Branch" (Join-Path $here "COHIWizard_Setup.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed ($LASTEXITCODE)" }
Write-Host "done: $(Join-Path $here "Output\COHIWizard_Setup_$Version.exe")"
