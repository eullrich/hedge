"""SQLAlchemy models for pair trading database."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Coin(Base):
    """Cryptocurrency coin information."""
    __tablename__ = 'coins'

    id = Column(String, primary_key=True)  # CoinGecko ID or Extended Exchange symbol
    symbol = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    market_cap = Column(Float)
    volume_24h = Column(Float)
    current_price = Column(Float)
    last_updated = Column(DateTime, default=datetime.now)

    # Extended Exchange specific fields
    funding_rate = Column(Float)
    open_interest = Column(Float)
    bid_price = Column(Float)
    ask_price = Column(Float)
    daily_high = Column(Float)
    daily_low = Column(Float)
    category = Column(String)
    ui_name = Column(String)
    index_price = Column(Float)
    mark_price = Column(Float)
    daily_volume_base = Column(Float)

    # Relationships
    pairs_as_base = relationship('TradingPair', foreign_keys='TradingPair.base_coin_id', back_populates='base_coin')
    pairs_as_quote = relationship('TradingPair', foreign_keys='TradingPair.quote_coin_id', back_populates='quote_coin')
    historical_data = relationship('HistoricalData', back_populates='coin', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_coin_symbol', 'symbol'),
        Index('idx_coin_market_cap', 'market_cap'),
    )

    def __repr__(self):
        return f"<Coin(id='{self.id}', symbol='{self.symbol}', name='{self.name}')>"


class TradingPair(Base):
    """Trading pair with relationship metrics."""
    __tablename__ = 'trading_pairs'

    id = Column(Integer, primary_key=True)
    base_coin_id = Column(String, ForeignKey('coins.id'), nullable=False)
    quote_coin_id = Column(String, ForeignKey('coins.id'), nullable=False)

    # Discovery metadata
    discovered_at = Column(DateTime, default=datetime.now)
    discovery_method = Column(String)  # 'correlation', 'narrative', 'manual'
    category = Column(String)  # e.g., 'AI', 'DeFi', 'Layer1'

    # Relationships
    base_coin = relationship('Coin', foreign_keys=[base_coin_id], back_populates='pairs_as_base')
    quote_coin = relationship('Coin', foreign_keys=[quote_coin_id], back_populates='pairs_as_quote')
    analyses = relationship('Analysis', back_populates='pair', cascade='all, delete-orphan')
    watchlists = relationship('Watchlist', back_populates='pair', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_pair_coins', 'base_coin_id', 'quote_coin_id', unique=True),
        Index('idx_pair_category', 'category'),
    )

    def __repr__(self):
        return f"<TradingPair(base={self.base_coin_id}, quote={self.quote_coin_id})>"


class HistoricalData(Base):
    """Historical OHLCV data for coins."""
    __tablename__ = 'historical_data'

    id = Column(Integer, primary_key=True)
    coin_id = Column(String, ForeignKey('coins.id'), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)

    price = Column(Float, nullable=False)
    market_cap = Column(Float)
    volume = Column(Float)

    # Relationships
    coin = relationship('Coin', back_populates='historical_data')

    __table_args__ = (
        Index('idx_historical_coin_time', 'coin_id', 'timestamp', unique=True),
    )

    def __repr__(self):
        return f"<HistoricalData(coin={self.coin_id}, timestamp={self.timestamp})>"


class Analysis(Base):
    """Statistical analysis results for trading pairs."""
    __tablename__ = 'analyses'

    id = Column(Integer, primary_key=True)
    pair_id = Column(Integer, ForeignKey('trading_pairs.id'), nullable=False)
    analyzed_at = Column(DateTime, default=datetime.now)

    # Time parameters
    lookback_days = Column(Integer, nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)

    # Correlation metrics
    correlation_pearson = Column(Float)
    correlation_spearman = Column(Float)
    rolling_correlation_mean = Column(Float)
    rolling_correlation_std = Column(Float)

    # Cointegration metrics
    is_cointegrated = Column(Boolean)
    cointegration_pvalue = Column(Float)
    half_life = Column(Float)  # Mean reversion half-life in days

    # Spread metrics
    spread_mean = Column(Float)
    spread_std = Column(Float)
    spread_zscore_current = Column(Float)

    # Reversion metrics
    reversion_count = Column(Integer)  # Number of historical reversions
    reversion_rate = Column(Float)  # Percentage of divergences that reverted
    avg_reversion_time = Column(Float)  # Average days to revert
    max_drawdown = Column(Float)

    # Additional metadata
    notes = Column(Text)
    quality_score = Column(Float)  # Composite quality metric (0-1)

    # Relationships
    pair = relationship('TradingPair', back_populates='analyses')

    __table_args__ = (
        Index('idx_analysis_pair_date', 'pair_id', 'analyzed_at'),
        Index('idx_analysis_correlation', 'correlation_pearson'),
        Index('idx_analysis_quality', 'quality_score'),
    )

    def __repr__(self):
        return f"<Analysis(pair_id={self.pair_id}, correlation={self.correlation_pearson:.2f})>"


class Watchlist(Base):
    """User watchlist for tracking interesting pairs."""
    __tablename__ = 'watchlist'

    id = Column(Integer, primary_key=True)
    pair_id = Column(Integer, ForeignKey('trading_pairs.id'), nullable=False)
    added_at = Column(DateTime, default=datetime.now)

    # User notes and tags
    notes = Column(Text)
    tags = Column(String)  # Comma-separated tags
    priority = Column(Integer, default=0)  # User-defined priority (0-5)
    is_active = Column(Boolean, default=True)

    # Relationships
    pair = relationship('TradingPair', back_populates='watchlists')

    __table_args__ = (
        Index('idx_watchlist_priority', 'priority'),
        Index('idx_watchlist_active', 'is_active'),
    )

    def __repr__(self):
        return f"<Watchlist(pair_id={self.pair_id}, priority={self.priority})>"


class MarketStats(Base):
    """Historical market statistics for perpetual futures contracts."""
    __tablename__ = 'market_stats'

    id = Column(Integer, primary_key=True)
    coin_id = Column(String, ForeignKey('coins.id'), nullable=False)
    timestamp = Column(DateTime, nullable=False)

    # Funding rate data
    funding_rate = Column(Float)  # Current funding rate (8-hour rate)
    predicted_funding_rate = Column(Float)  # Next funding rate prediction
    funding_timestamp = Column(DateTime)  # Next funding time

    # Open interest data
    open_interest = Column(Float)  # Total open interest in USD
    open_interest_value = Column(Float)  # OI in base currency

    # Price data
    mark_price = Column(Float)  # Perpetual mark price
    index_price = Column(Float)  # Underlying index price
    last_price = Column(Float)  # Last traded price

    # Bid/Ask spread
    bid_price = Column(Float)  # Best bid
    ask_price = Column(Float)  # Best ask
    bid_size = Column(Float)  # Best bid size
    ask_size = Column(Float)  # Best ask size

    # Volume data
    volume_24h = Column(Float)  # 24h trading volume
    volume_24h_base = Column(Float)  # 24h volume in base currency
    turnover_24h = Column(Float)  # 24h turnover

    # Price change metrics
    price_change_24h = Column(Float)  # 24h price change %
    high_24h = Column(Float)  # 24h high
    low_24h = Column(Float)  # 24h low

    # Relationships
    coin = relationship('Coin', foreign_keys=[coin_id])

    __table_args__ = (
        Index('idx_market_stats_coin_time', 'coin_id', 'timestamp', unique=True),
        Index('idx_market_stats_timestamp', 'timestamp'),
        Index('idx_market_stats_funding', 'funding_rate'),
        Index('idx_market_stats_oi', 'open_interest'),
    )

    def __repr__(self):
        return f"<MarketStats(coin={self.coin_id}, timestamp={self.timestamp}, funding={self.funding_rate})>"
