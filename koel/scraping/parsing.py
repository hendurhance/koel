from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from selectolax.parser import HTMLParser

from koel.scraping.exceptions import ParseError

_RATE_RE = re.compile(r"-?\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?")


def parse_decimal(raw: str | float | int | Decimal) -> Decimal:
    """Accept common rate representations: '1,234.5678', '1.234,5678' (EU), '0.9123', 1.2.

    Rejects values <= 0. The ExchangeRateCurrent check constraint enforces this
    server-side too, but catching it here gives a clearer error.
    """
    if isinstance(raw, Decimal):
        value = raw
    elif isinstance(raw, (int, float)):
        value = Decimal(str(raw))
    else:
        cleaned = raw.strip()
        if _is_european_format(cleaned):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "").replace(" ", "")
        try:
            value = Decimal(cleaned)
        except InvalidOperation as exc:
            raise ParseError(f"cannot parse decimal: {raw!r}") from exc

    if value <= 0:
        raise ParseError(f"non-positive rate: {value}")
    return value


def _is_european_format(s: str) -> bool:
    """Heuristic: '1.234,56' is European; '1,234.56' is US/UK.

    Detect by position of last '.' vs last ',' — European has the comma
    after the dot.
    """
    last_dot = s.rfind(".")
    last_comma = s.rfind(",")
    return last_comma > last_dot and last_dot != -1


def extract_first_number(text: str) -> Decimal:
    """Pull the first rate-shaped number out of a text blob. Use only when
    the source page has no clean selector for the value."""
    match = _RATE_RE.search(text)
    if match is None:
        raise ParseError("no number found in text")
    return parse_decimal(match.group(0))


def select_text(html: str, css: str) -> str:
    tree = HTMLParser(html)
    node = tree.css_first(css)
    if node is None:
        raise ParseError(f"selector {css!r} not found")
    return node.text(strip=True)


def select_first_text(html: str, selectors: Sequence[str]) -> str:
    """Return the text of the first selector that matches a non-empty node.

    Reputable finance pages tweak their markup over time; trying an ordered
    list of selectors makes a scraper resilient to one of them moving.
    """
    tree = HTMLParser(html)
    for css in selectors:
        node = tree.css_first(css)
        if node is not None:
            text = node.text(strip=True)
            if text:
                return text
    raise ParseError(f"none of selectors matched: {list(selectors)}")


def select_attr(html: str, css: str, attr: str) -> str:
    tree = HTMLParser(html)
    node = tree.css_first(css)
    if node is None:
        raise ParseError(f"selector {css!r} not found")
    value = node.attributes.get(attr)
    if value is None:
        raise ParseError(f"attribute {attr!r} missing on {css!r}")
    return value


def json_path(data: Any, path: str) -> Any:
    """Dotted-path lookup into nested dicts/lists.

    Supports: 'data.mid', 'rates.0.value', 'quote.price'.
    """
    cursor: Any = data
    for segment in path.split("."):
        if isinstance(cursor, list):
            try:
                cursor = cursor[int(segment)]
            except (ValueError, IndexError) as exc:
                raise ParseError(f"json path {path!r} fails at {segment!r}") from exc
        elif isinstance(cursor, dict):
            if segment not in cursor:
                raise ParseError(f"json path {path!r} missing key {segment!r}")
            cursor = cursor[segment]
        else:
            raise ParseError(f"json path {path!r} hit non-traversable at {segment!r}")
    return cursor
