"""Hash helpers shared by the scanner, model verifier, and audit log."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import BinaryIO
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_stream(stream: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
    """Hash a binary stream from its beginning without loading it all at once.

    If the stream is seekable, its original position is restored afterwards.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    try:
        original_position = stream.tell()
        stream.seek(0)
    except (AttributeError, OSError):
        original_position = None
    digest = hashlib.sha256()
    try:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    finally:
        if original_position is not None:
            stream.seek(original_position)
    return digest.hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate SHA-256 for a local file using bounded memory."""
    with Path(path).open("rb") as file:
        return sha256_stream(file, chunk_size=chunk_size)


def hash_matches(actual_hash: str, reference_hash: str | None) -> bool:
    """Compare two canonical 64-character SHA-256 hex digests."""
    if not reference_hash or not re.fullmatch(r"[0-9a-fA-F]{64}", reference_hash):
        return False
    if not re.fullmatch(r"[0-9a-fA-F]{64}", actual_hash):
        return False
    return hmac.compare_digest(actual_hash.lower(), reference_hash.lower())


def canonical_json(value: Any) -> bytes:
    """Stable JSON representation used when linking audit records."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def audit_record_hash(record: dict[str, Any], previous_hash: str) -> str:
    payload = {"record": record, "previous_hash": previous_hash}
    return sha256_bytes(canonical_json(payload))
