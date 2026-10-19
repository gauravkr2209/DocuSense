"""Tests for the DocuSense Q&A helpers (no Ollama needed)."""
import unittest

from langchain_core.documents import Document

from qa import (
    NOT_FOUND,
    extract_cited_pages,
    find_unverified_numbers,
    format_context,
    format_history,
    is_not_found,
    strip_citations,
    strip_page_labels,
    top_pages,
    trim_history,
)


class TestQAHelpers(unittest.TestCase):
    def test_format_context_has_page_labels(self):
        chunks = [
            Document(page_content="Alpha", metadata={"page": 2}),
            Document(page_content="Beta", metadata={"page": 5}),
        ]
        text = format_context(chunks)
        self.assertIn("[Page 2]", text)
        self.assertIn("[Page 5]", text)
        self.assertIn("Beta", text)

    def test_is_not_found(self):
        self.assertTrue(is_not_found(NOT_FOUND))
        self.assertTrue(is_not_found("i could not find that in the document"))
        self.assertFalse(is_not_found("The model uses 8 heads (page 5)."))

    def test_trim_history(self):
        history = [(f"q{i}", f"a{i}") for i in range(10)]
        trimmed = trim_history(history, 3)
        self.assertEqual(len(trimmed), 3)
        self.assertEqual(trimmed[-1], ("q9", "a9"))

    def test_empty_history_text(self):
        self.assertEqual(format_history([]), "(none)")

    def test_page_helpers(self):
        self.assertEqual(extract_cited_pages("Uses 8 heads (page 3)."), [3])
        self.assertEqual(strip_page_labels("[Page 3] \nHello"), "Hello")

    def test_multiple_cited_pages(self):
        self.assertEqual(extract_cited_pages("Text (pages 4, 7)."), [4, 7])
        self.assertEqual(extract_cited_pages("No citation here."), [])

    def test_top_pages_keeps_relevance_order(self):
        chunks = [
            Document(page_content="a", metadata={"page": 9}),
            Document(page_content="b", metadata={"page": 9}),
            Document(page_content="c", metadata={"page": 2}),
            Document(page_content="d", metadata={"page": 5}),
        ]
        self.assertEqual(top_pages(chunks, 2), [9, 2])

    def test_strip_citations_removes_page_refs(self):
        self.assertEqual(strip_citations("Uses 8 heads (page 3)."), "Uses 8 heads.")
        self.assertEqual(strip_citations("Text (pages 4, 7)."), "Text.")
        self.assertEqual(strip_citations("[Page 3] \nHello"), "Hello")
        self.assertEqual(strip_citations("A (Page 2 and 5) b"), "A b")

    def test_strip_citations_leaves_normal_text(self):
        text = "Plain answer with 28.4 BLEU."
        self.assertEqual(strip_citations(text), text)

    def test_strip_citations_removes_meta_comment(self):
        answer = (
            "Ask three questions.\n\n"
            "(No page numbers used, as the answer is not found on a "
            "specific page)"
        )
        self.assertEqual(strip_citations(answer), "Ask three questions.")

    def test_strip_citations_keeps_real_parentheses(self):
        text = "Pages with text were skipped (see page 3)."
        self.assertEqual(strip_citations(text), text)

    def test_unverified_number_is_flagged(self):
        self.assertEqual(
            find_unverified_numbers("BLEU score of 41.0.", "It reached 41.8 BLEU."),
            ["41.0"],
        )

    def test_verified_number_passes(self):
        self.assertEqual(
            find_unverified_numbers("BLEU of 28.4", "scored 28.4 on"), []
        )

    def test_small_numbers_and_model_names_ignored(self):
        self.assertEqual(
            find_unverified_numbers("8 NVIDIA P100 GPUs and 2 heads", "nothing"),
            [],
        )

    def test_thousands_separator_matches(self):
        self.assertEqual(
            find_unverified_numbers("4,500,000 pairs", "about 4,500,000 pairs"),
            [],
        )

    def test_numbers_from_question_are_ignored(self):
        self.assertEqual(
            find_unverified_numbers("It is 2099.", "nothing", "What about 2099?"),
            [],
        )

    def test_number_boundary_not_partial_match(self):
        self.assertEqual(
            find_unverified_numbers("28.4", "got 128.45 here"), ["28.4"]
        )

    def test_invented_page_does_not_count_as_number(self):
        answer = strip_citations("The authors used Adam. (page 20)")
        self.assertEqual(find_unverified_numbers(answer, "Adam optimizer"), [])


if __name__ == "__main__":
    unittest.main()