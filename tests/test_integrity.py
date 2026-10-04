import io
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from trustcv.dataset import scan_images
from trustcv.hashing import hash_matches, sha256_bytes, sha256_file
from trustcv.storage import add_audit, configured_db_path, verify_chain


class HashingTests(unittest.TestCase):
    def test_sha256_known_value(self):
        self.assertEqual(sha256_bytes(b"abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_scan_marks_exact_and_pixel_duplicates(self):
        image = Image.new("RGB", (8, 8), (30, 90, 160))
        png = io.BytesIO()
        image.save(png, format="PNG")
        bmp = io.BytesIO()
        image.save(bmp, format="BMP")
        frame = scan_images([("one.png", png.getvalue()), ("copy.png", png.getvalue()), ("same-pixels.bmp", bmp.getvalue())])
        self.assertEqual(int(frame["valid"].sum()), 3)
        self.assertTrue(frame.iloc[0]["exact_duplicate"])
        self.assertTrue(frame.iloc[1]["exact_duplicate"])
        self.assertTrue(frame.iloc[2]["content_duplicate"])


class ModelFileVerificationTests(unittest.TestCase):
    def test_matching_file_matches_reference_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.bin"
            model.write_bytes(b"model artifact bytes")
            expected = sha256_file(model)
            self.assertTrue(hash_matches(sha256_file(model), expected))

    def test_changed_file_does_not_match_saved_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.bin"
            model.write_bytes(b"model artifact bytes")
            saved_reference = sha256_file(model)
            model.write_bytes(b"model artifact bytes with a change")
            self.assertFalse(hash_matches(sha256_file(model), saved_reference))


class AuditChainTests(unittest.TestCase):
    def _create_two_record_chain(self, path: Path) -> None:
        add_audit("a" * 64, "b" * 64, "cat", 0.9, "test", path)
        add_audit("c" * 64, "b" * 64, "dog", None, "demo", path)

    def _update_record(self, path: Path, statement: str, parameters: tuple) -> None:
        db = sqlite3.connect(path)
        try:
            db.execute(statement, parameters)
            db.commit()
        finally:
            db.close()

    def test_unmodified_chain_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.sqlite3"
            self._create_two_record_chain(path)
            self.assertEqual(verify_chain(path), (True, "Verified 2 record(s)"))

    def test_modified_audit_record_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.sqlite3"
            self._create_two_record_chain(path)
            self._update_record(path, "UPDATE inference_audits SET prediction=? WHERE id=?", ("changed", 1))
            valid, explanation = verify_chain(path)
            self.assertFalse(valid)
            self.assertEqual(explanation, "Record 1 content or hash was changed")

    def test_broken_previous_hash_link_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.sqlite3"
            self._create_two_record_chain(path)
            self._update_record(path, "UPDATE inference_audits SET previous_hash=? WHERE id=?", ("f" * 64, 2))
            valid, explanation = verify_chain(path)
            self.assertFalse(valid)
            self.assertEqual(explanation, "Record 2 points to a different previous hash")


class DatabasePathTests(unittest.TestCase):
    def test_default_database_path_is_relative_for_cloud_and_source_runs(self):
        with patch.dict(os.environ):
            os.environ.pop("TRUSTCV_DB_PATH", None)
            self.assertEqual(configured_db_path(), Path("trustcv_audit.sqlite3"))
            self.assertFalse(configured_db_path().is_absolute())

    def test_host_can_select_a_writable_persistent_mount_path(self):
        with tempfile.TemporaryDirectory() as directory:
            expected = Path(directory) / "persistent" / "audit.sqlite3"
            with patch.dict(os.environ, {"TRUSTCV_DB_PATH": str(expected)}):
                self.assertEqual(configured_db_path(), expected)


if __name__ == "__main__":
    unittest.main()
