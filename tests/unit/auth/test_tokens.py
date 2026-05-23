from __future__ import annotations

import re

from koel.auth.tokens import generate_token, hash_token


class TestGenerateToken:
    def test_returns_raw_and_hash(self):
        t = generate_token()
        assert t.raw
        assert t.hashed
        assert re.fullmatch(r"[a-f0-9]{64}", t.hashed), "expected a sha256 hex digest"

    def test_tokens_are_unique(self):
        tokens = {generate_token().raw for _ in range(100)}
        assert len(tokens) == 100

    def test_hash_matches_hash_token(self):
        t = generate_token()
        assert t.hashed == hash_token(t.raw)


class TestHashToken:
    def test_deterministic(self):
        assert hash_token("abc") == hash_token("abc")

    def test_different_input_different_hash(self):
        assert hash_token("abc") != hash_token("abd")
