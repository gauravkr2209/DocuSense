"""Tests for the DocuSense UI helpers (no Ollama, no browser)."""
import unittest

import ui

SAMPLE = """# Demo (Asha)

## Context
A system.

## Objectives
Not stated in the document.

## Methodology
Methods.

## Results
Good.

## Limitations
Some.

## Suggested Viva Questions
1. Why?

_Note: long document. Only 8 of 10 parts were read (evenly spaced)._"""


class TestUI(unittest.TestCase):
        
    def test_info_note_content_and_theme(self):
        out = ui.info_note()
        self.assertIn("ds-info", out)
        self.assertIn("10 minutes", out)
        self.assertIn("working on making this faster", out)
        self.assertIn(".ds-info", ui.build_css(False))
        self.assertIn(".ds-info", ui.build_css(True))

    def test_split_summary_finds_all_sections(self):
        title, sections, note = ui.split_summary(SAMPLE)
        self.assertEqual(title, "Demo (Asha)")
        self.assertEqual(len(sections), 6)
        self.assertEqual(sections["Context"], "A system.")
        self.assertEqual(sections["Suggested Viva Questions"], "1. Why?")
        self.assertTrue(note.startswith("Note: long document"))

    def test_split_summary_unknown_format(self):
        _, sections, _ = ui.split_summary("Just some text.")
        self.assertEqual(sections, {})

    def test_note_not_inside_last_section(self):
        _, sections, _ = ui.split_summary(SAMPLE)
        self.assertNotIn("Note", sections["Suggested Viva Questions"])

    def test_is_empty_section(self):
        self.assertTrue(ui.is_empty_section("Not stated in the document."))
        self.assertTrue(ui.is_empty_section("None stated in the document."))
        self.assertTrue(ui.is_empty_section("  "))
        self.assertFalse(ui.is_empty_section("Uses Adam."))

    def test_esc_escapes_html_and_dollar(self):
        self.assertEqual(ui.esc("<b>$5</b>"), "&lt;b&gt;&#36;5&lt;/b&gt;")

    def test_page_chips(self):
        text = ui.page_chips([5, 8], "Sources")
        self.assertIn("p. 5", text)
        self.assertIn("p. 8", text)
        self.assertIn("Sources", text)

    def test_truncate(self):
        self.assertEqual(ui.truncate("short", 10), "short")
        cut = ui.truncate("a" * 50, 10)
        self.assertEqual(len(cut), 10)
        self.assertTrue(cut.endswith("…"))

    def test_body_html_lists_and_paragraphs(self):
        out = ui.body_html("Intro line.\n1. First\n2. Second\n- bullet")
        self.assertIn("<p>Intro line.</p>", out)
        self.assertIn("<ol><li>First</li><li>Second</li></ol>", out)
        self.assertIn("<ul><li>bullet</li></ul>", out)

    def test_body_html_escapes_model_text(self):
        out = ui.body_html("<script>x</script>")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertEqual(
            ui.body_html("A **big** step"), "<p>A <strong>big</strong> step</p>"
        )

    def test_card_html_empty_section(self):
        out = ui.card_html("Limitations", "Not stated in the document.")
        self.assertIn("ds-empty", out)
        self.assertIn("ds-c-limitations wide", out)

    def test_summary_html_order_and_wide(self):
        sections = {
            "Suggested Viva Questions": "ccc",
            "Context": "aaa",
            "Results": "bbb",
        }
        out = ui.summary_html(sections)
        self.assertTrue(out.startswith('<div class="ds-grid">'))
        self.assertTrue(out.endswith("</div>"))
        self.assertLess(out.index("aaa"), out.index("bbb"))
        self.assertLess(out.index("bbb"), out.index("ccc"))
        self.assertIn("ds-c-viva wide", out)

    def test_topbar_status(self):
        good = ui.topbar("DocuSense", "Tagline", True)
        bad = ui.topbar("DocuSense", "Tagline", False)
        self.assertIn("Ollama running", good)
        self.assertIn("ds-ok", good)
        self.assertIn("Ollama not running", bad)
        self.assertIn("ds-bad", bad)

    def test_thinking_stages(self):
        self.assertIn("Searching", ui.thinking("search"))
        self.assertIn("🔍", ui.thinking("search"))
        self.assertIn("Writing", ui.thinking("write"))
        self.assertIn("Working", ui.thinking("unknown-stage"))

    def test_build_css_light_and_dark_differ(self):
        light, dark = ui.build_css(False), ui.build_css(True)
        self.assertNotEqual(light, dark)
        self.assertIn("#FFFFFF", light)
        self.assertIn("#171B26", dark)
        self.assertTrue(light.startswith("<style>"))
        self.assertTrue(dark.endswith("</style>"))

    def test_meta_chips_escape(self):
        out = ui.meta_chips([("Student", "<b>x</b>")])
        self.assertNotIn("<b>x", out)
        self.assertIn("&lt;b&gt;", out)


if __name__ == "__main__":
    unittest.main()