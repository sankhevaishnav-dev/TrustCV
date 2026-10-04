import http.server
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import desktop_launcher
from desktop_launcher import find_available_port, wait_for_server, _stop_process, _WindowsJob


class _HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/_stcore/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_error(404)

    def log_message(self, *_args):
        pass


class DesktopLauncherTests(unittest.TestCase):
    def test_port_is_available_on_loopback(self):
        port = find_available_port()
        with socket.socket() as server_socket:
            server_socket.bind(("127.0.0.1", port))

    def test_waits_for_streamlit_health_endpoint(self):
        server = http.server.HTTPServer(("127.0.0.1", 0), _HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            try:
                self.assertTrue(wait_for_server(process, server.server_port, timeout=2))
            finally:
                _stop_process(process)
                self.assertIsNotNone(process.poll())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_exited_server_is_reported_as_not_ready(self):
        process = subprocess.Popen([sys.executable, "-c", "pass"])
        process.wait(timeout=5)
        self.assertFalse(wait_for_server(process, find_available_port(), timeout=0.2))

    def test_packaged_data_uses_user_local_app_data_and_seeds_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            config_source = bundle / ".streamlit" / "config.toml"
            config_source.parent.mkdir(parents=True)
            config_source.write_text("[theme]\nbase='dark'\n", encoding="utf-8")
            local_app_data = root / "LocalAppData"
            with patch.object(desktop_launcher, "FROZEN", True), \
                 patch.object(desktop_launcher, "APP_DIR", bundle), \
                 patch.dict("os.environ", {"LOCALAPPDATA": str(local_app_data)}):
                data_path = desktop_launcher.prepare_data_directory()
                self.assertEqual(data_path, local_app_data / "TrustCV")
                self.assertEqual((data_path / ".streamlit" / "config.toml").read_text(encoding="utf-8"),
                                 "[theme]\nbase='dark'\n")
                (data_path / "trustcv_audit.sqlite3").write_bytes(b"local audit data")
                self.assertTrue((data_path / "trustcv_audit.sqlite3").is_file())

    def test_source_desktop_data_uses_user_profile_and_migrates_legacy_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            (source / ".streamlit").mkdir(parents=True)
            (source / ".streamlit" / "config.toml").write_text("[theme]\nbase='dark'\n", encoding="utf-8")
            (source / "trustcv_audit.sqlite3").write_bytes(b"existing source audit data")
            local_app_data = root / "LocalAppData"
            with patch.object(desktop_launcher, "FROZEN", False), \
                 patch.object(desktop_launcher, "APP_DIR", source), \
                 patch.dict("os.environ", {"LOCALAPPDATA": str(local_app_data)}):
                data_path = desktop_launcher.prepare_data_directory()
                self.assertEqual(data_path, local_app_data / "TrustCV")
                self.assertEqual((data_path / "trustcv_audit.sqlite3").read_bytes(),
                                 b"existing source audit data")
                self.assertEqual((data_path / ".streamlit" / "config.toml").read_text(encoding="utf-8"),
                                 "[theme]\nbase='dark'\n")

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Objects are Windows-only")
    def test_windows_job_close_stops_its_child_process(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        job = _WindowsJob(process)
        try:
            job.close()
            process.wait(timeout=5)
            self.assertIsNotNone(process.returncode)
        finally:
            _stop_process(process)


if __name__ == "__main__":
    unittest.main()
