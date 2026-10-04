# TrustCV — Computer Vision Integrity Assurance

TrustCV is a lightweight integrity-assurance dashboard for the computer-vision pipeline:

**Dataset → Model → Inference → Risk → Evidence**

The same Streamlit app supports two independent run modes:

1. **Online browser app:** deploy `app.py` from GitHub to Streamlit Community Cloud.
2. **Windows desktop app:** start Streamlit behind a pywebview window, or package that launcher with PyInstaller.

The shared business logic is in `trustcv/`. The Cloud requirements intentionally do not install pywebview; desktop-only dependencies are in `requirements-desktop.txt`.

## Features and honest limitations

- Scan supported image uploads and ZIP archives in memory; check decoding, SHA-256, exact-byte duplicates, and decoded-pixel duplicates.
- Hash model artifacts as bytes and compare against a saved reference hash. Trust the reference only if it was obtained securely.
- Record demo inference locally, or optionally run ImageNet ResNet-18 when PyTorch, torchvision, and model weights are available.
- Store inference records and the trusted model hash in SQLite; link audit records with a SHA-256 hash chain and verify the chain.
- Export scan/audit CSV and JSON evidence reports.

These checks do not prove that a dataset or model is safe. They do not currently detect label errors, poisoned data, trigger patterns, OOD samples, model backdoors, or replayed predictions. The hash chain detects ordinary record/link changes, but is not a digital signature and cannot stop an attacker who can rewrite the database and recompute hashes.

### Cloud data and privacy behavior

Uploaded image and model bytes are processed in memory; TrustCV does not save those uploaded artifacts to disk. The app saves hashes, predictions, settings, and audit history to a SQLite file selected by `TRUSTCV_DB_PATH`, or to `trustcv_audit.sqlite3` in the current working directory if that variable is unset. Streamlit Community Cloud executes from the repository root, so the default database is created beside `app.py` at runtime, not committed by this project. **Community Cloud does not guarantee local-file persistence**; a restart, rebuild, or redeploy may erase this database. Export reports you need to keep.

One hosted app instance uses one database for all viewers. This MVP has no sign-in or per-user database separation, so viewers of the same app share its records and saved model reference. Do not upload sensitive/private images or artifacts to a public hosted app. If reliable shared persistence is needed, add a database adapter for a managed PostgreSQL service (for example, Supabase or Neon) and configure its credentials in the hosting provider's secret manager; that adapter is not included yet.

For Community Cloud file and dependency behavior, see the [official file organization guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization), [dependency guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies), and [local storage guidance](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data).

## Option A — GitHub and Streamlit Community Cloud

### Before publishing

- The entry point is **`app.py`** at the repository root.
- Cloud dependencies are listed in **`requirements.txt`**. `.streamlit/config.toml` is the non-secret Streamlit theme/upload configuration.
- App modules are imported from the root-level `trustcv/` package. Keep the repository root as the app working directory.
- `requirements.txt` deliberately excludes pywebview and PyInstaller. It also excludes optional PyTorch/torchvision to keep the cloud install lighter; demo inference works without them.
- `.gitignore` excludes environments, build artifacts, exports, local SQLite databases, local secrets, and scratch data. Synthetic sample fixtures are documented in `samples/README.md`.

### Create and push a private GitHub repository

