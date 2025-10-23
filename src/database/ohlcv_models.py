"""Extended database models for OHLCV data and explorer features."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Index, Text
)
from .models import Base


class OHLCVData(Base):
    """Multi-granularity OHLCV candle data for coins (5min, 1hour, 4hour)."""
    __tablename__ = 'ohlcv_data'

    id = Column(Integer, primary_key=True)
    coin_id = Column(String, ForeignKey('coins.id'), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    granularity = Column(String, nullable=False, default='4hour')  # '5min', '1hour', '4hour'

    # OHLCV data
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float)
    market_cap = Column(Float)

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('idx_ohlcv_coin_time_gran', 'coin_id', 'timestamp', 'granularity', unique=True),
        Index('idx_ohlcv_timestamp', 'timestamp'),
        Index('idx_ohlcv_granularity', 'granularity'),
    )

    def __repr__(self):
        return f"<OHLCVData(coin={self.coin_id}, time={self.timestamp}, close={self.close})>"


class ExplorerWatchlist(Base):
    """User's watchlist of coins for the explorer page."""
    __tablename__ = 'explorer_watchlist'

    id = Column(Integer, primary_key=True)
    coin_id = Column(String, ForeignKey('coins.id'), nullable=False, unique=True)

    added_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True, index=True)
    position = Column(Integer, default=0)  # Display order

    # User notes
    notes = Column(Text)

    __table_args__ = (
        Index('idx_watchlist_active_position', 'is_active', 'position'),
    )

    def __repr__(self):
        return f"<ExplorerWatchlist(coin={self.coin_id}, position={self.position})>"


class ExplorerMetricsCache(Base):
    """Cached calculated metrics for explorer table."""
    __tablename__ = 'explorer_metrics_cache'

    id = Column(Integer, primary_key=True)
    coin_id = Column(String, ForeignKey('coins.id'), nullable=False)
    reference_coin_id = Column(String, ForeignKey('coins.id'), nullable=True)  # NULL = absolute mode
    lookback_days = Column(Integer, nullable=False)  # 14, 30, 90, or 180

    calculated_at = Column(DateTime, default=datetime.now, index=True)

    # Price data
    current_price = Column(Float)
    price_change_pct = Column(Float)  # % change over lookback period

    # Absolute metrics (always calculated)
    rsi = Column(Float)
    volatility = Column(Float)
    beta = Column(Float)  # vs Bitcoin
    trend = Column(String)  # 'Bullish', 'Bearish', 'Neutral'
    volume_to_mcap = Column(Float)
    liquidity_rating = Column(String)

    # Relative metrics (only when reference_coin_id is set)
    correlation = Column(Float)
    ratio_current = Column(Float)
    ratio_trend = Column(String)  # 'Strengthening', 'Weakening', 'Neutral'
    outperformance = Column(Float)  # % points
    spread_zscore = Column(Float)
    suggested_position = Column(String)  # 'LONG', 'SHORT', 'long', 'short', '-'

    __table_args__ = (
        Index('idx_metrics_coin_ref_lookback', 'coin_id', 'reference_coin_id', 'lookback_days'),
        Index('idx_metrics_calculated_at', 'calculated_at'),
    )

    def __repr__(self):
        ref = f" vs {self.reference_coin_id}" if self.reference_coin_id else ""
        return f"<ExplorerMetricsCache(coin={self.coin_id}{ref}, {self.lookback_days}d)>"


class Tag(Base):
    """Tags for categorizing coins."""
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String)  # Hex color code for UI display
    description = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Tag(name={self.name})>"


class CoinTag(Base):
    """Many-to-many relationship between coins and tags."""
    __tablename__ = 'coin_tags'

    id = Column(Integer, primary_key=True)
    coin_id = Column(String, nullable=False)
    tag_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('idx_coin_tags_coin', 'coin_id'),
        Index('idx_coin_tags_tag', 'tag_id'),
        Index('idx_coin_tags_unique', 'coin_id', 'tag_id', unique=True),
    )

    def __repr__(self):
        return f"<CoinTag(coin={self.coin_id}, tag={self.tag_id})>"


class FundingRateHistory(Base):
    """Historical funding rate data for perpetual markets."""
    __tablename__ = 'funding_rate_history'

    id = Column(Integer, primary_key=True)
    coin_id = Column(String, ForeignKey('coins.id'), nullable=False)
    timestamp = Column(DateTime, nullable=False)

    # Funding rate metrics
    funding_rate = Column(Float, nullable=False)
    mark_price = Column(Float)
    index_price = Column(Float)

    # Volume and interest
    open_interest = Column(Float)
    open_interest_base = Column(Float)
    daily_volume = Column(Float)
    daily_volume_base = Column(Float)

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('idx_funding_coin_time', 'coin_id', 'timestamp', unique=True),
        Index('idx_funding_timestamp', 'timestamp'),
    )

    def __repr__(self):
        return f"<FundingRateHistory(coin={self.coin_id}, time={self.timestamp}, rate={self.funding_rate})>"


class MarketStatsHistory(Base):
    """Historical market statistics snapshots."""
    __tablename__ = 'market_stats_history'

    id = Column(Integer, primary_key=True)
    coin_id = Column(String, ForeignKey('coins.id'), nullable=False)
    timestamp = Column(DateTime, nullable=False)

    # Price metrics
    last_price = Column(Float)
    mark_price = Column(Float)
    index_price = Column(Float)
    ask_price = Column(Float)
    bid_price = Column(Float)

    # Daily metrics
    daily_high = Column(Float)
    daily_low = Column(Float)
    daily_price_change = Column(Float)
    daily_price_change_pct = Column(Float)

    # Volume and OI
    daily_volume = Column(Float)
    daily_volume_base = Column(Float)
    open_interest = Column(Float)
    open_interest_base = Column(Float)

    # Funding
    funding_rate = Column(Float)
    next_funding_time = Column(DateTime)

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('idx_market_stats_coin_time', 'coin_id', 'timestamp', unique=True),
        Index('idx_market_stats_timestamp', 'timestamp'),
    )

    def __repr__(self):
        return f"<MarketStatsHistory(coin={self.coin_id}, time={self.timestamp})>"


class DataUpdateLog(Base):
    """Log of background data updates."""
    __tablename__ = 'data_update_log'

    id = Column(Integer, primary_key=True)
    update_type = Column(String, nullable=False)  # 'ohlcv', 'metrics', 'full', 'funding', 'market_stats'
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)

    coins_updated = Column(Integer, default=0)
    coins_failed = Column(Integer, default=0)

    status = Column(String, nullable=False)  # 'running', 'completed', 'failed'
    error_message = Column(Text)

    __table_args__ = (
        Index('idx_update_log_type_status', 'update_type', 'status'),
        Index('idx_update_log_started', 'started_at'),
    )

    def __repr__(self):
        return f"<DataUpdateLog(type={self.update_type}, status={self.status}, started={self.started_at})>"
