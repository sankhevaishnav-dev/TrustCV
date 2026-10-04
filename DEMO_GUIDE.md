# TrustCV 5-minute live demo

This runbook is designed to run locally and repeatably without network access or pretrained weights. It uses only generated sample images and a synthetic file fixture. The inference step uses TrustCV's **Demo mode**, which logs a labelled demo result; it does not classify the image and has no confidence score.

## One-time setup

From the project folder, generate the sample files. This command is safe to rerun; it recreates the documented sample fixtures:

```powershell
.\.venv\Scripts\python.exe scripts\create_demo_assets.py
```

Start TrustCV with a separate local database for the live demo, so it does not mix with the normal `trustcv_audit.sqlite3` history:

```powershell
$env:TRUSTCV_DB_PATH = "trustcv_demo_audit.sqlite3"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If TrustCV is already running, press **Ctrl+C** in that PowerShell window first, then run the two lines above. Keep the PowerShell window open during the demo.

## Timed walkthrough

### 0:00–0:30 · Set the scope

Open **Overview**. Explain that TrustCV checks file integrity and links local audit records; the dashboard reports findings, not proof that a model or dataset is safe. Point out the local-demo label.

### 0:30–1:10 · Scan a normal dataset

Open **Dataset Scanner**, upload both files from `samples\normal_dataset`, and click **Scan dataset**.

Expected: **2 files checked**, **2 decodable**, **0 unreadable**, and **0** in both duplicate metrics. The decode bar should show full success. Download the scan CSV if you want to retain this clean-scan evidence; the JSON report later includes only the most recent scan in the current Streamlit session.

### 1:10–1:55 · Show duplicate detection

Replace the uploads with all three files from `samples\duplicate_dataset` and scan again.

Expected: **3 files checked**, **3 decodable**, **2 exact duplicate entries**, and **3 identical-pixel entries**. Two PNGs are byte-for-byte copies; the BMP uses the same decoded pixels with a different encoding. This is a pixel-equality heuristic, not near-duplicate or poison detection.

### 1:55–2:40 · Verify the trusted reference

Open **Model Verification** and upload `samples\synthetic_demo_model_fixture.bin`. Click **Save uploaded hash as trusted reference**. Re-upload the same file if needed; the dashboard should report a match. For an optional mismatch, upload `samples\synthetic_demo_model_fixture_changed.bin`; it should report a mismatch. Do not describe either fixture as a real model.

The reference is stored in the demo SQLite database. It demonstrates hash comparison only; it is not a securely sourced production reference.

### 2:40–3:40 · Record a labelled demo inference

Open **Inference Audit**, upload `samples\normal_dataset\blue_mug.png`, keep **Demo mode** selected, then click **Run and record inference**.

Expected: output text **“Demo result — no model prediction”**, no confidence score, and a new SQLite audit record. Say explicitly: “This is a simulated audit-path demonstration, not a genuine image-classification prediction.” Pretrained ResNet-18 is a separate option and may need internet to download weights; it is not needed for this walkthrough.

### 3:40–4:20 · Verify the audit chain

Open **Audit History**. The chain should show **PASS** and a verified record count. The count may exceed one if this demo database was used in an earlier run. Explain that the chain detects ordinary content edits and broken links when checked from its beginning.

### 4:20–5:00 · Export the evidence

Open **Evidence Reports** and download **JSON evidence report**. It contains the latest dataset scan (the duplicate set), the trusted reference hash, the stored audit rows, chain status, UTC generation time, and limitations. The clean dataset CSV from the earlier step is a separate download. Point out that the report describes the demo inference as demo mode and does not claim it was a model prediction.

## Sample asset provenance and purpose

All files under `samples/` are generated locally by `scripts/create_demo_assets.py` using Pillow drawing primitives. They contain no downloaded imagery, real people, external datasets, model weights, or private data.

- `normal_dataset/blue_mug.png` and `normal_dataset/potted_plant.png`: two distinct valid synthetic images for a clean scan and the audit-flow input.
- `duplicate_dataset/leaf_original.png`: synthetic source illustration.
- `duplicate_dataset/leaf_exact_copy.png`: byte-for-byte copy to exercise exact SHA-256 duplicate detection.
- `duplicate_dataset/leaf_same_pixels.bmp`: same RGB pixels encoded as BMP to exercise decoded-pixel duplicate detection.
- `synthetic_demo_model_fixture.bin`: fixed explanatory text bytes used only to demonstrate hash save/match. It is not a model or checkpoint and must not be loaded for inference.
- `synthetic_demo_model_fixture_changed.bin`: same fixture with extra bytes to demonstrate a reference mismatch.

The generation script prints each file's SHA-256 so the fixtures can be checked after regeneration. The JSON evidence report contains the most recent scan in session memory, not a history of all scans. SQLite chain hashes are not signatures; someone able to rewrite the database and recompute the chain can produce a different chain that verifies.
