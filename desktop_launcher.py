"""Launch the existing Streamlit TrustCV dashboard in a native window."""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
APP_FILE = APP_DIR / "app.py"
FROZEN = bool(getattr(sys, "frozen", False))
STARTUP_TIMEOUT_SECONDS = 60


def data_directory() -> Path:
    """Keep desktop app data in the current user's writable profile folder."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "TrustCV"


def prepare_data_directory() -> Path:
    """Create writable app storage and seed its config once in packaged mode."""
    folder = data_directory()
    folder.mkdir(parents=True, exist_ok=True)
    source = APP_DIR / ".streamlit" / "config.toml"
    destination = folder / ".streamlit" / "config.toml"
    if source.is_file() and not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    # Preserve records from older source-mode desktop launches on first migration.
    legacy_database = APP_DIR / "trustcv_audit.sqlite3"
    user_database = folder / "trustcv_audit.sqlite3"
    if not FROZEN and legacy_database.is_file() and not user_database.exists():
        shutil.copy2(legacy_database, user_database)
    return folder


def _show_message(title: str, message: str, error: bool = False) -> None:
    """Use a message box so a pythonw-launched app can report failures."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10 if error else 0x40)
    except Exception:
        print(f"{title}: {message}", file=sys.stderr)


def _acquire_single_instance_mutex():
    """Return a Windows named mutex handle and whether another app owns it."""
    if os.name != "nt":
        return None, False
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.CreateMutexW(None, False, "Local\\TrustCV.DesktopLauncher.Singleton")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return (kernel32, handle), ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS


def find_available_port(host: str = "127.0.0.1") -> int:
    """Get an ephemeral port from Windows; bind the server to loopback only."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def wait_for_server(process: subprocess.Popen, port: int, timeout: float = STARTUP_TIMEOUT_SECONDS) -> bool:
    """Return when Streamlit's health endpoint answers or the child exits."""
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/_stcore/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.25)
    return False


class _WindowsJob:
    """Kill server descendants automatically when the desktop launcher exits."""
    def __init__(self, process: subprocess.Popen):
        import ctypes
        from ctypes import wintypes

        class BasicLimit(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                        ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class ExtendedLimit(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int,
                                                        wintypes.LPVOID, wintypes.DWORD)
        self.kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if getattr(self, "handle", None):
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _start_process(command: list[str], env: dict[str, str], log_handle):
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process_cwd = prepare_data_directory()
    process = subprocess.Popen(command, cwd=str(process_cwd), env=env, stdin=subprocess.DEVNULL,
                               stdout=log_handle, stderr=subprocess.STDOUT, creationflags=flags)
    job = None
    if os.name == "nt":
        try:
            job = _WindowsJob(process)
        except Exception:
            pass  # The parent process is still explicitly terminated during cleanup.
    return process, job


def _stop_process(process, job=None):
    if process is not None and process.poll() is None:
        if os.name == "nt" and job is None:
            # Fallback for locked-down Windows configurations where assigning
            # the process to a Job Object is not permitted. Kill the tree first
            # so the parent cannot exit before taskkill identifies descendants.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        else:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   check=False, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
    if job is not None:
        job.close()


def _read_log_tail(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(max(0, path.stat().st_size - 5000))
            return handle.read().strip()[-5000:] or "No server output was recorded."
    except OSError:
        return "No server output was available."


def run_desktop() -> int:
    if not APP_FILE.is_file():
        _show_message("TrustCV could not start", f"Dashboard file not found:\n{APP_FILE}", True)
        return 1
    try:
        import webview
    except Exception as exc:
        _show_message("TrustCV desktop dependency missing",
                      f"Could not load pywebview ({exc}). Install requirements-desktop.txt, then try again.", True)
        return 1
    try:
        mutex, already_running = _acquire_single_instance_mutex()
    except Exception as exc:
        _show_message("TrustCV could not start", f"Could not create app lock:\n{exc}", True)
        return 1
    if already_running:
        if mutex:
            mutex[0].CloseHandle(mutex[1])
        _show_message("TrustCV is already open", "A TrustCV desktop window is already running.")
        return 0

    process = job = log_handle = None
    log_path = Path(tempfile.gettempdir()) / "trustcv-streamlit.log"
    try:
        port = find_available_port()
        user_data = prepare_data_directory()
        env = os.environ.copy()
        env.update({"STREAMLIT_SERVER_HEADLESS": "true", "STREAMLIT_SERVER_ADDRESS": "127.0.0.1",
                    "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
                    "STREAMLIT_SERVER_MAXUPLOADSIZE": "100",
                    "TRUSTCV_SERVER_LOG": str(log_path)})
        env.setdefault("TRUSTCV_DB_PATH", str(user_data / "trustcv_audit.sqlite3"))
        if FROZEN:
            command = [sys.executable, "--trustcv-server-worker", str(port)]
        else:
            server_python = Path(sys.executable)
            if server_python.name.lower() == "pythonw.exe":
                console_python = server_python.with_name("python.exe")
                if console_python.is_file():
                    server_python = console_python
            command = [str(server_python), "-m", "streamlit", "run", str(APP_FILE),
                       "--server.address=127.0.0.1", f"--server.port={port}",
                       "--server.headless=true", "--server.maxUploadSize=100",
                       "--browser.gatherUsageStats=false"]
        log_handle = log_path.open("w", encoding="utf-8")
        process, job = _start_process(command, env, log_handle)
        if not wait_for_server(process, port):
            raise RuntimeError(f"Dashboard did not become ready in {STARTUP_TIMEOUT_SECONDS} seconds.\n\n"
                               f"Server log:\n{_read_log_tail(log_path)}\n\nFull log: {log_path}")
        webview.create_window("TrustCV — Computer Vision Integrity Assurance",
                              f"http://127.0.0.1:{port}", width=1440, height=920,
                              min_size=(960, 640), text_select=True)
        webview.start(gui="edgechromium")
        return 0
    except Exception as exc:
        extra = ""
        if os.name == "nt" and ("webview" in str(exc).lower() or "edge" in str(exc).lower()):
            extra = ("\n\nTrustCV uses Microsoft Edge WebView2. Install the Evergreen WebView2 Runtime "
                     "from https://developer.microsoft.com/microsoft-edge/webview2/, then try again.")
        _show_message("TrustCV startup error", f"{exc}{extra}", True)
        return 1
    finally:
        _stop_process(process, job)
        if log_handle is not None:
            log_handle.close()
        if mutex:
            mutex[0].CloseHandle(mutex[1])


def run_frozen_streamlit_worker() -> int:
    """Entry point used by the bundled executable to start Streamlit itself."""
    try:
        worker_log_path = os.environ.get("TRUSTCV_SERVER_LOG")
        if worker_log_path:
            worker_log = open(worker_log_path, "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = worker_log
        import streamlit.web.cli as stcli
        if len(sys.argv) != 3 or not sys.argv[2].isdigit():
            raise ValueError("Invalid internal server worker arguments")
        sys.argv = ["streamlit", "run", str(APP_FILE), "--server.address=127.0.0.1",
                    f"--server.port={sys.argv[2]}", "--server.headless=true",
                    "--server.maxUploadSize=100",
                    "--browser.gatherUsageStats=false"]
        stcli.main()
        return 0
    except Exception as exc:
        try:
            print(f"TrustCV Streamlit worker failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        except Exception:
            _show_message("TrustCV server error", str(exc), True)
        return 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--trustcv-server-worker":
        raise SystemExit(run_frozen_streamlit_worker())
    raise SystemExit(run_desktop())
