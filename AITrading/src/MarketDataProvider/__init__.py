"""Market data provider package.

The package exposes a small provider layer for the trading training app. It is
designed around free public sources and does not depend on vendor-only keys.
"""

from .provider import MarketDataProvider
from .public_fetchers import create_demo_provider
from .types import DataResult, DataSource, ProviderError

__all__ = [
    "create_demo_provider",
    "DataResult",
    "DataSource",
    "MarketDataProvider",
    "ProviderError",
]
