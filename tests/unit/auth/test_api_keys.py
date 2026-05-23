from __future__ import annotations

import re

from koel.auth.api_keys import (
    KEY_PREFIX_LENGTH,
    generate_api_key,
    hash_api_key,
    parse_prefix,
)


class TestGenerate:
    def test_raw_shape(self):
        m = generate_api_key()
        assert m.raw.startswith("koel_")
        # token_urlsafe may contain "_", so split into at most 3 parts.
        parts = m.raw.split("_", 2)
        assert len(parts) == 3
        assert parts[0] == "koel"
        assert len(parts[1]) == KEY_PREFIX_LENGTH
        assert len(parts[2]) >= 24

    def test_prefix_matches_raw(self):
        m = generate_api_key()
        assert m.raw.split("_", 2)[1] == m.prefix

    def test_hash_is_sha256_hex(self):
        m = generate_api_key()
        assert re.fullmatch(r"[a-f0-9]{64}", m.hashed)
        assert m.hashed == hash_api_key(m.raw)

    def test_keys_are_unique(self):
        raws = {generate_api_key().raw for _ in range(100)}
        assert len(raws) == 100


class TestParsePrefix:
    def test_well_formed(self):
        m = generate_api_key()
        assert parse_prefix(m.raw) == m.prefix

    def test_rejects_wrong_brand(self):
        assert parse_prefix("foo_12345678_secret") is None

    def test_rejects_bad_prefix_length(self):
        assert parse_prefix("koel_xx_secret") is None

    def test_rejects_missing_secret(self):
        assert parse_prefix("koel_12345678") is None
