"""QML bridge for Market Data - Rich market browser with stats."""
from PyQt6.QtCore import QObject, QAbstractListModel, Qt, pyqtSignal, pyqtSlot, QModelIndex, pyqtProperty
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api import HyperliquidClient


class MarketDataModel(QAbstractListModel):
    """Qt model for exposing market data to QML."""

    # Category mappings (manual categorization)
    CATEGORY_MAP = {
        # Layer 1
        'BTC': ['Layer 1'], 'ETH': ['Layer 1'], 'SOL': ['Layer 1'], 'AVAX': ['Layer 1'],
        'ADA': ['Layer 1'], 'DOT': ['Layer 1'], 'ATOM': ['Layer 1'], 'NEAR': ['Layer 1'],
        'APT': ['Layer 1'], 'SUI': ['Layer 1'], 'SEI': ['Layer 1'], 'INJ': ['Layer 1'],
        'TIA': ['Layer 1'], 'FTM': ['Layer 1'], 'ALGO': ['Layer 1'],

        # Layer 2
        'ARB': ['Layer 2'], 'OP': ['Layer 2'], 'MATIC': ['Layer 2'], 'IMX': ['Layer 2'],

        # DeFi
        'UNI': ['Defi'], 'AAVE': ['Defi'], 'CRV': ['Defi'], 'MKR': ['Defi'],
        'COMP': ['Defi'], 'SNX': ['Defi'], 'SUSHI': ['Defi'], 'YFI': ['Defi'],
        'PENDLE': ['Defi'], 'JUP': ['Defi'], 'DYDX': ['Defi'], 'GMX': ['Defi'],

        # AI
        'FET': ['AI'], 'AGIX': ['AI'], 'RNDR': ['AI'], 'TAO': ['AI'],
        'OCEAN': ['AI'], 'WLD': ['AI'], 'ARKM': ['AI'],

        # Gaming
        'AXS': ['Gaming'], 'SAND': ['Gaming'], 'MANA': ['Gaming'], 'ENJ': ['Gaming'],
        'GALA': ['Gaming'], 'MAGIC': ['Gaming'], 'PRIME': ['Gaming'],
        'BEAM': ['Gaming'], 'RON': ['Gaming'], 'PIXEL': ['Gaming'],

        # Meme
        'DOGE': ['Meme'], 'SHIB': ['Meme'], 'PEPE': ['Meme'], 'BONK': ['Meme'],
        'WIF': ['Meme'], 'FLOKI': ['Meme'], 'BRETT': ['Meme'], 'MEW': ['Meme'],
        'POPCAT': ['Meme'], 'MOODENG': ['Meme'], 'NEIRO': ['Meme'],
    }

    # Define roles for QML access
    SymbolRole = Qt.ItemDataRole.UserRole + 1
    LastPriceRole = Qt.ItemDataRole.UserRole + 2
    Change24hRole = Qt.ItemDataRole.UserRole + 3
    Change24hPctRole = Qt.ItemDataRole.UserRole + 4
    FundingRateRole = Qt.ItemDataRole.UserRole + 5
    VolumeRole = Qt.ItemDataRole.UserRole + 6
    OpenInterestRole = Qt.ItemDataRole.UserRole + 7
    LeverageRole = Qt.ItemDataRole.UserRole + 8
    CategoryRole = Qt.ItemDataRole.UserRole + 9
    IsTrendingRole = Qt.ItemDataRole.UserRole + 10

    # Signals
    dataLoaded = pyqtSignal()
    searchQueryChanged = pyqtSignal()
    selectedCategoryChanged = pyqtSignal()

    def __init__(self, api_client: HyperliquidClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._items: List[Dict[str, Any]] = []
        self._all_items: List[Dict[str, Any]] = []  # Unfiltered items
        self._search_query: str = ""
        self._selected_category: str = "All Coins"

        # DISABLED: Load initial data (causes rate limiting on startup)
        # Call loadMarketData() manually from QML when needed
        # self.loadMarketData()

    def rowCount(self, parent=QModelIndex()):
        """Return number of items."""
        return len(self._items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return data for given index and role."""
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]

        if role == self.SymbolRole:
            return item.get('symbol', '')
        elif role == self.LastPriceRole:
            return item.get('lastPrice', 0.0)
        elif role == self.Change24hRole:
            return item.get('change24h', 0.0)
        elif role == self.Change24hPctRole:
            return item.get('change24hPct', 0.0)
        elif role == self.FundingRateRole:
            return item.get('fundingRate', 0.0)
        elif role == self.VolumeRole:
            return item.get('volume', 0.0)
        elif role == self.OpenInterestRole:
            return item.get('openInterest', 0.0)
        elif role == self.LeverageRole:
            return item.get('leverage', '40x')
        elif role == self.CategoryRole:
            return item.get('category', 'PERP')
        elif role == self.IsTrendingRole:
            return item.get('isTrending', False)

        return None

    def roleNames(self):
        """Return mapping of role IDs to role names for QML."""
        return {
            self.SymbolRole: b'symbol',
            self.LastPriceRole: b'lastPrice',
            self.Change24hRole: b'change24h',
            self.Change24hPctRole: b'change24hPct',
            self.FundingRateRole: b'fundingRate',
            self.VolumeRole: b'volume',
            self.OpenInterestRole: b'openInterest',
            self.LeverageRole: b'leverage',
            self.CategoryRole: b'category',
            self.IsTrendingRole: b'isTrending',
        }

    @pyqtSlot()
    def loadMarketData(self):
        """Load market data from database cache - instant performance."""
        print("📊 Loading market data from database cache...")

        self.beginResetModel()

        try:
            from datetime import datetime, timedelta

            # Get ONE bulk API call for real-time data (fast)
            meta, contexts = self.api_client.get_perp_meta_and_contexts()

            if not meta or not contexts:
                print("⚠️  No market data available")
                self._all_items = []
                self.endResetModel()
                return

            universe = meta.get('universe', [])
            print(f"📊 Loading ALL {len(universe)} markets from cache...")

            items = []
            for idx, asset_meta in enumerate(universe):  # Load ALL markets
                try:
                    symbol = asset_meta.get('name', '')
                    if not symbol:
                        continue

                    # Get real-time context data (already loaded, no API call)
                    ctx = contexts[idx] if idx < len(contexts) else {}

                    mark_price = float(ctx.get('markPx', 0))
                    if mark_price == 0:
                        continue

                    # REAL funding rate (8h = hourly * 8)
                    funding_8h = float(ctx.get('funding', 0)) * 8

                    # REAL open interest
                    open_interest = float(ctx.get('openInterest', 0))

                    # Get 24h change from prevDayPx if available in context
                    prev_day_px = float(ctx.get('prevDayPx', 0))
                    day_volume = float(ctx.get('dayNtlVlm', 0))

                    if prev_day_px > 0:
                        change_24h = mark_price - prev_day_px
                        change_24h_pct = (change_24h / prev_day_px) * 100
                    else:
                        change_24h = 0.0
                        change_24h_pct = 0.0

                    volume_24h = day_volume

                    # Get categories for this symbol
                    categories = self.CATEGORY_MAP.get(symbol, [])

                    items.append({
                        'symbol': symbol,
                        'lastPrice': float(mark_price),
                        'change24h': float(change_24h),
                        'change24hPct': float(change_24h_pct),
                        'fundingRate': float(funding_8h),
                        'volume': float(volume_24h),
                        'openInterest': float(open_interest),
                        'leverage': '50x',
                        'category': 'PERP',
                        'categories': categories,  # Store all categories
                        'isTrending': False,
                    })

                except Exception as e:
                    print(f"⚠️  Error processing {symbol}: {e}")
                    continue

            # Sort by open interest
            items.sort(key=lambda x: x['openInterest'], reverse=True)

            # Mark top 10 as trending
            for i, item in enumerate(items[:10]):
                item['isTrending'] = True

            self._all_items = items
            self._apply_filters()

            print(f"✅ Loaded {len(self._all_items)} markets")
            self.dataLoaded.emit()

        except Exception as e:
            print(f"❌ Error loading market data: {e}")
            import traceback
            traceback.print_exc()
            self._items = []

        self.endResetModel()

    def _apply_filters(self):
        """Apply search and category filters to items."""
        filtered = self._all_items

        # Apply category filter
        if self._selected_category != "All Coins":
            print(f"🔍 Filtering by category: {self._selected_category}")

            if self._selected_category == "Trending":
                filtered = [item for item in filtered if item['isTrending']]
            elif self._selected_category == "Spot":
                filtered = [item for item in filtered if item['category'] == 'SPOT']
            else:
                # Filter by category tags (AI, DeFi, Gaming, Layer 1, Layer 2, Meme)
                filtered = [
                    item for item in filtered
                    if self._selected_category in item.get('categories', [])
                ]

        # Apply search filter
        if self._search_query:
            query_lower = self._search_query.lower()
            filtered = [
                item for item in filtered
                if query_lower in item['symbol'].lower()
            ]

        self._items = filtered
        print(f"📊 Filtered to {len(self._items)} markets")

    @pyqtSlot(str)
    def setSearchQuery(self, query: str):
        """Filter results by search query."""
        if self._search_query != query:
            self._search_query = query
            self.searchQueryChanged.emit()

            self.beginResetModel()
            self._apply_filters()
            self.endResetModel()

    @pyqtSlot(str)
    def setCategory(self, category: str):
        """Filter by category."""
        if self._selected_category != category:
            self._selected_category = category
            self.selectedCategoryChanged.emit()
            self.beginResetModel()
            self._apply_filters()
            self.endResetModel()

    @pyqtSlot()
    def loadFromDatabase(self):
        """Load simple coin list from database (no API calls)."""
        print("📊 Loading coin list from database...")

        self.beginResetModel()

        try:
            from src.database import DatabaseManager
            from datetime import datetime, timedelta

            db = DatabaseManager()

            with db.get_session() as session:
                # Get all unique coin_ids from OHLCV data
                from sqlalchemy import distinct
                from src.database.ohlcv_models import OHLCVData

                coins = session.query(distinct(OHLCVData.coin_id)).all()
                coin_ids = sorted([c[0] for c in coins if c[0]])

                items = []
                for symbol in coin_ids:
                    # Get latest price from most recent candle
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=1)

                    latest = session.query(OHLCVData).filter(
                        OHLCVData.coin_id == symbol,
                        OHLCVData.granularity == '1hour',
                        OHLCVData.timestamp >= start_date
                    ).order_by(OHLCVData.timestamp.desc()).first()

                    if latest:
                        # Get price from 24h ago for change calculation
                        price_24h_ago = session.query(OHLCVData).filter(
                            OHLCVData.coin_id == symbol,
                            OHLCVData.granularity == '1hour',
                            OHLCVData.timestamp >= start_date
                        ).order_by(OHLCVData.timestamp.asc()).first()

                        change_24h_pct = 0.0
                        if price_24h_ago and price_24h_ago.close > 0:
                            change_24h_pct = ((latest.close - price_24h_ago.close) / price_24h_ago.close) * 100

                        items.append({
                            'symbol': symbol,
                            'lastPrice': float(latest.close),
                            'change24h': 0.0,
                            'change24hPct': float(change_24h_pct),
                            'fundingRate': 0.0,
                            'volume': float(latest.volume),
                            'openInterest': 0.0,
                            'leverage': '50x',
                            'category': 'PERP',
                            'categories': self.CATEGORY_MAP.get(symbol, []),
                            'isTrending': False,
                        })

                self._all_items = items
                self._apply_filters()

                print(f"✅ Loaded {len(self._all_items)} coins from database")
                self.dataLoaded.emit()

        except Exception as e:
            print(f"❌ Error loading from database: {e}")
            import traceback
            traceback.print_exc()
            self._items = []

        self.endResetModel()

    @pyqtProperty(str, notify=searchQueryChanged)
    def searchQuery(self):
        """Return current search query."""
        return self._search_query

    @pyqtProperty(str, notify=selectedCategoryChanged)
    def selectedCategory(self):
        """Return current selected category."""
        return self._selected_category
