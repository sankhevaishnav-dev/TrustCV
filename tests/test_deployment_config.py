"""Guardrails for independent Cloud and Windows desktop configurations."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigurationTests(unittest.TestCase):
    def test_cloud_entrypoint_and_runtime_requirements_are_root_level(self):
        self.assertTrue((ROOT / "app.py").is_file())
        self.assertTrue((ROOT / "trustcv" / "__init__.py").is_file())
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        for dependency in ("streamlit", "pandas", "pillow", "opencv-python-headless"):
            self.assertIn(dependency, requirements)
        self.assertNotIn("pywebview", requirements)
        self.assertNotIn("pyinstaller", requirements)

    def test_desktop_dependencies_extend_cloud_dependencies(self):
        desktop = (ROOT / "requirements-desktop.txt").read_text(encoding="utf-8").lower()
        build = (ROOT / "requirements-build.txt").read_text(encoding="utf-8").lower()
        self.assertIn("-r requirements.txt", desktop)
        self.assertIn("pywebview", desktop)
        self.assertIn("-r requirements-desktop.txt", build)

    def test_gitignore_excludes_local_databases_secrets_and_build_outputs(self):
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for entry in ("*.sqlite3", "*.db", ".streamlit/secrets.toml", ".env", ".venv/", "build/", "dist/"):
            self.assertIn(entry, ignored)

    def test_streamlit_configuration_is_present_and_has_no_machine_paths(self):
        config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("maxUploadSize = 100", config)
        self.assertNotIn("C:\\Users\\", config)
        self.assertNotIn("D:\\Events\\", config)


if __name__ == "__main__":
    unittest.main()
