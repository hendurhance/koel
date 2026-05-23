from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

USD = "USD"


def cross_rate(base: str, target: str, usd_rates: Mapping[str, Decimal]) -> Decimal:
    """Derive ``base → target`` from the USD table."""
    if base == target:
        return Decimal(1)
    if base == USD:
        return _lookup(usd_rates, target)
    if target == USD:
        return Decimal(1) / _lookup(usd_rates, base)
    # Single division preserves Decimal precision better than two ops.
    return _lookup(usd_rates, target) / _lookup(usd_rates, base)


def derive_all_cross_rates(
    usd_rates: Mapping[str, Decimal],
    codes: Iterable[str] | None = None,
) -> dict[tuple[str, str], Decimal]:
    """Return a dict of every (base, target) → rate for the given currency codes.

    If `codes` is None, uses the full set of currencies present in `usd_rates`
    (plus USD itself). Self-pairs (USD → USD, EUR → EUR, …) are omitted.
    """
    currencies = list(codes) if codes is not None else [USD, *usd_rates.keys()]
    out: dict[tuple[str, str], Decimal] = {}
    for base in currencies:
        for target in currencies:
            if base == target:
                continue
            try:
                out[(base, target)] = cross_rate(base, target, usd_rates)
            except KeyError:
                # Silently drop pairs we can't derive — the caller sees the
                # gap and can decide whether to fall back or warn.
                continue
    return out


def _lookup(table: Mapping[str, Decimal], code: str) -> Decimal:
    try:
        rate = table[code]
    except KeyError as exc:
        raise KeyError(f"no USD rate for {code!r}") from exc
    if rate <= 0:
        raise ValueError(f"non-positive USD rate for {code!r}: {rate}")
    return rate
