"""Tests for the DocuSense summary helpers (no Ollama needed)."""
import unittest

from langchain_core.documents import Document

from summarize import (
    NOT_STATED,
    SECTIONS,
    fix_spacing,
    group_chunks,
    page_range,
    parse_sections,
    pick_groups,
    render_summary,
)


def make_chunks(count, size=100):
    return [
        Document(page_content="x" * size, metadata={"page": i + 1})
        for i in range(count)
    ]


class TestSummaryHelpers(unittest.TestCase):
    def test_group_chunks_respects_limit(self):
        groups = group_chunks(make_chunks(10, 100), 350)
        self.assertEqual(sum(len(g) for g in groups), 10)
        for group in groups:
            self.assertLessEqual(sum(len(c.page_content) for c in group), 350)

    def test_pick_groups_keeps_first_and_last(self):
        groups = [[c] for c in make_chunks(20)]
        picked = pick_groups(groups, 5)
        self.assertEqual(len(picked), 5)
        self.assertEqual(picked[0], groups[0])
        self.assertEqual(picked[-1], groups[-1])

    def test_pick_groups_small_input_unchanged(self):
        groups = [[c] for c in make_chunks(3)]
        self.assertEqual(pick_groups(groups, 8), groups)

    def test_page_range(self):
        chunks = make_chunks(4)
        self.assertEqual(page_range(chunks[1:4]), "pages 2-4")
        self.assertEqual(page_range(chunks[:1]), "page 1")

    def test_parse_sections_complete(self):
        text = (
            "## Context\nA system.\n\n## Objectives\nGoals.\n\n"
            "## Methodology\nMethods.\n\n## Results\nGood.\n\n"
            "## Limitations\nSome.\n\n## Suggested Viva Questions\n1. Why?"
        )
        sections = parse_sections(text)
        self.assertEqual(sections["Context"], "A system.")
        self.assertEqual(sections["Suggested Viva Questions"], "1. Why?")

    def test_parse_sections_fills_missing(self):
        sections = parse_sections("## Context\nOnly this.")
        self.assertEqual(sections["Context"], "Only this.")
        self.assertEqual(sections["Results"], NOT_STATED)
        self.assertEqual(list(sections), SECTIONS)

    def test_parse_sections_accepts_bold_headings(self):
        sections = parse_sections("**Objectives:**\nGoals here.")
        self.assertEqual(sections["Objectives"], "Goals here.")

    def test_render_summary_has_all_headings(self):
        text = render_summary(parse_sections(""), "Demo")
        self.assertTrue(text.startswith("# Demo"))
        for name in SECTIONS:
            self.assertIn(f"## {name}", text)

    def test_fix_spacing_adds_missing_space(self):
        self.assertEqual(
            fix_spacing("It replaces convolutions.It was tested."),
            "It replaces convolutions. It was tested.",
        )

    def test_fix_spacing_leaves_normal_text_alone(self):
        text = "Uses Ph.D data, e.g.The U.S. set and v3.2 of the model."
        self.assertEqual(fix_spacing(text), text)

    def test_parse_sections_applies_spacing_fix(self):
        sections = parse_sections("## Context\nFirst idea.Second idea.")
        self.assertEqual(sections["Context"], "First idea. Second idea.")


if __name__ == "__main__":
    unittest.main()