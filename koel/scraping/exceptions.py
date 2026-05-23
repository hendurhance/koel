class ScraperError(Exception):
    """Base for all scraping failures."""


class NetworkError(ScraperError):
    """Transport-level failure: DNS, TCP, TLS, timeout."""


class RateLimitError(ScraperError):
    """Source explicitly rate-limited us (HTTP 429 or equivalent)."""


class ParseError(ScraperError):
    """Response reached us intact but the rate couldn't be extracted."""


class BlockedError(ScraperError):
    """Response indicates we were blocked (captcha, WAF, 403)."""
