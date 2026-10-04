param([string]$Python = ".\.build-venv\Scripts\python.exe")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Build Python not found at '$Python'. Follow the README build setup to create .build-venv and install requirements plus PyInstaller."
}
$pythonPath = (Resolve-Path -LiteralPath $Python).Path
$pyinstallerVersion = & $pythonPath -c "import PyInstaller; print(PyInstaller.__version__)" 2>$null
if ($LASTEXITCODE -ne 0) { throw "PyInstaller is missing. Install requirements-build.txt first." }
if ($pyinstallerVersion.Trim() -ne "6.22.3") {
    throw "Expected PyInstaller 6.22.3, found $pyinstallerVersion. Install requirements-build.txt for a reproducible build."
}
$distRoot = Join-Path $projectRoot "dist"
$packageRoot = Join-Path $distRoot "TrustCV"

Write-Host "Running project tests before packaging..."
& $pythonPath -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed; packaging stopped." }

Write-Host "Building the one-folder Windows package from TrustCV.spec..."
& $pythonPath -m PyInstaller --noconfirm --clean --distpath $distRoot `
    --workpath (Join-Path $projectRoot "build") TrustCV.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed. Review the build output above." }

$exePath = Join-Path $packageRoot "TrustCV.exe"
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "PyInstaller returned success but $exePath was not created."
}
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $packageRoot -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "DEMO_GUIDE.md") -Destination $packageRoot -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "samples") -Destination $packageRoot -Recurse -Force
Write-Host "Distribution ready: $packageRoot"
Write-Host "Run .\test_distribution.ps1 to check the bundled Streamlit worker."
