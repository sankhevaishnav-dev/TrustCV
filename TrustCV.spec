# PyInstaller one-folder configuration. Build with: pyinstaller TrustCV.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = Path(SPECPATH).resolve()
datas = [
    (str(ROOT / "app.py"), "."),
    (str(ROOT / ".streamlit" / "config.toml"), ".streamlit"),
]

binaries = []
hiddenimports = [
    "streamlit.web.cli",
    "trustcv.dataset", "trustcv.hashing", "trustcv.inference", "trustcv.risk", "trustcv.storage",
    "webview.platforms.edgechromium", "clr", "clr_loader", "pythonnet",
]
for package in (
    "streamlit", "webview", "pandas", "PIL", "cv2", "numpy", "altair",
    "pydeck", "pyarrow", "watchdog", "tornado", "jsonschema", "clr_loader", "pythonnet",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

# Some libraries discover their own version at runtime through importlib.metadata.
for distribution in ("streamlit", "pywebview", "pandas", "Pillow", "opencv-python-headless",
                     "numpy", "altair", "pydeck", "pyarrow", "watchdog", "tornado", "jsonschema",
                     "pythonnet", "clr_loader"):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        # collect_all or its package's PyInstaller hook may already carry metadata.
        pass

a = Analysis(
    [str(ROOT / "desktop_launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "torchvision", "PySide2", "PySide6", "PyQt5", "PyQt6", "cefpython3"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="TrustCV", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=False, name="TrustCV",
)
