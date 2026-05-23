from decimal import Decimal

import pytest
from koel.scraping.exceptions import ParseError
from koel.scraping.parsing import (
    extract_first_number,
    json_path,
    parse_decimal,
    select_attr,
    select_text,
)


class TestParseDecimal:
    def test_plain_float(self):
        assert parse_decimal("0.9123") == Decimal("0.9123")

    def test_us_thousands(self):
        assert parse_decimal("1,234.5678") == Decimal("1234.5678")

    def test_european_format(self):
        assert parse_decimal("1.234,56") == Decimal("1234.56")

    def test_numeric_input(self):
        assert parse_decimal(0.9123) == Decimal("0.9123")
        assert parse_decimal(5) == Decimal("5")

    def test_decimal_passthrough(self):
        d = Decimal("0.9123456789")
        assert parse_decimal(d) is d

    def test_zero_rejected(self):
        with pytest.raises(ParseError):
            parse_decimal("0")

    def test_negative_rejected(self):
        with pytest.raises(ParseError):
            parse_decimal("-0.5")

    def test_garbage_rejected(self):
        with pytest.raises(ParseError):
            parse_decimal("not a number")


class TestJsonPath:
    def test_nested_dict(self):
        data = {"data": {"mid": 0.9123, "bid": 0.9110}}
        assert json_path(data, "data.mid") == 0.9123

    def test_list_index(self):
        data = {"rates": [{"value": 1.1}, {"value": 2.2}]}
        assert json_path(data, "rates.0.value") == 1.1
        assert json_path(data, "rates.1.value") == 2.2

    def test_missing_key(self):
        with pytest.raises(ParseError):
            json_path({"a": 1}, "b")

    def test_missing_index(self):
        with pytest.raises(ParseError):
            json_path({"rates": []}, "rates.0")

    def test_non_traversable(self):
        with pytest.raises(ParseError):
            json_path({"a": 1}, "a.b")


class TestExtractFirstNumber:
    def test_rate_in_sentence(self):
        assert extract_first_number("The rate is 1.2345 USD") == Decimal("1.2345")

    def test_no_number(self):
        with pytest.raises(ParseError):
            extract_first_number("nothing here")


class TestSelectors:
    HTML = '<div class="rate" data-value="1.2345">1.2345</div>'

    def test_select_text(self):
        assert select_text(self.HTML, "div.rate") == "1.2345"

    def test_select_text_missing(self):
        with pytest.raises(ParseError):
            select_text(self.HTML, "span.missing")

    def test_select_attr(self):
        assert select_attr(self.HTML, "div.rate", "data-value") == "1.2345"

    def test_select_attr_missing(self):
        with pytest.raises(ParseError):
            select_attr(self.HTML, "div.rate", "missing")
