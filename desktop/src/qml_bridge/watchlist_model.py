"""QML bridge for Watchlist data."""
from PyQt6.QtCore import QObject, QAbstractTableModel, Qt, pyqtSignal, pyqtSlot, QModelIndex
from typing import List, Dict, Any
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.database import DatabaseManager
from src.api import HyperliquidClient

# Watchlist storage file
WATCHLIST_FILE = Path.home() / ".hedge" / "watchlist.json"


class WatchlistModel(QAbstractTableModel):
    """Qt model for exposing watchlist data to QML."""

    def __init__(self, db_manager: DatabaseManager, api_client: HyperliquidClient, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.api_client = api_client
        self._items: List[Dict[str, Any]] = []
        self._watchlist_pairs: List[tuple[str, str]] = []  # Store (coin1, coin2) tuples
        self._sort_column = 'zscore'  # Default sort by z-score
        self._sort_ascending = False  # Descending by default

        # Load saved pairs from database/config
        self._load_saved_pairs()
        self.refresh()

    def rowCount(self, parent=QModelIndex()):
        """Return number of rows."""
        return len(self._items)

    def columnCount(self, parent=QModelIndex()):
        """Return number of columns."""
        return 8  # Pair, Ratio, Z-Score, Correlation, 24h Change, 7d Change, Signal, Actions

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
            return item.get('ratio', 0.0)
        elif column == 2:
            return item.get('zscore', 0.0)
        elif column == 3:
            return item.get('correlation', 0.0)
        elif column == 4:
            return item.get('change_24h', 0.0)
        elif column == 5:
            return item.get('change_7d', 0.0)
        elif column == 6:
            return item.get('signal', 'NEUTRAL')
        elif column == 7:
            return ""  # Actions column (rendered in QML)

        return None

    def roleNames(self):
        """Return mapping of role IDs to role names for QML."""
        return {
            Qt.ItemDataRole.DisplayRole: b'display',
        }

    @pyqtSlot()
    def refresh(self):
        """Refresh watchlist data with live calculations."""
        self.beginResetModel()

        try:
            self._items = []
            from datetime import datetime, timedelta
            from src.services.basket_calculator import BasketCalculator

            calculator = BasketCalculator(self.db)
            days = 60
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            granularity = '1hour'

            # Calculate live data for each watchlist pair
            for pair in self._watchlist_pairs:
                try:
                    # Detect if pair is basket or single coins
                    # Baskets are stored as tuple of tuples/lists
                    # Single coins are stored as tuple of strings
                    numerator = pair[0]
                    denominator = pair[1]

                    # Check if numerator/denominator are strings or collections
                    is_numerator_basket = isinstance(numerator, (tuple, list))
                    is_denominator_basket = isinstance(denominator, (tuple, list))

                    with self.db.get_session() as session:
                        # Get numerator prices
                        if is_numerator_basket:
                            # Create temp basket for numerator
                            num_basket_id = calculator.create_basket_from_coins(
                                session, f"temp_num_{datetime.now().timestamp()}", list(numerator)
                            )
                            num_df = calculator.calculate_basket_price(
                                session, num_basket_id, start_date, end_date, granularity
                            )
                        else:
                            # Single coin
                            coin1_data = self.db.get_ohlcv_data(
                                session, coin_id=numerator.upper(),
                                start_date=start_date, end_date=end_date, granularity=granularity
                            )
                            if not coin1_data:
                                continue
                            num_df = pd.DataFrame([{'timestamp': c.timestamp, 'close': c.close} for c in coin1_data])
                            num_df.set_index('timestamp', inplace=True)

                        # Get denominator prices
                        if is_denominator_basket:
                            # Create temp basket for denominator
                            denom_basket_id = calculator.create_basket_from_coins(
                                session, f"temp_denom_{datetime.now().timestamp()}", list(denominator)
                            )
                            denom_df = calculator.calculate_basket_price(
                                session, denom_basket_id, start_date, end_date, granularity
                            )
                        else:
                            # Single coin
                            coin2_data = self.db.get_ohlcv_data(
                                session, coin_id=denominator.upper(),
                                start_date=start_date, end_date=end_date, granularity=granularity
                            )
                            if not coin2_data:
                                continue
                            denom_df = pd.DataFrame([{'timestamp': c.timestamp, 'close': c.close} for c in coin2_data])
                            denom_df.set_index('timestamp', inplace=True)

                        if num_df is None or denom_df is None:
                            continue

                        # Align timestamps
                        df_aligned = num_df.join(denom_df, how='inner', lsuffix='_num', rsuffix='_denom')

                        if len(df_aligned) < 10:
                            continue

                        # Calculate ratio
                        ratio = df_aligned['close_num'] / df_aligned['close_denom']

                        # Calculate correlation
                        correlation = df_aligned['close_num'].corr(df_aligned['close_denom'])

                        # Calculate z-score
                        ratio_mean = ratio.mean()
                        ratio_std = ratio.std()
                        current_ratio = ratio.iloc[-1]
                        zscore = (current_ratio - ratio_mean) / ratio_std if ratio_std > 0 else 0

                        # Normalized ratio
                        normalized_ratio = current_ratio / ratio_mean if ratio_mean > 0 else 0

                        # Calculate 24h and 7d ratio changes
                        change_24h = 0.0
                        change_7d = 0.0

                        if len(ratio) >= 24:
                            ratio_24h_ago = ratio.iloc[-24]
                            change_24h = ((current_ratio - ratio_24h_ago) / ratio_24h_ago) * 100

                        if len(ratio) >= 168:
                            ratio_7d_ago = ratio.iloc[-168]
                            change_7d = ((current_ratio - ratio_7d_ago) / ratio_7d_ago) * 100

                        # Determine signal
                        signal = "NEUTRAL"
                        if zscore > 2.0:
                            signal = "SHORT"
                        elif zscore < -2.0:
                            signal = "LONG"

                        # Format pair display
                        num_display = '+'.join(numerator) if is_numerator_basket else numerator.upper()
                        denom_display = '+'.join(denominator) if is_denominator_basket else denominator.upper()
                        pair_display = f"{num_display}/{denom_display}"

                        self._items.append({
                            'pair': pair_display,
                            'ratio': float(normalized_ratio),
                            'zscore': float(zscore),
                            'correlation': float(correlation),
                            'change_24h': float(change_24h),
                            'change_7d': float(change_7d),
                            'signal': signal,
                        })

                except Exception as e:
                    print(f"Error calculating data for pair: {e}")
                    continue

        except Exception as e:
            print(f"Error loading watchlist: {e}")

        # Sort items
        self._sort_items()

        self.endResetModel()

    def _sort_items(self):
        """Sort items based on current sort column and direction."""
        if not self._items:
            return

        reverse = not self._sort_ascending

        if self._sort_column == 'pair':
            self._items.sort(key=lambda x: x['pair'], reverse=reverse)
        elif self._sort_column == 'ratio':
            self._items.sort(key=lambda x: x['ratio'], reverse=reverse)
        elif self._sort_column == 'ratio_change':
            self._items.sort(key=lambda x: x['ratio_change'], reverse=reverse)
        elif self._sort_column == 'zscore':
            self._items.sort(key=lambda x: abs(x['zscore']), reverse=reverse)
        elif self._sort_column == 'correlation':
            self._items.sort(key=lambda x: x['correlation'], reverse=reverse)

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

    @pyqtSlot(str, str)
    def addPair(self, coin1: str, coin2: str):
        """Add a pair to the watchlist (backwards compatibility)."""
        pair = (coin1.upper(), coin2.upper())
        if pair not in self._watchlist_pairs:
            self._watchlist_pairs.append(pair)
            self._save_pairs()
            self.refresh()

    @pyqtSlot('QVariantList', 'QVariantList')
    def addBasketPair(self, numerator_coins: list, denominator_coins: list):
        """Add a basket pair to the watchlist."""
        # Store as tuple of lists for baskets
        pair = (tuple([c.upper() for c in numerator_coins]), tuple([c.upper() for c in denominator_coins]))
        if pair not in self._watchlist_pairs:
            self._watchlist_pairs.append(pair)
            self._save_pairs()
            self.refresh()

    @pyqtSlot(int)
    def remove(self, index: int):
        """Remove item at index."""
        if 0 <= index < len(self._watchlist_pairs):
            self.beginRemoveRows(QModelIndex(), index, index)
            self._watchlist_pairs.pop(index)
            self._items.pop(index)
            self._save_pairs()
            self.endResetModel()

    def _load_saved_pairs(self):
        """Load saved watchlist pairs from JSON file."""
        try:
            if WATCHLIST_FILE.exists():
                with open(WATCHLIST_FILE, 'r') as f:
                    data = json.load(f)
                    self._watchlist_pairs = [tuple(pair) for pair in data.get('pairs', [])]
                    print(f"📋 Loaded {len(self._watchlist_pairs)} pairs from watchlist")
        except Exception as e:
            print(f"⚠️ Error loading watchlist: {e}")
            self._watchlist_pairs = []

    def _save_pairs(self):
        """Save watchlist pairs to JSON file."""
        try:
            # Create directory if it doesn't exist
            WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Save pairs as list of lists
            data = {
                'pairs': [list(pair) for pair in self._watchlist_pairs]
            }

            with open(WATCHLIST_FILE, 'w') as f:
                json.dump(data, f, indent=2)

            print(f"💾 Saved {len(self._watchlist_pairs)} pairs to watchlist")
        except Exception as e:
            print(f"❌ Error saving watchlist: {e}")

