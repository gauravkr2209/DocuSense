"""Tests for the DocuSense registry and summary cache (no Ollama)."""
import tempfile
import unittest
from pathlib import Path

import store


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.registry = self.dir / "registry.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_safe_filename(self):
        self.assertEqual(store.safe_filename("My Report (final).pdf"), "My_Report_final.pdf")
        self.assertEqual(store.safe_filename("../../evil.pdf"), "evil.pdf")
        self.assertEqual(store.safe_filename("???.pdf"), "document.pdf")

    def test_hash_is_stable_and_different(self):
        self.assertEqual(store.file_sha256(b"a"), store.file_sha256(b"a"))
        self.assertNotEqual(store.file_sha256(b"a"), store.file_sha256(b"b"))

    def test_registry_add_find_get(self):
        result = {"collection_name": "doc_x_1", "document_id": "1",
                  "pages": 3, "chunks": 9}
        record = store.make_record(" Asha ", " Demo ", "x.pdf", "h1", result)
        store.add_record(record, self.registry)
        self.assertEqual(record["student_name"], "Asha")
        self.assertEqual(store.find_by_hash("h1", self.registry)["collection_name"], "doc_x_1")
        self.assertIsNotNone(store.get_record("doc_x_1", self.registry))
        self.assertIsNone(store.find_by_hash("nope", self.registry))

    def test_missing_registry_is_empty(self):
        self.assertEqual(store.load_registry(self.registry), [])

    def test_corrupt_registry_is_set_aside(self):
        self.registry.write_text("{not json", encoding="utf-8")
        self.assertEqual(store.load_registry(self.registry), [])
        self.assertTrue(self.registry.with_suffix(".bad").exists())

    def test_summary_round_trip(self):
        self.assertIsNone(store.load_summary("c1", self.dir))
        store.save_summary("c1", "# Hello", self.dir)
        self.assertEqual(store.load_summary("c1", self.dir), "# Hello")

    def test_label(self):
        self.assertEqual(store.label({"student_name": "Asha", "project_title": "Demo"}), "Asha - Demo")
        self.assertEqual(
            store.label({"collection_name": "doc_a"}), "Unknown student - doc_a"
        )


if __name__ == "__main__":
    unittest.main()