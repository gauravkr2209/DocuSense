"""Tests for the DocuSense evaluation helpers (no Ollama needed)."""
import json
import tempfile
import unittest
from pathlib import Path

from evaluate import (
    EvalError,
    contains_any,
    evidence_pages,
    grade,
    load_questions,
    pct,
    split_valid,
    summarize,
)


def result(answer="x", found=True, cited=False, pages=None):
    return {"answer": answer, "found": found, "cited": cited,
            "pages": pages or []}


ANSWERABLE = {"question": "q", "type": "answerable",
              "evidence": ["28.4"], "answer_contains": ["28.4"]}
UNANSWERABLE = {"question": "u", "type": "unanswerable",
                "evidence": [], "answer_contains": []}


class TestEvaluate(unittest.TestCase):
    def test_contains_any_ignores_case_and_spacing(self):
        self.assertTrue(contains_any("The  BLEU score\nwas 28.4.", ["28.4"]))
        self.assertTrue(contains_any("Trained on P100 GPUs", ["p100"]))
        self.assertFalse(contains_any("nothing here", ["28.4"]))

    def test_evidence_pages(self):
        chunks = [("a 28.4 b", 8), ("c", 2), ("again 28.4", 9)]
        self.assertEqual(evidence_pages(chunks, ["28.4"]), {8, 9})

    def test_split_valid_skips_missing_evidence(self):
        chunks = [("only text", 1)]
        valid, skipped = split_valid([ANSWERABLE, UNANSWERABLE], chunks)
        self.assertEqual(skipped, [ANSWERABLE])
        self.assertEqual(valid, [UNANSWERABLE])

    def test_grade_correct_answer(self):
        row = grade(ANSWERABLE, result("It scored 28.4 BLEU", pages=[8]), {8})
        self.assertTrue(row["ok"])
        self.assertTrue(row["source_ok"])

    def test_grade_wrong_pages(self):
        row = grade(ANSWERABLE, result("28.4", pages=[2]), {8})
        self.assertTrue(row["ok"])
        self.assertFalse(row["source_ok"])

    def test_grade_false_refusal(self):
        row = grade(ANSWERABLE, result("nope", found=False), {8})
        self.assertFalse(row["ok"])
        self.assertIsNone(row["source_ok"])

    def test_grade_unanswerable(self):
        self.assertTrue(grade(UNANSWERABLE, result(found=False), set())["ok"])
        self.assertFalse(grade(UNANSWERABLE, result(found=True), set())["ok"])

    def test_pct(self):
        self.assertEqual(pct(1, 4), "1/4 (25%)")
        self.assertEqual(pct(0, 0), "n/a")

    def test_summarize(self):
        rows = [
            {**grade(ANSWERABLE, result("28.4", cited=True, pages=[8]), {8}), "seconds": 10},
            {**grade(UNANSWERABLE, result(found=False), set()), "seconds": 20},
        ]
        metrics = summarize(rows)
        self.assertEqual(metrics["Answer correct (answerable)"], "1/1 (100%)")
        self.assertEqual(metrics["Correct refusals (unanswerable)"], "1/1 (100%)")
        self.assertEqual(metrics["Average seconds per question"], "15")

    def _write(self, data):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "q.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_load_questions_defaults_answer_terms(self):
        path = self._write([{"question": "q?", "type": "answerable",
                             "evidence": ["abc"]}])
        self.assertEqual(load_questions(path)[0]["answer_contains"], ["abc"])

    def test_load_questions_rejects_bad_input(self):
        with self.assertRaises(EvalError):
            load_questions(self._write([{"question": "q?", "type": "maybe"}]))
        with self.assertRaises(EvalError):
            load_questions(self._write([{"question": "q?", "type": "answerable"}]))
        with self.assertRaises(EvalError):
            load_questions(self._write([]))


if __name__ == "__main__":
    unittest.main()