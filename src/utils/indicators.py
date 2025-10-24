"""Technical indicators for market analysis."""
import numpy as np
import pandas as pd
from typing import Dict, Any


def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
    """Calculate RSI (Relative Strength Index)."""
    if len(prices) < period + 1:
        return 50.0

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi)


def calculate_volatility(prices: np.ndarray, period: int = 30) -> float:
    """Calculate annualized volatility."""
    if len(prices) < 2:
        return 0.0

    returns = np.diff(prices) / prices[:-1]
    volatility = np.std(returns[-period:]) * np.sqrt(365)
    return float(volatility)


def calculate_beta(asset_prices: np.ndarray, market_prices: np.ndarray) -> float:
    """Calculate beta relative to market."""
    if len(asset_prices) < 2 or len(market_prices) < 2:
        return 1.0

    asset_returns = np.diff(asset_prices) / asset_prices[:-1]
    market_returns = np.diff(market_prices) / market_prices[:-1]

    covariance = np.cov(asset_returns, market_returns)[0, 1]
    market_variance = np.var(market_returns)

    if market_variance == 0:
        return 1.0

    beta = covariance / market_variance
    return float(beta)


def calculate_volume_profile(volume_24h: float, market_cap: float) -> Dict[str, Any]:
    """Calculate volume-related metrics."""
    if market_cap == 0:
        return {
            'volume_mcap_ratio': 0.0,
            'liquidity_score': 0.0
        }

    volume_mcap_ratio = volume_24h / market_cap
    liquidity_score = min(volume_mcap_ratio * 10, 10.0)

    return {
        'volume_mcap_ratio': float(volume_mcap_ratio),
        'liquidity_score': float(liquidity_score)
    }


def detect_trend(prices: np.ndarray) -> str:
    """Detect price trend (uptrend, downtrend, sideways)."""
    if len(prices) < 20:
        return "sideways"

    # Simple trend detection using moving averages
    short_ma = np.mean(prices[-10:])
    long_ma = np.mean(prices[-20:])

    diff_pct = ((short_ma - long_ma) / long_ma) * 100

    if diff_pct > 2:
        return "uptrend"
    elif diff_pct < -2:
        return "downtrend"
    else:
        return "sideways"


def calculate_relative_strength(price_change: float, market_change: float) -> float:
    """Calculate relative strength vs market."""
    if market_change == 0:
        return 0.0

    relative_strength = price_change - market_change
    return float(relative_strength)


def calculate_rsi_series(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate RSI for entire price series (vectorized for backtesting).

    Args:
        prices: Pandas Series of prices
        period: RSI period (default 14)

    Returns:
        Pandas Series of RSI values
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_stochastic(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Stochastic Oscillator %K for entire price series.

    Args:
        prices: Pandas Series of prices
        period: Lookback period (default 14)

    Returns:
        Pandas Series of Stochastic %K values (0-100)
    """
    lowest_low = prices.rolling(window=period).min()
    highest_high = prices.rolling(window=period).max()

    stoch_k = 100 * (prices - lowest_low) / (highest_high - lowest_low)
    return stoch_k
