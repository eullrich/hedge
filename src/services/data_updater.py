"""Background data updater for OHLCV and metrics."""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ..api import HyperliquidClient
from ..database import DatabaseManager
from ..utils.indicators import (
    calculate_rsi, calculate_volatility, calculate_beta,
    calculate_volume_profile, detect_trend, calculate_relative_strength
)
from ..utils.metrics import calculate_correlation


class DataUpdater:
    """Handles background updates of OHLCV data and metrics calculation."""

    def __init__(self, api_client: HyperliquidClient, db_manager: DatabaseManager):
        """Initialize data updater."""
        self.api = api_client
        self.db = db_manager
        self._db_write_lock = threading.Lock()  # Serialize SQLite writes

    def update_ohlcv_for_coin(
        self,
        coin_id: str,
        days: int = 365
    ) -> tuple[int, Optional[str]]:
        """
        Fetch and store OHLCV data for a single coin at multiple granularities.

        CoinGecko API Granularity Mapping:
        - days=1: 5-minute candles (aggregated to 15min - 96 candles for last 24 hours)
        - days=7: 1-hour candles (168 candles for last 7 days)
        - days=90: 4-hour candles (fetched, then pruned to 60 days = 360 candles)

        Strategy: Fetch all three granularities to support Scalping/Intraday/Swing
        - 15min: Last 24 hours for scalping (aggregated from 5min)
        - 1hour: Last 7 days for intraday
        - 4hour: Fetch 90 days (API limit), prune to 60 days for swing

        Args:
            coin_id: Coin ID to fetch
            days: Days of history to fetch (not used, kept for API compatibility)

        Returns:
            Tuple of (candles_added, error_message)
        """
        try:
            candles_added = 0

            # Hyperliquid uses just coin names like 'BTC' (no -USD suffix)
            # Extract coin name without suffix for API calls
            coin_symbol = coin_id.upper().replace('-USD', '')

            with self.db.get_session() as session:
                # Fetch 1: Last 24 hours with 5-minute candles from Hyperliquid (for scalping)
                if self.api.is_coin_supported(coin_symbol):
                    end_time = datetime.now()

                    # Incremental fetch: Get latest timestamp from DB
                    latest_5min = self.db.get_latest_timestamp(session, coin_id, '5min')
                    if latest_5min and (end_time - latest_5min) < timedelta(days=1):
                        # Data exists and is recent - fetch only new candles
                        start_time = latest_5min + timedelta(minutes=5)
                    else:
                        # No data or very old - fetch full 24 hours
                        start_time = end_time - timedelta(days=1)

                    data_5min = self.api.get_candles_formatted(
                        coin_symbol,
                        interval='5m',
                        start_time=start_time,
                        end_time=end_time
                    )

                    # Batch insert all 5min candles at once (write queue handles concurrency)
                    if data_5min:
                        self.db.batch_upsert_ohlcv_data(
                            session,
                            coin_id=coin_id,
                            candles=data_5min,
                            granularity='5min'
                        )
                        candles_added += len(data_5min)
                else:
                    print(f"⚠️  {coin_symbol} not supported on Hyperliquid, skipping 5min data")

                # Fetch 2: Last 7 days with 1-hour candles from Hyperliquid (for intraday)
                if self.api.is_coin_supported(coin_symbol):
                    end_time = datetime.now()

                    # Incremental fetch: Get latest timestamp from DB
                    latest_1hour = self.db.get_latest_timestamp(session, coin_id, '1hour')
                    if latest_1hour and (end_time - latest_1hour) < timedelta(days=7):
                        # Data exists and is recent - fetch only new candles
                        start_time = latest_1hour + timedelta(hours=1)
                    else:
                        # No data or very old - fetch full 7 days
                        start_time = end_time - timedelta(days=7)

                    data_1hour = self.api.get_candles_formatted(
                        coin_symbol,
                        interval='1h',
                        start_time=start_time,
                        end_time=end_time
                    )

                    # Batch insert all 1hour candles at once (write queue handles concurrency)
                    if data_1hour:
                        self.db.batch_upsert_ohlcv_data(
                            session,
                            coin_id=coin_id,
                            candles=data_1hour,
                            granularity='1hour'
                        )
                        candles_added += len(data_1hour)
                else:
                    print(f"⚠️  {coin_symbol} not supported on Hyperliquid, skipping 1hour data")

                # Fetch 3: Last 60 days with 4-hour candles from Hyperliquid (for swing)
                if self.api.is_coin_supported(coin_symbol):
                    end_time = datetime.now()

                    # Incremental fetch: Get latest timestamp from DB
                    latest_4hour = self.db.get_latest_timestamp(session, coin_id, '4hour')
                    if latest_4hour and (end_time - latest_4hour) < timedelta(days=60):
                        # Data exists and is recent - fetch only new candles
                        start_time = latest_4hour + timedelta(hours=4)
                    else:
                        # No data or very old - fetch full 60 days
                        start_time = end_time - timedelta(days=60)

                    data_4hour = self.api.get_candles_formatted(
                        coin_symbol,
                        interval='4h',
                        start_time=start_time,
                        end_time=end_time
                    )

                    # Batch insert all 4hour candles at once (write queue handles concurrency)
                    if data_4hour:
                        self.db.batch_upsert_ohlcv_data(
                            session,
                            coin_id=coin_id,
                            candles=data_4hour,
                            granularity='4hour'
                        )
                        candles_added += len(data_4hour)
                else:
                    print(f"⚠️  {coin_symbol} not supported on Hyperliquid, skipping 4hour data")

                session.commit()

            return candles_added, None

        except Exception as e:
            error_msg = f"Error fetching OHLCV for {coin_id}: {str(e)}"
            print(f"❌ {error_msg}")
            return 0, error_msg

    def update_ohlcv_for_all_tokens(self, stale_only: bool = True) -> Dict[str, Any]:
        """
        Update OHLCV data for ALL available Hyperliquid tokens.
        Fetches all three granularities (1h/4h for all tokens).

        Args:
            stale_only: If True, only update coins with stale data (default: True)

        Returns:
            Dict with update statistics
        """
        print("🔄 Starting multi-granularity OHLCV update for ALL Hyperliquid tokens...")

        # Get all available perpetual tokens from Hyperliquid
        try:
            symbols = self.api.get_all_symbols()
            all_coin_ids = sorted([s for s in symbols if s])
            print(f"📊 Found {len(all_coin_ids)} perpetual tokens on Hyperliquid")
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error fetching symbols: {error_msg}")

            # Check if API is down
            if "500" in error_msg or "502" in error_msg or "503" in error_msg:
                print("⚠️ Hyperliquid API appears to be experiencing issues")
                print("   Skipping update - data will be fetched when API recovers")
                return {'coins_updated': 0, 'coins_failed': 0, 'errors': [error_msg], 'api_down': True}

            return {'coins_updated': 0, 'coins_failed': 0, 'errors': [error_msg]}

        # Filter to only stale coins if requested
        if stale_only:
            from sqlalchemy import text
            with self.db.get_session() as session:
                stale_query = text("""
                    SELECT DISTINCT coin_id
                    FROM ohlcv_data
                    GROUP BY coin_id, granularity
                    HAVING
                        (granularity = '5min' AND
                         (JULIANDAY(datetime('now', 'localtime')) - JULIANDAY(MAX(timestamp))) * 24 > 1) OR
                        (granularity = '1hour' AND
                         (JULIANDAY(datetime('now', 'localtime')) - JULIANDAY(MAX(timestamp))) * 24 > 4) OR
                        (granularity = '4hour' AND
                         (JULIANDAY(datetime('now', 'localtime')) - JULIANDAY(MAX(timestamp))) * 24 > 8)
                """)
                stale_results = session.execute(stale_query).fetchall()
                stale_coin_ids = {row[0] for row in stale_results}

                # Also include coins with no data at all
                all_coin_ids_set = set(all_coin_ids)
                existing_query = text("SELECT DISTINCT coin_id FROM ohlcv_data")
                existing_results = session.execute(existing_query).fetchall()
                existing_coin_ids = {row[0] for row in existing_results}
                missing_coin_ids = all_coin_ids_set - existing_coin_ids

                # Combine stale + missing
                coin_ids = sorted(stale_coin_ids | missing_coin_ids)

            if coin_ids:
                print(f"📊 Found {len(coin_ids)} coins with stale/missing data (out of {len(all_coin_ids)} total)")
            else:
                print(f"✅ All {len(all_coin_ids)} coins have fresh data - nothing to update!")
                return {'coins_updated': 0, 'coins_failed': 0, 'errors': [], 'skipped': True}
        else:
            coin_ids = all_coin_ids
            print(f"📊 Force updating ALL {len(coin_ids)} tokens (ignoring freshness)")

        with self.db.get_session() as session:
            # Create update log
            log = self.db.create_update_log(session, 'ohlcv')
            session.commit()
            log_id = log.id

        if not coin_ids:
            print("⚠️  No tokens available")
            return {'coins_updated': 0, 'coins_failed': 0}

        print(f"📊 Updating {len(coin_ids)} tokens with 3 granularities each...")

        coins_updated = 0
        coins_failed = 0
        errors = []

        # Use ThreadPoolExecutor for parallel API calls
        # Balanced parallelism to avoid rate limiting
        max_workers = 5  # 5 parallel workers
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all jobs
            future_to_coin = {
                executor.submit(self.update_ohlcv_for_coin, coin_id, 180): coin_id
                for coin_id in coin_ids
            }

            # Process completed jobs
            for future in as_completed(future_to_coin):
                coin_id = future_to_coin[future]
                try:
                    candles_added, error = future.result()
                    if error:
                        coins_failed += 1
                        errors.append(error)
                    else:
                        coins_updated += 1

                    # Progress indicator
                    total = coins_updated + coins_failed
                    if total % 10 == 0:
                        print(f"  Progress: {total}/{len(coin_ids)} tokens processed...")

                except Exception as e:
                    coins_failed += 1
                    errors.append(f"{coin_id}: {str(e)}")

        print(f"  ✅ Processed {len(coin_ids)} tokens ({max_workers} parallel workers)")

        # Wait for write queue to finish before pruning
        if self.db.write_queue:
            queue_depth = self.db.write_queue.get_queue_depth()
            if queue_depth > 0:
                print(f"⏳ Waiting for {queue_depth} queued writes to complete...")
                self.db.write_queue.wait(timeout=120)
                print("✅ Write queue drained")

        # Prune old data to maintain rolling windows
        print("\n🗑️  Pruning old OHLCV data...")
        with self.db.get_session() as session:
            pruned_counts = self.db.prune_old_ohlcv_data(session)
            print(f"   Pruned: 5min={pruned_counts['5min']}, 1hour={pruned_counts['1hour']}, 4hour={pruned_counts['4hour']}")

        # Complete the log
        with self.db.get_session() as session:
            error_msg = "; ".join(errors[:10]) if errors else None  # Limit error message
            self.db.complete_update_log(
                session,
                log_id,
                coins_updated,
                coins_failed,
                error_msg
            )
            session.commit()

        print(f"✅ OHLCV update complete: {coins_updated} updated, {coins_failed} failed")

        return {
            'coins_updated': coins_updated,
            'coins_failed': coins_failed,
            'errors': errors
        }

    def update_ohlcv_for_watchlist(self) -> Dict[str, Any]:
        """
        Update OHLCV data for all coins in explorer watchlist.
        Fetches all three granularities (5min/1hour/4hour) and prunes old data.

        Returns:
            Dict with update statistics
        """
        print("🔄 Starting multi-granularity OHLCV update for watchlist coins...")

        with self.db.get_session() as session:
            # Get active watchlist coins
            watchlist = self.db.get_explorer_watchlist(session, active_only=True)
            coin_ids = [item.coin_id for item in watchlist]

            # Create update log
            log = self.db.create_update_log(session, 'ohlcv')
            session.commit()
            log_id = log.id

        if not coin_ids:
            print("⚠️  No coins in watchlist")
            return {'coins_updated': 0, 'coins_failed': 0}

        print(f"📊 Updating {len(coin_ids)} coins with 3 granularities each...")

        coins_updated = 0
        coins_failed = 0
        errors = []

        for coin_id in coin_ids:
            candles_added, error = self.update_ohlcv_for_coin(coin_id, days=180)

            if error:
                coins_failed += 1
                errors.append(error)
            else:
                coins_updated += 1

            # No rate limiting needed - Hyperliquid has no rate limits for public data
            # Optional: small delay to be respectful to the API
            time.sleep(0.5)

        # Prune old data to maintain rolling windows
        print("\n🗑️  Pruning old OHLCV data...")
        with self.db.get_session() as session:
            pruned_counts = self.db.prune_old_ohlcv_data(session)
            print(f"   Pruned: 5min={pruned_counts['5min']}, 1hour={pruned_counts['1hour']}, 4hour={pruned_counts['4hour']}")

        # Complete the log
        with self.db.get_session() as session:
            error_msg = "; ".join(errors) if errors else None
            self.db.complete_update_log(
                session,
                log_id,
                coins_updated,
                coins_failed,
                error_msg
            )
            session.commit()

        print(f"✅ OHLCV update complete: {coins_updated} updated, {coins_failed} failed")

        return {
            'coins_updated': coins_updated,
            'coins_failed': coins_failed,
            'errors': errors
        }

    def calculate_metrics_for_coin(
        self,
        coin_id: str,
        lookback_days: int,
        reference_coin_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate metrics for a coin from OHLCV data.

        Args:
            coin_id: Coin to calculate for
            lookback_days: Lookback period (14, 30, 90, or 180)
            reference_coin_id: Optional reference coin for relative metrics

        Returns:
            Dict of calculated metrics or None if insufficient data
        """
        # Determine granularity based on three-tier system
        # All data from Hyperliquid API (no rate limits, high-quality data)
        # Scalping: 1 day / 5min candles
        # Intraday: 7 days / 1hour candles
        # Swing: 60 days / 4hour candles
        if lookback_days <= 1:
            granularity = '5min'
        elif lookback_days <= 7:
            granularity = '1hour'
        else:
            granularity = '4hour'

        with self.db.get_session() as session:
            # Get OHLCV data for the lookback period
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            ohlcv_data = self.db.get_ohlcv_data(
                session,
                coin_id,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity
            )

            # Adjust minimum candles based on lookback period
            # For very short lookbacks (< 1 day), we need at least 2 candles
            # For normal lookbacks, we need at least 7 candles for meaningful stats
            min_candles = 2 if lookback_days < 1 else 7

            if len(ohlcv_data) < min_candles:
                print(f"⚠️  Insufficient data for {coin_id} ({len(ohlcv_data)} candles, need {min_candles})")
                return None

            # Convert to DataFrame
            df = pd.DataFrame([{
                'timestamp': candle.timestamp,
                'open': candle.open,
                'high': candle.high,
                'low': candle.low,
                'close': candle.close,
                'volume': candle.volume
            } for candle in ohlcv_data])

            df = df.set_index('timestamp').sort_index()

            # Get current price and calculate change
            current_price = df['close'].iloc[-1]
            first_price = df['close'].iloc[0]
            price_change_pct = ((current_price - first_price) / first_price) * 100

            # Calculate absolute metrics
            close_prices = df['close']

            rsi = calculate_rsi(close_prices, period=14)
            volatility = calculate_volatility(close_prices, period=lookback_days)
            trend = detect_trend(close_prices)

            # Calculate beta vs Bitcoin
            btc_data = self.db.get_ohlcv_data(
                session,
                'BTC',  # Now using symbol instead of coin_id
                start_date=start_date,
                end_date=end_date,
                granularity=granularity
            )

            if btc_data and len(btc_data) > 7:
                btc_df = pd.DataFrame([{
                    'timestamp': candle.timestamp,
                    'close': candle.close
                } for candle in btc_data])
                btc_df = btc_df.set_index('timestamp').sort_index()

                # Align timestamps
                aligned = pd.DataFrame({
                    'coin': df['close'],
                    'btc': btc_df['close']
                }).dropna()

                if len(aligned) >= 7:
                    beta = calculate_beta(aligned['coin'], aligned['btc'])
                else:
                    beta = 1.0
            else:
                beta = 1.0

            # Get market cap and volume from coin table
            coin = self.db.get_coin(session, coin_id)
            volume_24h = coin.volume_24h if coin else 0
            market_cap = coin.market_cap if coin else 1

            volume_metrics = calculate_volume_profile(volume_24h, market_cap)

            metrics = {
                'current_price': current_price,
                'price_change_pct': price_change_pct,
                'rsi': rsi,
                'volatility': volatility,
                'beta': beta,
                'trend': trend,
                'volume_to_mcap': volume_metrics['volume_to_mcap_ratio'],
                'liquidity_rating': volume_metrics['liquidity_rating']
            }

            # Calculate relative metrics if reference coin provided
            if reference_coin_id:
                ref_data = self.db.get_ohlcv_data(
                    session,
                    reference_coin_id,
                    start_date=start_date,
                    end_date=end_date,
                    granularity=granularity
                )

                if ref_data and len(ref_data) >= 7:
                    ref_df = pd.DataFrame([{
                        'timestamp': candle.timestamp,
                        'close': candle.close
                    } for candle in ref_data])
                    ref_df = ref_df.set_index('timestamp').sort_index()

                    # Align prices
                    aligned = pd.DataFrame({
                        'coin': df['close'],
                        'ref': ref_df['close']
                    }).dropna()

                    if len(aligned) >= 7:
                        # Correlation
                        correlation = calculate_correlation(
                            aligned['coin'],
                            aligned['ref'],
                            method='pearson'
                        )

                        # Relative strength
                        rel_strength = calculate_relative_strength(
                            aligned['coin'],
                            aligned['ref'],
                            period=min(lookback_days, len(aligned))
                        )

                        # Spread z-score
                        ratio = aligned['coin'] / aligned['ref']
                        ratio_mean = ratio.mean()
                        ratio_std = ratio.std()
                        current_ratio = ratio.iloc[-1]
                        spread_zscore = (current_ratio - ratio_mean) / ratio_std if ratio_std > 0 else 0

                        # Suggest position based on spread
                        if abs(spread_zscore) < 1.5:
                            suggested_position = '-'
                        elif spread_zscore > 2.0:
                            suggested_position = 'SHORT'
                        elif spread_zscore < -2.0:
                            suggested_position = 'LONG'
                        elif spread_zscore > 1.5:
                            suggested_position = 'short'
                        else:
                            suggested_position = 'long'

                        metrics.update({
                            'correlation': correlation,
                            'ratio_current': rel_strength['ratio_current'],
                            'ratio_trend': rel_strength['ratio_trend'],
                            'outperformance': rel_strength['outperformance'],
                            'spread_zscore': spread_zscore,
                            'suggested_position': suggested_position
                        })

            return metrics

    def update_metrics_for_watchlist(
        self,
        lookback_days: int = 30,
        reference_coin_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate and cache metrics for all watchlist coins.

        Args:
            lookback_days: Lookback period
            reference_coin_id: Optional reference coin

        Returns:
            Dict with update statistics
        """
        ref_str = f" vs {reference_coin_id}" if reference_coin_id else ""
        print(f"🔄 Calculating metrics for {lookback_days}d lookback{ref_str}...")

        with self.db.get_session() as session:
            watchlist = self.db.get_explorer_watchlist(session, active_only=True)
            coin_ids = [item.coin_id for item in watchlist]

            log = self.db.create_update_log(session, 'metrics')
            session.commit()
            log_id = log.id

        if not coin_ids:
            print("⚠️  No coins in watchlist")
            return {'coins_updated': 0, 'coins_failed': 0}

        coins_updated = 0
        coins_failed = 0
        errors = []

        for coin_id in coin_ids:
            try:
                metrics = self.calculate_metrics_for_coin(
                    coin_id,
                    lookback_days,
                    reference_coin_id
                )

                if metrics:
                    with self.db.get_session() as session:
                        self.db.upsert_explorer_metrics(
                            session,
                            coin_id,
                            lookback_days,
                            metrics,
                            reference_coin_id
                        )
                        session.commit()
                    coins_updated += 1
                else:
                    coins_failed += 1
                    errors.append(f"{coin_id}: insufficient data")

            except Exception as e:
                coins_failed += 1
                error_msg = f"{coin_id}: {str(e)}"
                errors.append(error_msg)
                print(f"❌ {error_msg}")

        with self.db.get_session() as session:
            error_msg = "; ".join(errors[:5]) if errors else None  # Limit error message length
            self.db.complete_update_log(
                session,
                log_id,
                coins_updated,
                coins_failed,
                error_msg
            )
            session.commit()

        print(f"✅ Metrics update complete: {coins_updated} updated, {coins_failed} failed")

        return {
            'coins_updated': coins_updated,
            'coins_failed': coins_failed,
            'errors': errors
        }

    def calculate_pairwise_correlations(
        self,
        reference_coins: List[str] = None
    ) -> Dict[str, Any]:
        """
        Pre-calculate pairwise correlations for discovery feature.
        Calculates correlation/z-score between reference coins and ALL other tokens.

        Args:
            reference_coins: List of reference coins to calculate against (e.g., ['BTC', 'ETH'])
                           If None, uses top popular coins

        Returns:
            Dict with calculation statistics
        """
        print("🔄 Calculating pairwise correlations for discovery...")

        # Default to popular reference coins
        if reference_coins is None:
            reference_coins = ['BTC', 'ETH', 'SOL', 'ARB', 'AVAX', 'DOGE', 'MATIC', 'LINK']

        # Get all available tokens
        try:
            all_symbols = self.api.get_all_symbols()
            all_tokens = sorted([s for s in all_symbols if s])
            print(f"📊 Found {len(all_tokens)} total tokens on Hyperliquid")
        except Exception as e:
            print(f"❌ Error fetching symbols: {e}")
            return {'pairs_calculated': 0, 'pairs_failed': 0, 'errors': [str(e)]}

        # Timeframe configuration matching discovery
        timeframe_configs = [
            {'days': 1, 'granularity': '1hour'},      # Scalping
            {'days': 7, 'granularity': '1hour'},      # Intraday
            {'days': 60, 'granularity': '4hour'},     # Swing
        ]

        total_calculated = 0
        total_failed = 0
        errors = []

        with self.db.get_session() as session:
            log = self.db.create_update_log(session, 'pairwise_correlations')
            session.commit()
            log_id = log.id

        for ref_coin in reference_coins:
            ref_coin_upper = ref_coin.upper()

            # Skip if reference coin not in available tokens
            if ref_coin_upper not in all_tokens:
                print(f"⚠️  {ref_coin_upper} not available, skipping...")
                continue

            print(f"\n📈 Processing reference coin: {ref_coin_upper}")

            # Get comparison coins (all except reference)
            comparison_coins = [t for t in all_tokens if t != ref_coin_upper]

            for config in timeframe_configs:
                days = config['days']
                granularity = config['granularity']

                print(f"  ⏱️  Timeframe: {days} days ({granularity})")

                # Fetch reference coin data
                with self.db.get_session() as session:
                    from datetime import datetime, timedelta
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=days)

                    ref_ohlcv = self.db.get_ohlcv_data(
                        session,
                        coin_id=ref_coin_upper,
                        start_date=start_date,
                        end_date=end_date,
                        granularity=granularity
                    )

                    if len(ref_ohlcv) < 10:
                        print(f"    ⚠️  Insufficient data for {ref_coin_upper}, skipping timeframe")
                        continue

                    ref_prices = [candle.close for candle in ref_ohlcv]

                # Calculate against each comparison coin
                for coin in comparison_coins:
                    try:
                        # Fetch comparison coin data
                        with self.db.get_session() as session:
                            coin_ohlcv = self.db.get_ohlcv_data(
                                session,
                                coin_id=coin,
                                start_date=start_date,
                                end_date=end_date,
                                granularity=granularity
                            )

                            if len(coin_ohlcv) < 10:
                                continue

                            coin_prices = [candle.close for candle in coin_ohlcv]

                        # Align data
                        import numpy as np
                        min_len = min(len(ref_prices), len(coin_prices))
                        if min_len < 10:
                            continue

                        ref_aligned = np.array(ref_prices[-min_len:])
                        coin_aligned = np.array(coin_prices[-min_len:])

                        # Calculate correlation
                        correlation = np.corrcoef(ref_aligned, coin_aligned)[0, 1]

                        # Calculate ratio and z-score
                        ratio = ref_aligned / coin_aligned
                        ratio_mean = np.mean(ratio)
                        ratio_std = np.std(ratio)
                        current_ratio = ratio[-1]
                        zscore = (current_ratio - ratio_mean) / ratio_std if ratio_std > 0 else 0.0

                        # Determine suggested position
                        if abs(zscore) < 1.5:
                            suggested_position = '-'
                        elif zscore > 2.0:
                            suggested_position = 'SHORT'
                        elif zscore < -2.0:
                            suggested_position = 'LONG'
                        elif zscore > 1.5:
                            suggested_position = 'short'
                        else:
                            suggested_position = 'long'

                        # Store in database
                        metrics = {
                            'correlation': float(correlation),
                            'spread_zscore': float(zscore),
                            'ratio_current': float(current_ratio),
                            'suggested_position': suggested_position,
                        }

                        with self.db.get_session() as session:
                            self.db.upsert_explorer_metrics(
                                session,
                                coin_id=coin,
                                lookback_days=days,
                                metrics=metrics,
                                reference_coin_id=ref_coin_upper
                            )
                            session.commit()

                        total_calculated += 1

                    except Exception as e:
                        total_failed += 1
                        if len(errors) < 10:  # Limit error collection
                            errors.append(f"{ref_coin_upper}/{coin} ({days}d): {str(e)}")

                print(f"  ✅ Calculated {total_calculated} pairs for {ref_coin_upper} @ {days}d")

        # Complete the log
        with self.db.get_session() as session:
            error_msg = "; ".join(errors[:5]) if errors else None
            self.db.complete_update_log(
                session,
                log_id,
                total_calculated,
                total_failed,
                error_msg
            )
            session.commit()

        print(f"✅ Pairwise correlation calculation complete: {total_calculated} calculated, {total_failed} failed")

        return {
            'pairs_calculated': total_calculated,
            'pairs_failed': total_failed,
            'errors': errors
        }

    def full_update(self) -> Dict[str, Any]:
        """
        Perform full update: OHLCV data + metrics for all lookback periods.
        Automatically calculates metrics for ALL watchlist coins as reference legs.

        Returns:
            Dict with update statistics
        """
        print("🚀 Starting full update...")

        # Step 1: Update OHLCV data
        ohlcv_result = self.update_ohlcv_for_watchlist()

        # Step 2: Get all watchlist coins to use as reference legs
        with self.db.get_session() as session:
            watchlist = self.db.get_explorer_watchlist(session, active_only=True)
            reference_coins = [item.coin_id for item in watchlist]

        print(f"📊 Will calculate metrics for {len(reference_coins)} reference coins")

        # Step 3: Update absolute metrics (no reference)
        lookback_periods = [30, 90, 180, 360]
        metrics_results = {}

        for lookback in lookback_periods:
            result = self.update_metrics_for_watchlist(lookback_days=lookback)
            metrics_results[f'{lookback}d_absolute'] = result

        # Step 4: Update relative metrics for ALL watchlist coins as reference legs
        pair_results = {}
        for ref_coin in reference_coins:
            print(f"\n  📈 Reference: {ref_coin}")
            for lookback in lookback_periods:
                result = self.update_metrics_for_watchlist(
                    lookback_days=lookback,
                    reference_coin_id=ref_coin
                )
                key = f'{lookback}d_vs_{ref_coin}'
                pair_results[key] = result

        print("✅ Full update complete!")

        return {
            'ohlcv': ohlcv_result,
            'metrics_absolute': metrics_results,
            'metrics_pairs': pair_results
        }
