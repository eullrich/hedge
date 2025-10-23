"""Enhanced Hyperliquid API client - replaces CoinGecko entirely."""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .base_client import BaseAPIClient
from ..utils.exceptions import APIResponseException


# Singleton instance to share rate limiter across entire app
_hyperliquid_client_instance = None


class HyperliquidClient(BaseAPIClient):
    """
    Complete Hyperliquid API client.

    Provides all market data functionality previously from CoinGecko:
    - Symbol/name mappings
    - Current prices
    - Historical OHLCV data
    - Market metadata
    """

    def __new__(cls):
        """Singleton pattern - only one instance with shared rate limiter."""
        global _hyperliquid_client_instance
        if _hyperliquid_client_instance is None:
            _hyperliquid_client_instance = super().__new__(cls)
        return _hyperliquid_client_instance

    def __init__(self):
        """Initialize Hyperliquid client (only runs once due to singleton)."""
        # Skip if already initialized
        if hasattr(self, '_initialized'):
            return

        super().__init__(
            base_url="https://api.hyperliquid.xyz",
            rate_limit_calls=54,  # 90% of 1200 weight/min (54 calls × 20 weight = 1080)
            rate_limit_period=60,
            cache_expiry=60,  # 1 minute cache for price data
            max_retries=5,  # More retries for flaky API
            timeout=30,
            verbose=False  # Reduce logging overhead
        )

        # Cache for metadata
        self._universe_cache: Optional[List[Dict[str, Any]]] = None
        self._universe_cache_time: Optional[datetime] = None
        self._initialized = True

    def _configure_session(self) -> None:
        """Configure session with Hyperliquid headers."""
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

    def _get_universe(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all available coins/markets (universe metadata).

        Args:
            force_refresh: Force refresh cached data

        Returns:
            List of coin metadata
        """
        # Use cache if available and fresh (5 minutes)
        if not force_refresh and self._universe_cache is not None:
            if self._universe_cache_time:
                age = (datetime.now() - self._universe_cache_time).total_seconds()
                if age < 300:  # 5 minutes
                    return self._universe_cache

        try:
            payload = {"type": "meta"}
            result = self.post('/info', json=payload, use_cache=True)

            if isinstance(result, dict) and 'universe' in result:
                self._universe_cache = result['universe']
                self._universe_cache_time = datetime.now()
                return self._universe_cache

            return []
        except Exception as e:
            print(f"❌ Error fetching Hyperliquid universe: {e}")
            return self._universe_cache or []

    def get_all_symbols(self) -> List[str]:
        """
        Get list of all available trading symbols.

        Returns:
            List of symbols (e.g., ['BTC', 'ETH', 'SOL'])
        """
        universe = self._get_universe()
        return [coin['name'] for coin in universe if not coin.get('isDelisted', False)]

    def get_symbol_metadata(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific symbol.

        Args:
            symbol: Trading symbol (e.g., 'BTC')

        Returns:
            Metadata dict or None if not found
        """
        universe = self._get_universe()
        for coin in universe:
            if coin['name'] == symbol and not coin.get('isDelisted', False):
                return coin
        return None

    def get_all_prices(self) -> Dict[str, float]:
        """
        Get current mid prices for all coins.

        Returns:
            Dict mapping symbols to prices
        """
        try:
            payload = {"type": "allMids"}
            result = self.post('/info', json=payload, use_cache=False)

            if isinstance(result, dict):
                # Convert string prices to floats
                return {symbol: float(price) for symbol, price in result.items()}

            return {}
        except Exception as e:
            print(f"❌ Error fetching prices: {e}")
            return {}

    def get_simple_price(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current prices for specific symbols (compatible with CoinGecko interface).

        Args:
            symbols: List of symbols to get prices for

        Returns:
            Dict mapping symbols to prices
        """
        all_prices = self.get_all_prices()
        return {symbol: all_prices.get(symbol, 0.0) for symbol in symbols}

    def get_coins_list(self) -> List[Dict[str, str]]:
        """
        Get list of all coins with id, symbol, and name (CoinGecko compatible).

        Returns:
            List of dicts with 'id', 'symbol', 'name'
        """
        universe = self._get_universe()
        coins = []

        for coin in universe:
            if not coin.get('isDelisted', False):
                symbol = coin['name']
                coins.append({
                    'id': symbol.lower(),  # Use symbol as ID
                    'symbol': symbol,
                    'name': symbol  # Hyperliquid doesn't provide full names
                })

        return coins

    def get_coins_markets(
        self,
        vs_currency: str = 'usd',
        order: str = 'volume_desc',
        per_page: int = 250,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get current market data for coins (CoinGecko compatible).

        Args:
            vs_currency: Target currency (ignored, always USD)
            order: Sort order (volume_desc, market_cap_desc, etc.)
            per_page: Results per page
            page: Page number

        Returns:
            List of market data dicts
        """
        prices = self.get_all_prices()
        universe = self._get_universe()

        markets = []
        for coin in universe:
            if coin.get('isDelisted', False):
                continue

            symbol = coin['name']
            price = prices.get(symbol, 0.0)

            markets.append({
                'id': symbol.lower(),
                'symbol': symbol,
                'name': symbol,
                'current_price': price,
                'market_cap': 0,  # Not available from Hyperliquid
                'total_volume': 0,  # Would need to aggregate from candle data
                'price_change_percentage_24h': 0,  # Would need historical data
            })

        # Simple pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        return markets[start_idx:end_idx]

    def get_market_chart(
        self,
        coin_id: str,
        vs_currency: str = 'usd',
        days: int = 90
    ) -> Dict[str, List[List[float]]]:
        """
        Get historical market data (CoinGecko compatible).

        Args:
            coin_id: Coin ID or symbol
            vs_currency: Target currency (ignored)
            days: Number of days

        Returns:
            Dict with 'prices', 'market_caps', 'total_volumes' arrays
        """
        # Convert coin_id to symbol
        symbol = coin_id.upper()

        # Determine interval based on days
        if days <= 1:
            interval = '5m'
        elif days <= 7:
            interval = '15m'
        elif days <= 30:
            interval = '1h'
        else:
            interval = '4h'

        # Fetch candles
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)

        candles = self.get_candles(symbol, interval, start_time, end_time)

        # Convert to CoinGecko format: [[timestamp_ms, value], ...]
        prices = []
        for candle in candles:
            try:
                timestamp_ms = candle['t']
                close_price = float(candle['c'])
                prices.append([timestamp_ms, close_price])
            except (KeyError, ValueError):
                continue

        return {
            'prices': prices,
            'market_caps': [],  # Not available
            'total_volumes': []  # Could be calculated from candles
        }

    def get_candles(
        self,
        symbol: str,
        interval: str = "5m",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV candle data from Hyperliquid.

        Args:
            symbol: Trading symbol (e.g., 'BTC', 'ETH')
            interval: Candle interval - "1m", "5m", "15m", "30m", "1h", "4h", etc.
            start_time: Start datetime (default: 24 hours ago)
            end_time: End datetime (default: now)
            limit: Max candles to fetch (Hyperliquid max: 5000)

        Returns:
            List of candle dicts with OHLCV data
        """
        # Default time range: last 24 hours
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(days=1)

        # Convert to milliseconds
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        # Build request payload
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": symbol,
                "interval": interval,
                "startTime": start_ms,
                "endTime": end_ms
            }
        }

        try:
            candles = self.post('/info', json=payload, use_cache=False)

            # Limit to requested number
            if isinstance(candles, list) and len(candles) > limit:
                candles = candles[-limit:]

            return candles if isinstance(candles, list) else []

        except Exception as e:
            print(f"❌ Error fetching Hyperliquid data for {symbol}: {e}")
            return []

    def get_candles_formatted(
        self,
        symbol: str,
        interval: str = "5m",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV candle data formatted for database storage.

        Args:
            symbol: Trading symbol
            interval: Candle interval
            start_time: Start datetime
            end_time: End datetime
            limit: Max candles

        Returns:
            List of dicts with: timestamp, open, high, low, close, volume
        """
        raw_candles = self.get_candles(symbol, interval, start_time, end_time, limit)

        formatted = []
        for candle in raw_candles:
            try:
                formatted.append({
                    'timestamp': datetime.fromtimestamp(candle['t'] / 1000),
                    'open': float(candle['o']),
                    'high': float(candle['h']),
                    'low': float(candle['l']),
                    'close': float(candle['c']),
                    'volume': float(candle.get('v', 0))
                })
            except (KeyError, ValueError, TypeError) as e:
                print(f"⚠️  Skipping malformed candle: {e}")
                continue

        return formatted

    def is_coin_supported(self, symbol: str) -> bool:
        """
        Check if a coin is supported on Hyperliquid.

        Args:
            symbol: Trading symbol

        Returns:
            True if supported, False otherwise
        """
        supported = self.get_all_symbols()
        return symbol.upper() in supported

    def get_supported_coins(self) -> List[str]:
        """
        Get list of all supported coin symbols.

        Returns:
            List of supported symbols
        """
        return self.get_all_symbols()

    # ==================== PERPETUALS / MICROSTRUCTURE DATA ====================

    def get_perp_meta_and_contexts(self) -> tuple[List[Dict], List[Dict]]:
        """
        Get perpetual metadata and asset contexts (includes funding, OI, prices).

        Returns:
            Tuple of (metadata_list, asset_contexts_list)
            Asset contexts include: markPx, funding, openInterest, premium, oraclePx
        """
        payload = {"type": "metaAndAssetCtxs"}
        result = self.post('/info', json=payload, use_cache=False)

        if isinstance(result, list) and len(result) >= 2:
            return result[0], result[1]
        return [], []

    def get_market_stats(self, symbol: str) -> Dict[str, Any]:
        """
        Get current market stats for a symbol (funding, OI, mark price, etc.).

        Args:
            symbol: Symbol like 'BTC-USD' or 'BTC'

        Returns:
            Dict with market stats including:
            - mark_price: Current mark price
            - funding_rate: Current funding rate (hourly)
            - open_interest: Total open interest
            - premium: Mark-Index premium
            - oracle_price: Oracle/index price
        """
        # Remove -USD suffix if present
        coin = symbol.replace('-USD', '').upper()

        meta, contexts = self.get_perp_meta_and_contexts()

        # Find the coin in the universe
        for idx, asset_meta in enumerate(meta.get('universe', [])):
            if asset_meta.get('name') == coin:
                ctx = contexts[idx]
                return {
                    'mark_price': float(ctx.get('markPx', 0)),
                    'funding_rate': float(ctx.get('funding', 0)),
                    'open_interest': float(ctx.get('openInterest', 0)),
                    'premium': float(ctx.get('premium', 0)),
                    'oracle_price': float(ctx.get('oraclePx', 0)),
                    'symbol': symbol,
                    'coin': coin
                }

        raise APIResponseException(f"Symbol {symbol} not found in perpetuals universe")

    def get_funding_history(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get historical funding rates for a symbol.

        Args:
            symbol: Symbol like 'BTC-USD' or 'BTC'
            start_time: Start datetime (default: 7 days ago)
            end_time: End datetime (default: now)

        Returns:
            List of funding rate entries with:
            - coin: Coin symbol
            - fundingRate: Funding rate
            - premium: Premium
            - time: Timestamp in milliseconds
            - timestamp: Datetime object (added)
        """
        # Remove -USD suffix if present
        coin = symbol.replace('-USD', '').upper()

        if start_time is None:
            start_time = datetime.now() - timedelta(days=7)

        start_ms = int(start_time.timestamp() * 1000)

        payload = {
            "type": "fundingHistory",
            "coin": coin,
            "startTime": start_ms
        }

        result = self.post('/info', json=payload, use_cache=False)

        # Add datetime objects for easier use
        if isinstance(result, list):
            for entry in result:
                entry['timestamp'] = datetime.fromtimestamp(entry['time'] / 1000)

        return result if isinstance(result, list) else []