First create a **Private** repository at [github.com/new](https://github.com/new). During development, private is the safer default. A public repository exposes its source and included sample files. A public Streamlit app exposes a usable app to its viewers; repository and app visibility are separate settings, so review the app's **Sharing** settings after deployment. Never commit API keys, passwords, certificates, `.streamlit/secrets.toml`, or private datasets.

Open PowerShell in the TrustCV project folder. If this folder is not already a Git repository, initialize it, review the staged file list, then commit and push:

```powershell
git init
git branch -M main
git add .
git status --short
git commit -m "Prepare TrustCV for deployment"
git remote add origin https://github.com/YOUR-GITHUB-NAME/TrustCV.git
git push -u origin main
```

Replace `YOUR-GITHUB-NAME` and `TrustCV` with the account and repository you created. If `git remote add origin` says `origin` already exists, inspect it with `git remote -v`; do not add a second remote. Before committing, confirm `git status --short` does **not** list `.venv`, `.build-venv`, `build`, `dist`, any `*.sqlite3`/`*.db`, exported CSVs, or secrets. If a secret or private database was committed earlier, removing it in a later commit is not enough; rotate the secret and remove sensitive history using GitHub's supported procedures.

### Deploy on Streamlit Community Cloud

1. Sign in at [share.streamlit.io](https://share.streamlit.io/) and authorize access to the GitHub repository.
2. Select **Create app** → **Yup, I have an app**.
3. Choose your GitHub repository, branch `main`, and entrypoint **`app.py`**.
4. Open **Advanced settings** and select Python **3.12** (the documented Community Cloud default when this README was written).
5. Select **Deploy** and wait for the build logs to report completion. If it fails, inspect the app logs before changing dependencies.
6. After it starts, check the app's **Sharing** settings. Keep it restricted to invited viewers if the app or its inputs should not be public. A private GitHub repo does not mean you should skip checking the app's own viewer permissions.
7. Copy the generated `*.streamlit.app` URL to your users.

Deployment is **not complete** until you connect this repository and the Cloud build actually succeeds. Deployment also does not make TrustCV a multi-user secure service: the current app has no authentication or per-user data isolation, and hosted SQLite can be lost.

### Features and internet requirements online

Image scanning, hashing, duplicate grouping, model-file hashing, demo inference, SQLite audit-chain functions, and report generation use local computation in the app runtime. They need no paid API. The hosted app itself requires internet access for users to open it. Optional genuine ResNet-18 inference is not installed by the default requirements; it needs compatible PyTorch and torchvision packages, and obtaining pretrained weights may need internet. If these are unavailable, select **Demo mode**; it is clearly labelled and does not claim to classify the image. The Windows desktop window is not used in Cloud; the compatible alternative is the browser dashboard.

## Option B — Run on Windows

### Source-code development mode

This mode uses Python and does not run the packaged EXE. In PowerShell from the project root, use an installed Python 3.12 interpreter (or a compatible version) to create the environment and install the desktop dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe .\desktop_launcher.py
```

For the normal browser-based Streamlit dashboard instead of the native window:

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\app.py
```

Then open the URL Streamlit prints (normally `http://localhost:8501`). Keep that terminal open until you finish; Ctrl+C stops the server. The desktop launcher starts the server on loopback, waits for its health endpoint, then shuts its child process down when the window closes. pywebview's Edge renderer needs the Microsoft Edge WebView2 Runtime. If Windows Smart App Control or Code Integrity blocks Python or a packaged EXE, use an approved interpreter/build or ask the administrator to approve it. **Do not disable or bypass Windows security policy.** Source mode remains available only if the Python interpreter is allowed to run.

Both native-window desktop modes (source and packaged) store the database and copied Streamlit settings in `%LOCALAPPDATA%\TrustCV\`. On the first source-mode launch, the launcher copies an existing project-root database there if no profile database exists, preserving earlier audit history. The ordinary browser development command uses `trustcv_audit.sqlite3` in the project working directory unless `TRUSTCV_DB_PATH` is set. To choose a different writable path for either source command in PowerShell:

```powershell
$env:TRUSTCV_DB_PATH = "$env:LOCALAPPDATA\TrustCV\trustcv_audit.sqlite3"
.\.venv\Scripts\python.exe .\desktop_launcher.py
```

Packaged desktop mode automatically stores its database and settings in `%LOCALAPPDATA%\TrustCV\`. Those records remain for that Windows user when the app folder moves, but do not transfer to another laptop unless you intentionally copy the database. A new laptop starts with its own database.

### Build the Windows distributable folder

Build on Windows x64 using Python 3.12 x64. This packages a Python runtime, Streamlit assets, TrustCV modules, and desktop dependencies into `dist\TrustCV\`. The target laptop does not need Python, but does need WebView2. The package may still be blocked by that laptop's Smart App Control or Code Integrity policy; use an approved signing/deployment process or administrator approval. This project does not claim that a generated EXE will be allowed by another computer's policy.

```powershell
py -3.12 -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install --upgrade pip
.\.build-venv\Scripts\python.exe -m pip install --no-build-isolation -r requirements-build.txt
.\package_windows.ps1
```

The packaging script runs unit tests before PyInstaller. After a successful build, test the bundled server worker with:

```powershell
.\test_distribution.ps1
```

That test must be allowed by local policy to launch `dist\TrustCV\TrustCV.exe`; a policy block is a blocked test, not a pass. For another laptop, copy the **entire** `dist\TrustCV\` folder, not only the EXE. Install WebView2 from the [official Microsoft download page](https://developer.microsoft.com/microsoft-edge/webview2/) if missing. Inspect the relevant Code Integrity/AppLocker logs if Windows blocks the app. A Windows package has not been proven to work on another laptop until it is tested there under its applicable security policies.

## Project layout

```text
app.py                    Streamlit Cloud and browser-mode entry point
trustcv/                  Shared dataset, hash, inference, risk, and SQLite logic
requirements.txt          Cloud/browser runtime dependencies
requirements-desktop.txt  Desktop-only dependency overlay (pywebview)
desktop_launcher.py       Native window and managed Streamlit worker
launch_trustcv.vbs         Optional no-console source launcher
TrustCV.spec               PyInstaller one-folder configuration
requirements-build.txt    Windows build dependencies
package_windows.ps1       Test and build the Windows distribution
test_distribution.ps1     Packaged worker startup/shutdown smoke test
installer/TrustCV.iss      Optional Inno Setup configuration
tests/                    Integrity and desktop-launcher tests
samples/                  Documented synthetic-only demo fixtures
```

Run core tests with the project's Python environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The packaged PyInstaller folder uses a generated Python runtime and bundled dependencies. It is separate from the Cloud requirements file and is still subject to Windows execution policy.
