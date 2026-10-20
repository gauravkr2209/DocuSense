"""Tests for the provider layer (no network and no API key needed)."""
import os
from providers import ModelChain
import unittest
from unittest import mock

import config
import providers


class _Reply:
    def __init__(self, content):
        self.content = content


class TestProviders(unittest.TestCase):
    def test_provider_is_known(self):
        self.assertIn(config.PROVIDER, ("gemini", "ollama"))

    def test_active_model_names_match_provider(self):
        if config.PROVIDER == "gemini":
            self.assertEqual(config.CHAT_MODEL, config.GEMINI_CHAT_MODEL)
            self.assertEqual(config.EMBEDDING_MODEL, config.GEMINI_EMBEDDING_MODEL)
        else:
            self.assertEqual(config.CHAT_MODEL, config.OLLAMA_CHAT_MODEL)
            self.assertEqual(config.EMBEDDING_MODEL, config.OLLAMA_EMBEDDING_MODEL)

    def test_gemini_not_ready_without_key(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(config, "PROVIDER", "gemini"):
            self.assertFalse(providers.provider_ready())
            with self.assertRaises(providers.ProviderError):
                providers._require_key()

    def test_gemini_ready_with_key(self):
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}), \
                mock.patch.object(config, "PROVIDER", "gemini"):
            self.assertTrue(providers.provider_ready())
            self.assertEqual(providers._require_key(), "test-key")

    def test_ollama_always_ready(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(config, "PROVIDER", "ollama"):
            self.assertTrue(providers.provider_ready())

    def test_chain_falls_back_on_busy_model(self):
        class Busy:
            def invoke(self, messages):
                raise RuntimeError("503 UNAVAILABLE high demand")

        class Ok:
            def invoke(self, messages):
                return _Reply("answer")

        chain = ModelChain([("first", Busy), ("second", Ok)])
        reply = chain.invoke([])
        self.assertEqual(providers.text_of(reply), "answer")
        self.assertEqual(chain.last_model, "second")

    def test_chain_raises_when_all_fail(self):
        class Fails:
            def invoke(self, messages):
                raise RuntimeError("429 RESOURCE_EXHAUSTED")

        chain = ModelChain([("only", Fails)])
        with self.assertRaises(providers.ProviderError) as ctx:
            chain.invoke([])
        self.assertIn("usage limit", str(ctx.exception))

    def test_labels(self):
        with mock.patch.object(config, "PROVIDER", "gemini"):
            self.assertEqual(providers.provider_label(), "Gemini (cloud)")
        with mock.patch.object(config, "PROVIDER", "ollama"):
            self.assertEqual(providers.provider_label(), "Ollama (local)")

    def test_explain_error_quota(self):
        msg = providers.explain_error(Exception("429 RESOURCE_EXHAUSTED"), "Failed.")
        self.assertIn("usage limit", msg)

    def test_explain_error_local_hint(self):
        with mock.patch.object(config, "PROVIDER", "ollama"):
            msg = providers.explain_error(Exception("connection refused"), "Failed.")
        self.assertIn("Ollama running", msg)

    def test_text_of_handles_string_and_parts(self):
        self.assertEqual(providers.text_of(_Reply("hi")), "hi")
        parts = [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
        self.assertEqual(providers.text_of(_Reply(parts)), "ab")


if __name__ == "__main__":
    unittest.main()