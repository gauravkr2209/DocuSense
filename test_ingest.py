"""Basic tests for DocuSense ingestion (no Ollama needed)."""
import unittest

from langchain_core.documents import Document

from ingest import IngestionError, clean_text, load_pdf, split_documents


class TestIngestion(unittest.TestCase):
    def test_clean_text(self):
        result = clean_text("  Hello   world \n\n\n Next line  ")
        self.assertEqual(result, "Hello world\n\nNext line")

    def test_split_preserves_metadata(self):
        document = Document(
            page_content="Project documentation. " * 150,
            metadata={"page": 3, "source": "sample.pdf"},
        )
        chunks = split_documents([document])
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertEqual(chunk.metadata["page"], 3)
            self.assertEqual(chunk.metadata["source"], "sample.pdf")

    def test_missing_pdf(self):
        with self.assertRaises(IngestionError):
            load_pdf("this_file_does_not_exist.pdf")


if __name__ == "__main__":
    unittest.main()