from __future__ import annotations

from fleet.redact import (
    RedactingRenderer,
    is_secret_name,
    mask,
    redact_config,
)


class TestNaming:
    def test_the_markers_catch_the_usual_suspects(self):
        for name in ("db_password", "API_TOKEN", "sshKey", "client-secret"):
            assert is_secret_name(name)

    def test_ordinary_names_pass(self):
        for name in ("timeout", "mode", "replicas"):
            assert not is_secret_name(name)


class TestMasking:
    def test_short_values_vanish_entirely(self):
        assert mask("abc") == "****"

    def test_long_values_keep_two_characters(self):
        assert mask("hunter2secret") == "hu***********"

    def test_the_mask_preserves_length(self):
        assert len(mask("a" * 20)) == 20


class TestRedaction:
    def test_only_secret_keys_are_masked(self):
        shown = redact_config({"timeout": "5", "api_token": "abcdef123"})
        assert shown["timeout"] == "5"
        assert shown["api_token"] == "ab*******"

    def test_the_renderer_counts_its_masks(self):
        renderer = RedactingRenderer()
        renderer.render("app", {"password": "swordfish", "mode": "fast"})
        assert renderer.masked == 1

    def test_no_secret_survives_into_a_page(self):
        renderer = RedactingRenderer()
        secrets = ["swordfish", "abcdef123"]
        renderer.render("app", {"password": "swordfish", "mode": "fast"})
        renderer.render("api", {"api_token": "abcdef123", "url": "http://x"})
        assert renderer.leaked(secrets) == []

    def test_the_audit_would_catch_a_leak(self):
        renderer = RedactingRenderer()
        renderer.lines.append("oops: swordfish")
        assert renderer.leaked(["swordfish"]) == ["swordfish"]
