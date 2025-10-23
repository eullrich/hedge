"""QML bridge for Pair Discovery data."""
from PyQt6.QtCore import QObject, QAbstractTableModel, Qt, pyqtSignal, pyqtSlot, QModelIndex, pyqtProperty
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.database import DatabaseManager
from src.api import HyperliquidClient


class DiscoveryModel(QAbstractTableModel):
    """Qt model for exposing pair discovery data to QML."""

    # Signals
    scanComplete = pyqtSignal(int)  # number of pairs found
    availableTokensChanged = pyqtSignal()

    def __init__(self, db_manager: DatabaseManager, api_client: HyperliquidClient, watchlist_model=None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.api_client = api_client
        self.watchlist_model = watchlist_model
        self._items: List[Dict[str, Any]] = []
        self._available_tokens: List[str] = []
        self._sort_column = 'correlation'  # Default sort by correlation
        self._sort_ascending = False  # Descending by default

        # Load available tokens from Hyperliquid on init
        self._load_available_tokens()

    def rowCount(self, parent=QModelIndex()):
        """Return number of rows."""
        return len(self._items)

    def columnCount(self, parent=QModelIndex()):
        """Return number of columns."""
        return 9  # Pair, Correlation, Cointegration, Z-Score, Signal, Price, 24h Change, 7d Change, Actions

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return data for given index and role."""
        if not index.isValid() or index.row() >= len(self._items):
            return None

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        item = self._items[index.row()]
        column = index.column()

        # Return data based on column
        if column == 0:
            return item.get('pair', '')
        elif column == 1:
            return item.get('correlation', 0.0)
        elif column == 2:
            return item.get('is_cointegrated', False)
        elif column == 3:
            return item.get('zscore', 0.0)
        elif column == 4:
            return item.get('signal', 'NEUTRAL')
        elif column == 5:
            return item.get('price', 0.0)
        elif column == 6:
            return item.get('change_24h', 0.0)
        elif column == 7:
            return item.get('change_7d', 0.0)
        elif column == 8:
            return ""  # Actions column (rendered in QML)

        return None

    def roleNames(self):
        """Return mapping of role IDs to role names for QML."""
        return {
            Qt.ItemDataRole.DisplayRole: b'display',
        }

    @pyqtSlot(str, int)
    def scanPairs(self, reference_coin: str, timeframe_index: int):
        """
        Scan for trading pairs based on reference coin and timeframe.
        This will discover pairs and run analysis automatically.

        Args:
            reference_coin: Reference coin symbol (e.g., 'BTC', 'ETH')
            timeframe_index: 0 = Scalping (1 day), 1 = Intraday (7 days), 2 = Swing (60 days)
        """
        print(f"🔍 Scanning for pairs with reference: {reference_coin}, timeframe index: {timeframe_index}")

        self.beginResetModel()

        try:
            import pandas as pd
            import numpy as np
            from datetime import datetime, timedelta

            # Map timeframe index to days and intervals
            timeframe_config = {
                0: {'days': 1, 'interval': '1h', 'limit': 24},      # Scalping: 1 day, 1h candles
                1: {'days': 7, 'interval': '1h', 'limit': 168},     # Intraday: 7 days, 1h candles
                2: {'days': 60, 'interval': '4h', 'limit': 360},    # Swing: 60 days, 4h candles
            }
            config = timeframe_config.get(timeframe_index, timeframe_config[1])
            days = config['days']
            interval = config['interval']
            limit = config['limit']

            # Get all available tokens
            all_tokens = self._available_tokens
            if not all_tokens:
                print("⚠️  No tokens available")
                self._items = []
                self.scanComplete.emit(0)
                self.endResetModel()
                return

            # Get other coins (exclude reference coin)
            other_coins = [token for token in all_tokens if token.upper() != reference_coin.upper()]
            reference_coin_upper = reference_coin.upper()

            print(f"📊 Scanning {len(other_coins)} tokens against reference {reference_coin_upper}")
            print(f"⏱️  Timeframe: {days} days, interval: {interval}, limit: {limit} candles")

            # Scan ALL coins since we have DB cache (no performance penalty)
            scan_coins = other_coins
            print(f"🔍 Analyzing {len(scan_coins)} coins from database...")

            # Try to use pre-calculated correlations first (instant)
            with self.db.get_session() as session:
                cached_metrics = self.db.get_explorer_metrics_bulk(
                    session,
                    coin_ids=scan_coins,
                    lookback_days=days,
                    reference_coin_id=reference_coin_upper
                )

            if cached_metrics and len(cached_metrics) > 20:
                # Use cached correlations (instant path)
                print(f"✨ Using {len(cached_metrics)} pre-calculated correlations from cache")

                results = []
                for metric in cached_metrics:
                    # Filter by correlation threshold
                    if abs(metric.correlation or 0.0) >= 0.7:
                        results.append({
                            'coin1': reference_coin_upper,
                            'coin2': metric.coin_id,
                            'correlation': metric.correlation,
                            'zscore': metric.spread_zscore,
                            'current_ratio': metric.ratio_current,
                        })

                # Sort by correlation (descending)
                results.sort(key=lambda x: abs(x['correlation']), reverse=True)
                print(f"✅ Found {len(results)} correlated pairs from cache (correlation ≥ 0.7)")

            else:
                # Fall back to database calculation (fast path using local data)
                print(f"💾 Calculating correlations from database...")

                # Map interval to granularity
                granularity_map = {'1h': '1hour', '4h': '4hour', '5m': '5min'}
                granularity = granularity_map.get(interval, '1hour')

                # Fetch reference coin data from database
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)

                with self.db.get_session() as session:
                    ref_data = self.db.get_ohlcv_data(
                        session,
                        coin_id=reference_coin_upper,
                        start_date=start_date,
                        end_date=end_date,
                        granularity=granularity
                    )

                    if not ref_data or len(ref_data) < 10:
                        print(f"❌ Insufficient database data for reference coin {reference_coin_upper}")
                        print(f"   Run 'Force Refresh' on the Analysis page to populate database")
                        self._items = []
                        self.scanComplete.emit(0)
                        self.endResetModel()
                        return

                    # Convert to prices array
                    ref_prices = np.array([c.close for c in ref_data])
                    print(f"📊 Loaded {len(ref_prices)} candles for {reference_coin_upper} from database")

                # Scan each coin against reference using database
                results = []
                processed = 0
                for coin in scan_coins:
                    try:
                        with self.db.get_session() as session:
                            coin_data = self.db.get_ohlcv_data(
                                session,
                                coin_id=coin.upper(),
                                start_date=start_date,
                                end_date=end_date,
                                granularity=granularity
                            )

                        if not coin_data or len(coin_data) < 10:
                            continue

                        coin_prices = np.array([c.close for c in coin_data])

                        # Align data length
                        min_len = min(len(ref_prices), len(coin_prices))
                        if min_len < 10:
                            continue

                        ref_aligned = ref_prices[-min_len:]
                        coin_aligned = coin_prices[-min_len:]

                        # Calculate correlation
                        correlation = np.corrcoef(ref_aligned, coin_aligned)[0, 1]

                        # Calculate price ratio and z-score (reference in numerator)
                        ratio = ref_aligned / coin_aligned
                        ratio_mean = np.mean(ratio)
                        ratio_std = np.std(ratio)
                        current_ratio = ratio[-1]
                        zscore = (current_ratio - ratio_mean) / ratio_std if ratio_std > 0 else 0.0

                        # Calculate 24h and 7d ratio changes
                        change_24h = 0.0
                        change_7d = 0.0

                        # 24h ratio change (if we have at least 24 data points for 1h interval, or 6 for 4h)
                        if granularity == '1hour' and len(ratio) >= 24:
                            ratio_24h_ago = ratio[-24]
                            change_24h = ((current_ratio - ratio_24h_ago) / ratio_24h_ago) * 100
                        elif granularity == '4hour' and len(ratio) >= 6:
                            ratio_24h_ago = ratio[-6]
                            change_24h = ((current_ratio - ratio_24h_ago) / ratio_24h_ago) * 100

                        # 7d ratio change (if we have at least 168 data points for 1h, or 42 for 4h)
                        if granularity == '1hour' and len(ratio) >= 168:
                            ratio_7d_ago = ratio[-168]
                            change_7d = ((current_ratio - ratio_7d_ago) / ratio_7d_ago) * 100
                        elif granularity == '4hour' and len(ratio) >= 42:
                            ratio_7d_ago = ratio[-42]
                            change_7d = ((current_ratio - ratio_7d_ago) / ratio_7d_ago) * 100

                        # Test for cointegration
                        is_cointegrated = False
                        try:
                            from statsmodels.tsa.stattools import coint
                            import pandas as pd

                            price1_series = pd.Series(ref_aligned)
                            price2_series = pd.Series(coin_aligned)
                            coint_score, p_value, crit_values = coint(price1_series, price2_series)

                            # Consider cointegrated if p-value < 0.05
                            is_cointegrated = p_value < 0.05
                        except Exception as e:
                            # Silently fail cointegration test if error occurs
                            pass

                        # Include all pairs (no correlation filter)
                        results.append({
                            'coin1': reference_coin_upper,
                            'coin2': coin.upper(),
                            'correlation': correlation,
                            'is_cointegrated': is_cointegrated,
                            'zscore': zscore,
                            'current_ratio': current_ratio,
                            'change_24h': change_24h,
                            'change_7d': change_7d,
                        })

                        processed += 1
                        if processed % 20 == 0:
                            print(f"  Progress: {processed}/{len(scan_coins)} coins analyzed...")

                    except Exception as e:
                        print(f"⚠️  Error analyzing {coin}: {e}")
                        continue

                print(f"✅ Found {len(results)} pairs from database")

            # Convert to display items
            self._items = []
            for pair_data in results:  # Show all results, not just top 20
                # Determine signal based on z-score
                zscore = float(pair_data['zscore'])
                signal = "NEUTRAL"
                if zscore > 2.0:
                    signal = "SHORT"
                elif zscore < -2.0:
                    signal = "LONG"

                self._items.append({
                    'pair': f"{pair_data['coin1']}/{pair_data['coin2']}",
                    'correlation': float(pair_data['correlation']),
                    'is_cointegrated': pair_data.get('is_cointegrated', False),
                    'zscore': zscore,
                    'signal': signal,
                    'price': float(pair_data['current_ratio']),
                    'change_24h': float(pair_data.get('change_24h', 0.0)),
                    'change_7d': float(pair_data.get('change_7d', 0.0)),
                })

            # Sort items with current sort settings
            self._sort_items()

            print(f"📋 Displaying {len(self._items)} pairs")
            self.scanComplete.emit(len(self._items))

        except Exception as e:
            print(f"❌ Error scanning pairs: {e}")
            import traceback
            traceback.print_exc()
            self._items = []
            self.scanComplete.emit(0)

        self.endResetModel()

    def _sort_items(self):
        """Sort items based on current sort column and direction."""
        if not self._items:
            return

        reverse = not self._sort_ascending

        if self._sort_column == 'pair':
            self._items.sort(key=lambda x: x['pair'], reverse=reverse)
        elif self._sort_column == 'correlation':
            self._items.sort(key=lambda x: abs(x['correlation']), reverse=reverse)
        elif self._sort_column == 'is_cointegrated':
            # Sort cointegrated pairs first (True before False)
            self._items.sort(key=lambda x: x['is_cointegrated'], reverse=not reverse)
        elif self._sort_column == 'zscore':
            self._items.sort(key=lambda x: abs(x['zscore']), reverse=reverse)
        elif self._sort_column == 'signal':
            # Sort by signal priority: LONG/SHORT first, then NEUTRAL
            signal_priority = {'LONG': 0, 'SHORT': 0, 'NEUTRAL': 1}
            self._items.sort(key=lambda x: signal_priority.get(x['signal'], 2), reverse=reverse)
        elif self._sort_column == 'price':
            self._items.sort(key=lambda x: x['price'], reverse=reverse)
        elif self._sort_column == 'change_24h':
            self._items.sort(key=lambda x: x['change_24h'], reverse=reverse)
        elif self._sort_column == 'change_7d':
            self._items.sort(key=lambda x: x['change_7d'], reverse=reverse)

    @pyqtSlot(str)
    def sortBy(self, column: str):
        """Sort the table by the given column."""
        # Toggle direction if same column, otherwise default to descending
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = False

        self.beginResetModel()
        self._sort_items()
        self.endResetModel()

    @pyqtSlot(int)
    def addToWatchlist(self, index: int):
        """Add discovered pair to watchlist."""
        if 0 <= index < len(self._items):
            try:
                item = self._items[index]
                pair_parts = item['pair'].split('/')
                if len(pair_parts) == 2:
                    coin1 = pair_parts[0]
                    coin2 = pair_parts[1]

                    # Add to watchlist model to update UI
                    if self.watchlist_model:
                        self.watchlist_model.addPair(coin1, coin2)
                        print(f"✅ Added {coin1}/{coin2} to watchlist")
                    else:
                        print(f"⚠️ Watchlist model not available")

            except Exception as e:
                print(f"❌ Error adding to watchlist: {e}")
                import traceback
                traceback.print_exc()

    def _load_available_tokens(self):
        """Load all available perpetual tokens from Hyperliquid API."""
        try:
            # Get all symbols from Hyperliquid (these are perps only)
            symbols = self.api_client.get_all_symbols()
            # Filter out any empty or invalid symbols and sort
            self._available_tokens = sorted([s for s in symbols if s])
            self.availableTokensChanged.emit()
            print(f"Loaded {len(self._available_tokens)} perpetual tokens from Hyperliquid")
        except Exception as e:
            print(f"Error loading available tokens: {e}")
            # Fallback to common tokens
            self._available_tokens = ["BTC", "ETH", "SOL", "ARB", "AVAX", "DOGE"]
            self.availableTokensChanged.emit()

    @pyqtProperty('QVariantList', notify=availableTokensChanged)
    def availableTokens(self):
        """Return list of available perpetual tokens for QML."""
        return self._available_tokens

    @pyqtSlot()
    def refreshAvailableTokens(self):
        """Refresh the list of available tokens from Hyperliquid API."""
        self._load_available_tokens()
