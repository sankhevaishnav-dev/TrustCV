"""Safe, in-memory image scanning for uploaded files and ZIP archives."""

from __future__ import annotations

import hashlib
import io
import warnings
import zipfile
from collections import Counter
from typing import Iterable

import pandas as pd
from PIL import Image, UnidentifiedImageError

try:
    import cv2
    import numpy as np
except ImportError:  # Pillow remains sufficient for the required validity check.
    cv2 = None
    np = None

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_FILES = 1000
MAX_TOTAL_UNCOMPRESSED = 250 * 1024 * 1024
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
Image.MAX_IMAGE_PIXELS = 20_000_000


def _inspect(name: str, data: bytes, declared_size: int | None = None) -> dict:
    row = {"filename": name, "size_bytes": declared_size if declared_size is not None else len(data),
           "sha256": hashlib.sha256(data).hexdigest(),
           "valid": False, "format": "", "width": None, "height": None,
           "opencv_decodable": False, "exact_duplicate": False, "content_duplicate": False, "error": ""}
    if row["size_bytes"] > MAX_FILE_BYTES:
        row["error"] = f"File exceeds {MAX_FILE_BYTES // (1024 * 1024)} MiB limit"
        return row
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                row.update(valid=True, format=image.format or "unknown", width=image.width, height=image.height)
                # Hash decoded pixels with dimensions and mode to group identical image content
                # even when the encoded file bytes differ. This is a heuristic, not a semantic check.
                pixels = image.convert("RGBA")
                content = f"{pixels.width}x{pixels.height}:RGBA:".encode() + pixels.tobytes()
                row["content_hash"] = hashlib.sha256(content).hexdigest()
        if cv2 is not None and np is not None:
            try:
                decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                row["opencv_decodable"] = decoded is not None
            except cv2.error:
                row["opencv_decodable"] = False
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        row["error"] = f"Unreadable image: {type(exc).__name__}"
    except Exception as exc:
        row["error"] = f"Image could not be inspected: {type(exc).__name__}"
    return row


def scan_images(files: Iterable[tuple[str, bytes]]) -> pd.DataFrame:
    """Scan uploaded image bytes and ZIP members without extracting to disk."""
    candidates: list[tuple[str, bytes, int | None]] = []
    warnings: list[str] = []
    total = 0
    for name, data in files:
        lower = name.lower()
        if lower.endswith(".zip"):
            if len(data) > MAX_ARCHIVE_BYTES:
                warnings.append(f"{name}: archive exceeds 100 MiB and was skipped")
                continue
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    members = [m for m in archive.infolist() if not m.is_dir() and "." in m.filename.rsplit("/", 1)[-1]
                               and m.filename.lower().rsplit(".", 1)[-1] in {s[1:] for s in IMAGE_SUFFIXES}]
                    if len(members) > MAX_ARCHIVE_FILES:
                        warnings.append(f"{name}: more than 1,000 image entries; archive skipped")
                        continue
                    for member in members:
                        total += member.file_size
                        if total > MAX_TOTAL_UNCOMPRESSED:
                            warnings.append("ZIP scan stopped at 250 MiB total uncompressed image data")
                            break
                        if member.file_size > MAX_FILE_BYTES:
                            candidates.append((member.filename, b"", member.file_size))
                            continue
                        candidates.append((member.filename, archive.read(member), None))
            except (zipfile.BadZipFile, OSError, RuntimeError):
                warnings.append(f"{name}: invalid or unreadable ZIP archive")
        else:
            suffix = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
            if suffix in IMAGE_SUFFIXES:
                candidates.append((name, data, None))

    rows = [_inspect(name, data, size) for name, data, size in candidates]
    exact_counts = Counter(r["sha256"] for r in rows if r["valid"])
    content_counts = Counter(r.get("content_hash") for r in rows if r["valid"])
    for row in rows:
        if row["valid"]:
            row["exact_duplicate"] = exact_counts[row["sha256"]] > 1
            row["content_duplicate"] = content_counts[row["content_hash"]] > 1
    frame = pd.DataFrame(rows)
    frame.attrs["warnings"] = warnings
    frame.attrs["limitations"] = "Duplicate-content checks compare decoded pixels. They do not detect mislabeled, poisoned, or adversarial samples."
    return frame
