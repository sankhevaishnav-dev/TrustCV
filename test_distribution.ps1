param([int]$StartupTimeoutSeconds = 60)
$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "dist\TrustCV\TrustCV.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Packaged EXE not found: $exe. Run .\package_windows.ps1 first."
}
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = $listener.LocalEndpoint.Port
$listener.Stop()

# This internal mode runs the included Streamlit application server without
# initializing pywebview. It tests frozen imports and bundled app resources.
$server = Start-Process -FilePath $exe -ArgumentList @("--trustcv-server-worker", $port) `
    -WorkingDirectory (Split-Path -Parent $exe) -PassThru -WindowStyle Hidden
try {
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline -and -not $server.HasExited) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$port/_stcore/health" -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 350 }
        $server.Refresh()
    }
    if (-not $ready) { throw "Bundled Streamlit worker did not become ready. Check %TEMP%\trustcv-streamlit.log if started via the desktop launcher." }
    Write-Host "PASS: packaged Streamlit worker answered the health check on port $port."
} finally {
    $server.Refresh()
    if (-not $server.HasExited) {
        & taskkill.exe /PID $server.Id /T /F *> $null
        try { $server.WaitForExit(5000) | Out-Null } catch { }
    }
}
$check = [System.Net.Sockets.TcpClient]::new()
try {
    $check.Connect("127.0.0.1", $port)
    throw "FAIL: worker port $port remained open after shutdown."
} catch [System.Net.Sockets.SocketException] {
    Write-Host "PASS: packaged worker stopped and released its port."
} finally { $check.Dispose() }
