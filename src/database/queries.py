"""Database queries and management."""
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, desc, and_, or_, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

from .models import Base, Coin, TradingPair, HistoricalData, Analysis, Watchlist, MarketStats
from .ohlcv_models import OHLCVData, ExplorerWatchlist, ExplorerMetricsCache, DataUpdateLog
from .write_queue import SQLiteWriteQueue

load_dotenv()


class DatabaseManager:
    """Manages database operations."""

    def __init__(self, db_path: Optional[str] = None, use_write_queue: bool = True):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
            use_write_queue: If True, use dedicated write queue for concurrent writes
        """
        if db_path is None:
            db_path = os.getenv('DATABASE_PATH', 'data/pairs.db')

        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self.use_write_queue = use_write_queue

        # Use SQLite with WAL mode for concurrent write performance
        self.engine = create_engine(
            f'sqlite:///{db_path}',
            connect_args={
                'timeout': 60,  # 60 second timeout for locks
                'check_same_thread': False  # Allow multi-threaded access
            },
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
        )

        # Enable SQLite performance optimizations for concurrent reads/writes
        with self.engine.connect() as conn:
            conn.execute(text('PRAGMA journal_mode=WAL'))  # Write-Ahead Logging
            conn.execute(text('PRAGMA synchronous=NORMAL'))  # Faster writes (fsync on checkpoints only)
            conn.execute(text('PRAGMA temp_store=MEMORY'))  # Temp tables/indexes in RAM
            conn.execute(text('PRAGMA mmap_size=30000000000'))  # 30GB memory-mapped I/O (fewer syscalls)
            conn.execute(text('PRAGMA busy_timeout=60000'))  # 60 second busy timeout
            conn.commit()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Initialize write queue for high-concurrency scenarios
        self.write_queue: Optional[SQLiteWriteQueue] = None
        if use_write_queue:
            self.write_queue = SQLiteWriteQueue(db_path)
            self.write_queue.start()

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.Session()

    # Coin operations
    def upsert_coin(self, session: Session, coin_data: Dict[str, Any]) -> Coin:
        """Insert or update coin information."""
        coin = session.query(Coin).filter_by(id=coin_data['id']).first()

        if coin:
            # Update existing
            for key, value in coin_data.items():
                setattr(coin, key, value)
            coin.last_updated = datetime.now()
        else:
            # Create new
            coin = Coin(**coin_data)
            session.add(coin)

        return coin

    def get_coin(self, session: Session, coin_id: str) -> Optional[Coin]:
        """Get coin by ID."""
        return session.query(Coin).filter_by(id=coin_id).first()

    def get_coins_by_market_cap(
        self,
        session: Session,
        min_market_cap: float = 0,
        limit: int = 100
    ) -> List[Coin]:
        """Get coins filtered by market cap."""
        return session.query(Coin)\
            .filter(Coin.market_cap >= min_market_cap)\
            .order_by(desc(Coin.market_cap))\
            .limit(limit)\
            .all()

    # Trading pair operations
    def create_pair(
        self,
        session: Session,
        base_coin_id: str,
        quote_coin_id: str,
        discovery_method: str = 'manual',
        category: Optional[str] = None
    ) -> TradingPair:
        """Create a new trading pair."""
        # Check if pair already exists
        existing = session.query(TradingPair).filter_by(
            base_coin_id=base_coin_id,
            quote_coin_id=quote_coin_id
        ).first()

        if existing:
            return existing

        pair = TradingPair(
            base_coin_id=base_coin_id,
            quote_coin_id=quote_coin_id,
            discovery_method=discovery_method,
            category=category
        )
        session.add(pair)
        return pair

    def get_pair(
        self,
        session: Session,
        base_coin_id: str,
        quote_coin_id: str
    ) -> Optional[TradingPair]:
        """Get trading pair by coin IDs."""
        return session.query(TradingPair).filter_by(
            base_coin_id=base_coin_id,
            quote_coin_id=quote_coin_id
        ).first()

    def get_all_pairs(
        self,
        session: Session,
        category: Optional[str] = None
    ) -> List[TradingPair]:
        """Get all trading pairs, optionally filtered by category."""
        query = session.query(TradingPair)
        if category:
            query = query.filter_by(category=category)
        return query.all()

    # Historical data operations
    def add_historical_data(
        self,
        session: Session,
        coin_id: str,
        timestamp: datetime,
        price: float,
        market_cap: Optional[float] = None,
        volume: Optional[float] = None
    ) -> HistoricalData:
        """Add historical data point."""
        # Check if data point exists
        existing = session.query(HistoricalData).filter_by(
            coin_id=coin_id,
            timestamp=timestamp
        ).first()

        if existing:
            existing.price = price
            existing.market_cap = market_cap
            existing.volume = volume
            return existing

        data = HistoricalData(
            coin_id=coin_id,
            timestamp=timestamp,
            price=price,
            market_cap=market_cap,
            volume=volume
        )
        session.add(data)
        return data

    def get_historical_data(
        self,
        session: Session,
        coin_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[HistoricalData]:
        """Get historical data for a coin within date range."""
        return session.query(HistoricalData)\
            .filter(
                HistoricalData.coin_id == coin_id,
                HistoricalData.timestamp >= start_date,
                HistoricalData.timestamp <= end_date
            )\
            .order_by(HistoricalData.timestamp)\
            .all()

    # Analysis operations
    def save_analysis(self, session: Session, analysis_data: Dict[str, Any]) -> Analysis:
        """Save analysis results for a pair."""
        analysis = Analysis(**analysis_data)
        session.add(analysis)
        return analysis

    def get_latest_analysis(
        self,
        session: Session,
        pair_id: int
    ) -> Optional[Analysis]:
        """Get most recent analysis for a pair."""
        return session.query(Analysis)\
            .filter_by(pair_id=pair_id)\
            .order_by(desc(Analysis.analyzed_at))\
            .first()

    def get_analyses(
        self,
        session: Session,
        pair_id: Optional[int] = None,
        min_correlation: Optional[float] = None,
        min_quality: Optional[float] = None,
        limit: int = 100
    ) -> List[Analysis]:
        """Get analyses with optional filters."""
        query = session.query(Analysis)

        if pair_id:
            query = query.filter_by(pair_id=pair_id)
        if min_correlation:
            query = query.filter(Analysis.correlation_pearson >= min_correlation)
        if min_quality:
            query = query.filter(Analysis.quality_score >= min_quality)

        return query.order_by(desc(Analysis.analyzed_at)).limit(limit).all()

    # Watchlist operations
    def add_to_watchlist(
        self,
        session: Session,
        pair_id: int,
        notes: Optional[str] = None,
        tags: Optional[str] = None,
        priority: int = 0
    ) -> Watchlist:
        """Add pair to watchlist."""
        # Check if already in watchlist
        existing = session.query(Watchlist)\
            .filter_by(pair_id=pair_id, is_active=True)\
            .first()

        if existing:
            return existing

        watchlist_item = Watchlist(
            pair_id=pair_id,
            notes=notes,
            tags=tags,
            priority=priority
        )
        session.add(watchlist_item)
        return watchlist_item

    def get_watchlist(
        self,
        session: Session,
        active_only: bool = True
    ) -> List[Watchlist]:
        """Get watchlist items."""
        query = session.query(Watchlist)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(desc(Watchlist.priority), desc(Watchlist.added_at)).all()

    def remove_from_watchlist(self, session: Session, watchlist_id: int) -> None:
        """Remove item from watchlist (soft delete)."""
        item = session.query(Watchlist).filter_by(id=watchlist_id).first()
        if item:
            item.is_active = False

    # OHLCV Data operations
    def upsert_ohlcv_data(
        self,
        session: Session,
        coin_id: str,
        timestamp: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: Optional[float] = None,
        market_cap: Optional[float] = None,
        granularity: str = '4hour'
    ) -> OHLCVData:
        """Insert or update OHLCV candle data with granularity support."""
        candle = session.query(OHLCVData).filter_by(
            coin_id=coin_id,
            timestamp=timestamp,
            granularity=granularity
        ).first()

        if candle:
            # Update existing
            candle.open = open_price
            candle.high = high
            candle.low = low
            candle.close = close
            candle.volume = volume
            candle.market_cap = market_cap
        else:
            # Create new
            candle = OHLCVData(
                coin_id=coin_id,
                timestamp=timestamp,
                granularity=granularity,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                market_cap=market_cap
            )
            session.add(candle)

        return candle

    def batch_upsert_ohlcv_data(
        self,
        session: Session,
        coin_id: str,
        candles: List[Dict[str, Any]],
        granularity: str = '1hour'
    ) -> int:
        """
        Batch insert/update OHLCV candle data using efficient INSERT OR REPLACE.

        Args:
            session: Database session
            coin_id: Coin identifier (e.g., 'BTC', 'ETH')
            candles: List of candle dicts with keys: timestamp, open, high, low, close, volume
            granularity: Candle granularity ('5min', '1hour', '4hour')

        Returns:
            Number of candles inserted/updated
        """
        if not candles:
            return 0

        # Use write queue for concurrent writes if available
        if self.write_queue and self.use_write_queue:
            # Prepare batch data for write queue
            sql = """
                INSERT OR REPLACE INTO ohlcv_data
                (coin_id, timestamp, granularity, open, high, low, close, volume, market_cap, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            now = datetime.now()
            params_list = [
                (
                    coin_id,
                    candle['timestamp'],
                    granularity,
                    candle['open'],
                    candle['high'],
                    candle['low'],
                    candle['close'],
                    candle.get('volume', 0.0),
                    candle.get('market_cap'),
                    now
                )
                for candle in candles
            ]

            # Submit to write queue (non-blocking)
            self.write_queue.submit_many(sql, params_list)
            return len(params_list)

        else:
            # Fallback to direct session execution (old behavior)
            from sqlalchemy import text

            # Prepare batch insert statement
            stmt = text("""
                INSERT OR REPLACE INTO ohlcv_data
                (coin_id, timestamp, granularity, open, high, low, close, volume, market_cap, created_at)
                VALUES
                (:coin_id, :timestamp, :granularity, :open, :high, :low, :close, :volume, :market_cap, :created_at)
            """)

            # Prepare data for batch insert
            batch_data = []
            for candle in candles:
                batch_data.append({
                    'coin_id': coin_id,
                    'timestamp': candle['timestamp'],
                    'granularity': granularity,
                    'open': candle['open'],
                    'high': candle['high'],
                    'low': candle['low'],
                    'close': candle['close'],
                    'volume': candle.get('volume', 0.0),
                    'market_cap': candle.get('market_cap'),
                    'created_at': datetime.now()
                })

            # Execute batch insert
            session.execute(stmt, batch_data)

            return len(batch_data)

    def get_ohlcv_data(
        self,
        session: Session,
        coin_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
        granularity: Optional[str] = None
    ) -> List[OHLCVData]:
        """Get OHLCV data for a coin with optional granularity filter."""
        query = session.query(OHLCVData).filter_by(coin_id=coin_id)

        if granularity:
            query = query.filter_by(granularity=granularity)

        if start_date:
            query = query.filter(OHLCVData.timestamp >= start_date)
        if end_date:
            query = query.filter(OHLCVData.timestamp <= end_date)

        query = query.order_by(OHLCVData.timestamp)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_latest_ohlcv(
        self,
        session: Session,
        coin_id: str
    ) -> Optional[OHLCVData]:
        """Get most recent OHLCV candle for a coin."""
        return session.query(OHLCVData)\
            .filter_by(coin_id=coin_id)\
            .order_by(desc(OHLCVData.timestamp))\
            .first()

    def get_latest_timestamp(
        self,
        session: Session,
        coin_id: str,
        granularity: str
    ) -> Optional[datetime]:
        """
        Get latest candle timestamp for a specific coin and granularity.
        Used for incremental updates to avoid re-fetching existing data.

        Args:
            session: Database session
            coin_id: Coin identifier (e.g., 'BTC')
            granularity: Candle granularity ('5min', '1hour', '4hour')

        Returns:
            Latest timestamp or None if no data exists
        """
        from sqlalchemy import func
        latest = session.query(func.max(OHLCVData.timestamp))\
            .filter_by(coin_id=coin_id, granularity=granularity)\
            .scalar()
        return latest

    def get_candles_formatted(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get OHLCV candles from database in same format as API client.
        Drop-in replacement for HyperliquidClient.get_candles_formatted().

        Args:
            symbol: Trading symbol (e.g., 'BTC', 'ETH')
            interval: Candle interval ('1h', '4h', '1d', etc.)
            limit: Max number of candles to return

        Returns:
            List of dicts with: timestamp, open, high, low, close, volume
        """
        # Map interval strings to database granularity names
        interval_map = {
            '5m': '5min',
            '15m': '15min',
            '1h': '1hour',
            '4h': '4hour',
            '1d': '1day',
            '1w': '1week'
        }
        granularity = interval_map.get(interval, '1hour')

        with self.get_session() as session:
            ohlcv_data = self.get_ohlcv_data(
                session,
                coin_id=symbol.upper(),
                granularity=granularity,
                limit=limit
            )

            # Format to match API client output
            formatted = []
            for candle in ohlcv_data:
                formatted.append({
                    'timestamp': candle.timestamp,
                    'open': float(candle.open),
                    'high': float(candle.high),
                    'low': float(candle.low),
                    'close': float(candle.close),
                    'volume': float(candle.volume) if candle.volume else 0.0
                })

            return formatted

    def prune_old_ohlcv_data(self, session: Session) -> Dict[str, int]:
        """
        Prune old OHLCV data to maintain rolling windows for each granularity.

        Retention policy:
        - 5min candles: Keep last 1 day only (scalping)
        - 1hour candles: Keep last 7 days only (intraday)
        - 4hour candles: Keep last 90 days only (swing)

        Returns:
            Dict with count of deleted records per granularity
        """
        from datetime import datetime, timedelta

        now = datetime.now()
        deleted_counts = {}

        # Prune 5min data older than 1 day
        cutoff_5min = now - timedelta(days=1)
        deleted_5min = session.query(OHLCVData).filter(
            OHLCVData.granularity == '5min',
            OHLCVData.timestamp < cutoff_5min
        ).delete()
        deleted_counts['5min'] = deleted_5min

        # Prune 1hour data older than 7 days
        cutoff_1hour = now - timedelta(days=7)
        deleted_1hour = session.query(OHLCVData).filter(
            OHLCVData.granularity == '1hour',
            OHLCVData.timestamp < cutoff_1hour
        ).delete()
        deleted_counts['1hour'] = deleted_1hour

        # Prune 4hour data older than 90 days
        cutoff_4hour = now - timedelta(days=90)
        deleted_4hour = session.query(OHLCVData).filter(
            OHLCVData.granularity == '4hour',
            OHLCVData.timestamp < cutoff_4hour
        ).delete()
        deleted_counts['4hour'] = deleted_4hour

        session.commit()

        return deleted_counts

    # Explorer Watchlist operations
    def add_to_explorer_watchlist(
        self,
        session: Session,
        coin_id: str,
        notes: Optional[str] = None
    ) -> ExplorerWatchlist:
        """Add coin to explorer watchlist."""
        # Check if already exists
        existing = session.query(ExplorerWatchlist)\
            .filter_by(coin_id=coin_id)\
            .first()

        if existing:
            existing.is_active = True
            return existing

        # Get max position
        max_pos = session.query(ExplorerWatchlist).count()

        watchlist_item = ExplorerWatchlist(
            coin_id=coin_id,
            notes=notes,
            position=max_pos
        )
        session.add(watchlist_item)
        return watchlist_item

    def get_explorer_watchlist(
        self,
        session: Session,
        active_only: bool = True
    ) -> List[ExplorerWatchlist]:
        """Get explorer watchlist coins."""
        query = session.query(ExplorerWatchlist)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(ExplorerWatchlist.position).all()

    def remove_from_explorer_watchlist(
        self,
        session: Session,
        coin_id: str
    ) -> None:
        """Remove coin from explorer watchlist (soft delete)."""
        item = session.query(ExplorerWatchlist)\
            .filter_by(coin_id=coin_id)\
            .first()
        if item:
            item.is_active = False

    def reorder_explorer_watchlist(
        self,
        session: Session,
        coin_id: str,
        new_position: int
    ) -> None:
        """Update position of coin in watchlist."""
        item = session.query(ExplorerWatchlist)\
            .filter_by(coin_id=coin_id)\
            .first()
        if item:
            item.position = new_position

    # Explorer Metrics Cache operations
    def upsert_explorer_metrics(
        self,
        session: Session,
        coin_id: str,
        lookback_days: int,
        metrics: Dict[str, Any],
        reference_coin_id: Optional[str] = None
    ) -> ExplorerMetricsCache:
        """Insert or update cached metrics."""
        cached = session.query(ExplorerMetricsCache).filter_by(
            coin_id=coin_id,
            reference_coin_id=reference_coin_id,
            lookback_days=lookback_days
        ).first()

        if cached:
            # Update existing
            for key, value in metrics.items():
                if hasattr(cached, key):
                    setattr(cached, key, value)
            cached.calculated_at = datetime.now()
        else:
            # Create new
            cached = ExplorerMetricsCache(
                coin_id=coin_id,
                reference_coin_id=reference_coin_id,
                lookback_days=lookback_days,
                **metrics
            )
            session.add(cached)

        return cached

    def get_explorer_metrics(
        self,
        session: Session,
        coin_id: str,
        lookback_days: int,
        reference_coin_id: Optional[str] = None
    ) -> Optional[ExplorerMetricsCache]:
        """Get cached metrics for a coin."""
        return session.query(ExplorerMetricsCache).filter_by(
            coin_id=coin_id,
            reference_coin_id=reference_coin_id,
            lookback_days=lookback_days
        ).first()

    def get_explorer_metrics_bulk(
        self,
        session: Session,
        coin_ids: List[str],
        lookback_days: int,
        reference_coin_id: Optional[str] = None
    ) -> List[ExplorerMetricsCache]:
        """Get cached metrics for multiple coins."""
        return session.query(ExplorerMetricsCache).filter(
            ExplorerMetricsCache.coin_id.in_(coin_ids),
            ExplorerMetricsCache.reference_coin_id == reference_coin_id,
            ExplorerMetricsCache.lookback_days == lookback_days
        ).all()

    # Data Update Log operations
    def create_update_log(
        self,
        session: Session,
        update_type: str
    ) -> DataUpdateLog:
        """Create a new update log entry."""
        log = DataUpdateLog(
            update_type=update_type,
            started_at=datetime.now(),
            status='running'
        )
        session.add(log)
        session.flush()  # Get ID immediately
        return log

    def complete_update_log(
        self,
        session: Session,
        log_id: int,
        coins_updated: int,
        coins_failed: int,
        error_message: Optional[str] = None
    ) -> None:
        """Mark update log as completed."""
        log = session.query(DataUpdateLog).filter_by(id=log_id).first()
        if log:
            log.completed_at = datetime.now()
            log.coins_updated = coins_updated
            log.coins_failed = coins_failed
            log.status = 'failed' if error_message else 'completed'
            log.error_message = error_message

    def get_latest_update_log(
        self,
        session: Session,
        update_type: Optional[str] = None
    ) -> Optional[DataUpdateLog]:
        """Get most recent update log."""
        query = session.query(DataUpdateLog)
        if update_type:
            query = query.filter_by(update_type=update_type)
        return query.order_by(desc(DataUpdateLog.started_at)).first()

    # ============================================================================
    # Tag Methods
    # ============================================================================

    def create_tag(
        self,
        session: Session,
        name: str,
        color: Optional[str] = None,
        description: Optional[str] = None
    ):
        """Create a new tag."""
        from .ohlcv_models import Tag

        tag = Tag(
            name=name,
            color=color,
            description=description
        )
        session.add(tag)
        return tag

    def get_all_tags(self, session: Session):
        """Get all tags."""
        from .ohlcv_models import Tag
        return session.query(Tag).order_by(Tag.name).all()

    def get_tag_by_name(self, session: Session, name: str):
        """Get tag by name."""
        from .ohlcv_models import Tag
        return session.query(Tag).filter_by(name=name).first()

    def delete_tag(self, session: Session, tag_id: int):
        """Delete a tag and its associations."""
        from .ohlcv_models import Tag, CoinTag

        # Delete all coin-tag associations
        session.query(CoinTag).filter_by(tag_id=tag_id).delete()

        # Delete the tag
        session.query(Tag).filter_by(id=tag_id).delete()

    def add_tag_to_coin(self, session: Session, coin_id: str, tag_id: int):
        """Add a tag to a coin."""
        from .ohlcv_models import CoinTag

        # Check if already exists
        existing = session.query(CoinTag).filter_by(
            coin_id=coin_id,
            tag_id=tag_id
        ).first()

        if not existing:
            coin_tag = CoinTag(coin_id=coin_id, tag_id=tag_id)
            session.add(coin_tag)
            return coin_tag
        return existing

    def remove_tag_from_coin(self, session: Session, coin_id: str, tag_id: int):
        """Remove a tag from a coin."""
        from .ohlcv_models import CoinTag

        session.query(CoinTag).filter_by(
            coin_id=coin_id,
            tag_id=tag_id
        ).delete()

    def get_tags_for_coin(self, session: Session, coin_id: str):
        """Get all tags for a coin."""
        from .ohlcv_models import Tag, CoinTag

        return session.query(Tag).join(
            CoinTag,
            Tag.id == CoinTag.tag_id
        ).filter(
            CoinTag.coin_id == coin_id
        ).order_by(Tag.name).all()

    def get_coins_by_tag(self, session: Session, tag_id: int):
        """Get all coins with a specific tag."""
        from .ohlcv_models import CoinTag

        coin_tags = session.query(CoinTag).filter_by(tag_id=tag_id).all()
        return [ct.coin_id for ct in coin_tags]

    # ========== Market Stats & Funding Rate Methods ==========

    def upsert_market_stats(
        self,
        session: Session,
        coin_id: str,
        timestamp: datetime,
        stats: Dict[str, Any]
    ):
        """Insert or update market stats snapshot."""
        from .ohlcv_models import MarketStatsHistory

        existing = session.query(MarketStatsHistory).filter_by(
            coin_id=coin_id,
            timestamp=timestamp
        ).first()

        if existing:
            for key, value in stats.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
        else:
            record = MarketStatsHistory(
                coin_id=coin_id,
                timestamp=timestamp,
                **stats
            )
            session.add(record)

    def get_market_stats_history(
        self,
        session: Session,
        coin_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """Get market stats history for a coin."""
        from .ohlcv_models import MarketStatsHistory

        query = session.query(MarketStatsHistory).filter_by(coin_id=coin_id)

        if start_date:
            query = query.filter(MarketStatsHistory.timestamp >= start_date)
        if end_date:
            query = query.filter(MarketStatsHistory.timestamp <= end_date)

        return query.order_by(MarketStatsHistory.timestamp).all()

    def upsert_funding_rate(
        self,
        session: Session,
        coin_id: str,
        timestamp: datetime,
        funding_data: Dict[str, Any]
    ):
        """Insert or update funding rate data."""
        from .ohlcv_models import FundingRateHistory

        existing = session.query(FundingRateHistory).filter_by(
            coin_id=coin_id,
            timestamp=timestamp
        ).first()

        if existing:
            for key, value in funding_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
        else:
            record = FundingRateHistory(
                coin_id=coin_id,
                timestamp=timestamp,
                **funding_data
            )
            session.add(record)

    def get_funding_rate_history(
        self,
        session: Session,
        coin_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """Get funding rate history for a coin."""
        from .ohlcv_models import FundingRateHistory

        query = session.query(FundingRateHistory).filter_by(coin_id=coin_id)

        if start_date:
            query = query.filter(FundingRateHistory.timestamp >= start_date)
        if end_date:
            query = query.filter(FundingRateHistory.timestamp <= end_date)

        return query.order_by(FundingRateHistory.timestamp).all()

    # Market Stats operations
    def upsert_market_stats(self, session: Session, stats_data: Dict[str, Any]) -> MarketStats:
        """Insert or update market statistics for a coin at a specific time."""
        stats = session.query(MarketStats).filter_by(
            coin_id=stats_data['coin_id'],
            timestamp=stats_data['timestamp']
        ).first()

        if stats:
            # Update existing
            for key, value in stats_data.items():
                setattr(stats, key, value)
        else:
            # Create new
            stats = MarketStats(**stats_data)
            session.add(stats)

        session.commit()
        return stats

    def get_market_stats(
        self,
        session: Session,
        coin_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[MarketStats]:
        """Get market statistics history for a coin."""
        query = session.query(MarketStats).filter_by(coin_id=coin_id)

        if start_date:
            query = query.filter(MarketStats.timestamp >= start_date)
        if end_date:
            query = query.filter(MarketStats.timestamp <= end_date)

        query = query.order_by(MarketStats.timestamp.desc())

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_latest_market_stats(self, session: Session, coin_id: str) -> Optional[MarketStats]:
        """Get the most recent market statistics for a coin."""
        return session.query(MarketStats).filter_by(
            coin_id=coin_id
        ).order_by(MarketStats.timestamp.desc()).first()

    def bulk_insert_market_stats(self, session: Session, stats_list: List[Dict[str, Any]]):
        """Bulk insert market statistics (more efficient for large datasets)."""
        for stats_data in stats_list:
            # Check if exists
            existing = session.query(MarketStats).filter_by(
                coin_id=stats_data['coin_id'],
                timestamp=stats_data['timestamp']
            ).first()

            if not existing:
                stats = MarketStats(**stats_data)
                session.add(stats)

        session.commit()
