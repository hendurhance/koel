from decimal import Decimal

import pytest
from koel.domain.pivot import cross_rate, derive_all_cross_rates

USD_RATES = {
    "EUR": Decimal("0.8500"),
    "GBP": Decimal("0.7400"),
    "JPY": Decimal("158.60"),
}


class TestCrossRate:
    def test_self_pair_is_one(self):
        assert cross_rate("USD", "USD", USD_RATES) == Decimal(1)
        assert cross_rate("EUR", "EUR", USD_RATES) == Decimal(1)

    def test_usd_to_target_is_direct_lookup(self):
        assert cross_rate("USD", "EUR", USD_RATES) == Decimal("0.8500")

    def test_base_to_usd_is_inverse(self):
        rate = cross_rate("EUR", "USD", USD_RATES)
        assert rate == Decimal(1) / Decimal("0.8500")

    def test_cross_pair_uses_formula(self):
        # EUR → JPY = (USD → JPY) / (USD → EUR) = 158.60 / 0.85
        expected = Decimal("158.60") / Decimal("0.8500")
        assert cross_rate("EUR", "JPY", USD_RATES) == expected

    def test_round_trip_invariant(self):
        # cross(A, B) * cross(B, A) == 1 (within Decimal precision)
        forward = cross_rate("EUR", "GBP", USD_RATES)
        back = cross_rate("GBP", "EUR", USD_RATES)
        assert abs(forward * back - Decimal(1)) < Decimal("1e-20")

    def test_missing_base_raises(self):
        with pytest.raises(KeyError):
            cross_rate("ZZZ", "EUR", USD_RATES)

    def test_missing_target_raises(self):
        with pytest.raises(KeyError):
            cross_rate("EUR", "ZZZ", USD_RATES)

    def test_zero_rate_in_table_raises(self):
        bad = {**USD_RATES, "NIO": Decimal("0")}
        with pytest.raises(ValueError):
            cross_rate("NIO", "EUR", bad)

    def test_negative_rate_in_table_raises(self):
        bad = {**USD_RATES, "NIO": Decimal("-1")}
        with pytest.raises(ValueError):
            cross_rate("NIO", "EUR", bad)


class TestDeriveAllCrossRates:
    def test_covers_every_pair_except_self(self):
        codes = ["USD", "EUR", "GBP"]
        rates = derive_all_cross_rates(USD_RATES, codes=codes)
        assert set(rates.keys()) == {
            ("USD", "EUR"),
            ("USD", "GBP"),
            ("EUR", "USD"),
            ("EUR", "GBP"),
            ("GBP", "USD"),
            ("GBP", "EUR"),
        }

    def test_default_codes_include_usd(self):
        rates = derive_all_cross_rates(USD_RATES)
        # Should include USD→X and X→USD for every X in the table, plus crosses.
        assert ("USD", "EUR") in rates
        assert ("EUR", "USD") in rates
        assert ("EUR", "JPY") in rates

    def test_gaps_when_currency_missing_from_table(self):
        # If we ask for ZZZ but have no USD→ZZZ rate, pairs touching ZZZ drop.
        codes = ["USD", "EUR", "ZZZ"]
        rates = derive_all_cross_rates(USD_RATES, codes=codes)
        assert ("USD", "EUR") in rates
        assert ("ZZZ", "EUR") not in rates
        assert ("EUR", "ZZZ") not in rates

    def test_usd_to_usd_is_not_included(self):
        rates = derive_all_cross_rates(USD_RATES, codes=["USD", "EUR"])
        assert ("USD", "USD") not in rates
