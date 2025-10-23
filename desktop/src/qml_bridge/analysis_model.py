"""QML bridge for Analysis data and chart rendering."""
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.database import DatabaseManager
from src.api import HyperliquidClient
from statsmodels.tsa.stattools import adfuller, coint
from statsmodels.regression.linear_model import OLS


class AnalysisModel(QObject):
    """Qt model for exposing analysis data and chart methods to QML."""

    # Signals
    pairLoaded = pyqtSignal(str, str)  # coin1, coin2
    analysisComplete = pyqtSignal()
    errorOccurred = pyqtSignal(str)  # error message

    # Property change signals
    currentPairChanged = pyqtSignal()
    correlationChanged = pyqtSignal()
    zscoreChanged = pyqtSignal()
    halfLifeChanged = pyqtSignal()
    signalChanged = pyqtSignal()
    isLoadingChanged = pyqtSignal()
    chartDataChanged = pyqtSignal()
    cointegrationChanged = pyqtSignal()
    hedgeRatioChanged = pyqtSignal()
    volatilityChanged = pyqtSignal()
    priceChangeChanged = pyqtSignal()

    def __init__(self, db_manager: DatabaseManager, api_client: HyperliquidClient, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.api_client = api_client

        # Internal state
        self._current_pair = ""
        self._coin1 = ""
        self._coin2 = ""
        self._correlation = 0.0
        self._zscore = 0.0
        self._half_life = 0.0
        self._signal = "NEUTRAL"
        self._is_loading = False

        # Cointegration & volatility metrics
        self._is_cointegrated = False
        self._coint_pvalue = 1.0
        self._hedge_ratio = 1.0
        self._spread_volatility = 0.0

        # Price change metrics
        self._change_24h = 0.0
        self._change_7d = 0.0

        # Chart data as simple lists
        self._ratio_timestamps = []
        self._ratio_values = []
        self._zscore_timestamps = []
        self._zscore_values = []
        self._coin1_timestamps = []
        self._coin1_values = []
        self._coin2_timestamps = []
        self._coin2_values = []

        # Spread candlestick data (OHLC)
        self._spread_timestamps = []
        self._spread_open = []
        self._spread_high = []
        self._spread_low = []
        self._spread_close = []

        # Ratio with EMA and Bollinger Bands
        self._ratio_ema_timestamps = []
        self._ratio_ema = []
        self._ratio_bb_upper = []
        self._ratio_bb_lower = []

        # Rolling correlation
        self._rolling_corr_timestamps = []
        self._rolling_corr_values = []

        # Beta evolution
        self._beta_timestamps = []
        self._beta_values = []
        self._beta_ci_upper = []
        self._beta_ci_lower = []

        # Volatility
        self._volatility_timestamps = []
        self._volatility_values = []

    # Properties
    @pyqtProperty(str, notify=currentPairChanged)
    def currentPair(self):
        return self._current_pair

    @pyqtProperty(float, notify=correlationChanged)
    def correlation(self):
        return self._correlation

    @pyqtProperty(float, notify=zscoreChanged)
    def zscore(self):
        return self._zscore

    @pyqtProperty(float, notify=halfLifeChanged)
    def halfLife(self):
        return self._half_life

    @pyqtProperty(str, notify=signalChanged)
    def signal(self):
        return self._signal

    @pyqtProperty(bool, notify=isLoadingChanged)
    def isLoading(self):
        return self._is_loading

    @pyqtProperty(bool, notify=cointegrationChanged)
    def isCointegrated(self):
        return self._is_cointegrated

    @pyqtProperty(float, notify=cointegrationChanged)
    def cointPvalue(self):
        return self._coint_pvalue

    @pyqtProperty(float, notify=hedgeRatioChanged)
    def hedgeRatio(self):
        return self._hedge_ratio

    @pyqtProperty(float, notify=volatilityChanged)
    def spreadVolatility(self):
        return self._spread_volatility

    @pyqtProperty(float, notify=priceChangeChanged)
    def change24h(self):
        return self._change_24h

    @pyqtProperty(float, notify=priceChangeChanged)
    def change7d(self):
        return self._change_7d

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def ratioTimestamps(self):
        return self._ratio_timestamps

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def ratioValues(self):
        return self._ratio_values

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def zscoreTimestamps(self):
        return self._zscore_timestamps

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def zscoreValues(self):
        return self._zscore_values

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def coin1Timestamps(self):
        return self._coin1_timestamps

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def coin1Values(self):
        return self._coin1_values

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def coin2Timestamps(self):
        return self._coin2_timestamps

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def coin2Values(self):
        return self._coin2_values

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def spreadTimestamps(self):
        return self._spread_timestamps

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def spreadOpen(self):
        return self._spread_open

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def spreadHigh(self):
        return self._spread_high

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def spreadLow(self):
        return self._spread_low

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def spreadClose(self):
        return self._spread_close

    # Ratio EMA and Bollinger Bands properties
    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def ratioEmaTimestamps(self):
        return self._ratio_ema_timestamps

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def ratioEma(self):
        return self._ratio_ema

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def ratioBbUpper(self):
        return self._ratio_bb_upper

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def ratioBbLower(self):
        return self._ratio_bb_lower

    # Rolling correlation properties
    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def rollingCorrTimestamps(self):
        return self._rolling_corr_timestamps

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def rollingCorrValues(self):
        return self._rolling_corr_values

    # Beta evolution properties
    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def betaTimestamps(self):
        return self._beta_timestamps

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def betaValues(self):
        return self._beta_values

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def betaCiUpper(self):
        return self._beta_ci_upper

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def betaCiLower(self):
        return self._beta_ci_lower

    # Volatility properties
    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def volatilityTimestamps(self):
        return self._volatility_timestamps

    @pyqtProperty('QVariantList', notify=chartDataChanged)
    def volatilityValues(self):
        return self._volatility_values

    @pyqtSlot(str, str, str)
    def loadPair(self, coin1: str, coin2: str, timeframe: str = '1d'):
        """
        Load analysis data for a trading pair.

        Args:
            coin1: First coin symbol
            coin2: Second coin symbol
            timeframe: Analysis timeframe (1h, 4h, 1d, 1w)
        """
        self._is_loading = True
        self.isLoadingChanged.emit()

        try:
            import pandas as pd
            import numpy as np
            from datetime import datetime

            self._coin1 = coin1.upper()
            self._coin2 = coin2.upper()
            self._current_pair = f"{self._coin1}/{self._coin2}"
            self.currentPairChanged.emit()

            # Fetch OHLCV data from database (not API!)
            from datetime import timedelta

            # Map timeframe to days and granularity
            timeframe_config = {
                '5min': {'days': 1, 'granularity': '5min'},
                '1hour': {'days': 7, 'granularity': '1hour'},
                '4hour': {'days': 60, 'granularity': '4hour'}
            }
            config = timeframe_config.get(timeframe, {'days': 7, 'granularity': '1hour'})
            days = config['days']
            granularity = config['granularity']

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            with self.db.get_session() as session:
                coin1_data = self.db.get_ohlcv_data(
                    session,
                    coin_id=self._coin1,
                    start_date=start_date,
                    end_date=end_date,
                    granularity=granularity
                )
                coin2_data = self.db.get_ohlcv_data(
                    session,
                    coin_id=self._coin2,
                    start_date=start_date,
                    end_date=end_date,
                    granularity=granularity
                )

            if not coin1_data or not coin2_data:
                self.errorOccurred.emit(f"No database data for {self._current_pair}. Run 'Force Refresh' first.")
                self._is_loading = False
                self.isLoadingChanged.emit()
                return

            # Convert ORM objects to DataFrames
            df1 = pd.DataFrame([{
                'timestamp': c.timestamp,
                'open': c.open,
                'high': c.high,
                'low': c.low,
                'close': c.close,
                'volume': c.volume
            } for c in coin1_data])
            df2 = pd.DataFrame([{
                'timestamp': c.timestamp,
                'open': c.open,
                'high': c.high,
                'low': c.low,
                'close': c.close,
                'volume': c.volume
            } for c in coin2_data])

            # Align data
            min_len = min(len(df1), len(df2))
            df1 = df1.tail(min_len)
            df2 = df2.tail(min_len)

            # Check for minimum data points
            if min_len < 10:
                print(f"⚠️ Insufficient data for {self._current_pair}: only {min_len} candles")
                print(f"💡 Try using a shorter timeframe (1h or 4h) for newly listed coins")
                self.errorOccurred.emit(f"Insufficient data for {self._current_pair} (only {min_len} candles). Try 1h or 4h timeframe for new coins.")
                self._is_loading = False
                self.isLoadingChanged.emit()
                return

            # Calculate ratio and z-score
            coin1_prices = df1['close'].values
            coin2_prices = df2['close'].values
            ratio = coin1_prices / coin2_prices

            # Calculate correlation
            self._correlation = float(np.corrcoef(coin1_prices, coin2_prices)[0, 1])

            # Calculate z-score
            ratio_mean = np.mean(ratio)
            ratio_std = np.std(ratio)
            zscore = (ratio - ratio_mean) / ratio_std if ratio_std > 0 else np.zeros_like(ratio)
            self._zscore = float(zscore[-1])

            # Calculate 24h and 7d ratio changes
            current_ratio = ratio[-1]

            # 24h change (need at least 24 data points for 1h, or 6 for 4h)
            if granularity == '1hour' and len(ratio) >= 24:
                ratio_24h_ago = ratio[-24]
                self._change_24h = ((current_ratio - ratio_24h_ago) / ratio_24h_ago) * 100
            elif granularity == '4hour' and len(ratio) >= 6:
                ratio_24h_ago = ratio[-6]
                self._change_24h = ((current_ratio - ratio_24h_ago) / ratio_24h_ago) * 100
            else:
                self._change_24h = 0.0

            # 7d change (need at least 168 data points for 1h, or 42 for 4h)
            if granularity == '1hour' and len(ratio) >= 168:
                ratio_7d_ago = ratio[-168]
                self._change_7d = ((current_ratio - ratio_7d_ago) / ratio_7d_ago) * 100
            elif granularity == '4hour' and len(ratio) >= 42:
                ratio_7d_ago = ratio[-42]
                self._change_7d = ((current_ratio - ratio_7d_ago) / ratio_7d_ago) * 100
            else:
                self._change_7d = 0.0

            # Test cointegration using Engle-Granger
            try:
                # Align series
                price1_series = pd.Series(coin1_prices)
                price2_series = pd.Series(coin2_prices)

                # Run Engle-Granger cointegration test
                coint_score, p_value, crit_values = coint(price1_series, price2_series)

                # Calculate hedge ratio using OLS regression
                model = OLS(price1_series, price2_series).fit()
                hedge_ratio = float(model.params[0])  # params is a numpy array

                # Calculate spread using hedge ratio
                spread = coin1_prices - hedge_ratio * coin2_prices

                # Calculate half-life from cointegrated spread (more accurate than AR(1))
                spread_lagged = spread[:-1]
                spread_diff = np.diff(spread)
                if len(spread_lagged) > 0:
                    # OLS regression: delta_spread = lambda * spread_lagged + epsilon
                    spread_model = OLS(spread_diff, spread_lagged).fit()
                    lambda_param = float(spread_model.params[0])  # params is a numpy array
                    if lambda_param < 0:
                        self._half_life = float(-np.log(2) / lambda_param)
                    else:
                        self._half_life = 0.0
                else:
                    self._half_life = 0.0

                # Store cointegration results
                self._is_cointegrated = bool(p_value < 0.05)
                self._coint_pvalue = float(p_value)
                self._hedge_ratio = hedge_ratio

                # Calculate spread volatility for the entire selected period (annualized)
                spread_returns = np.diff(spread) / spread[:-1]
                spread_std = np.std(spread_returns)
                # Annualize based on granularity
                periods_per_year = {'5min': 105120, '1hour': 8760, '4hour': 2190}  # 365 * periods_per_day
                annualization_factor = np.sqrt(periods_per_year.get(granularity, 8760))
                self._spread_volatility = float(spread_std * annualization_factor * 100)  # As percentage for stats card

            except Exception as e:
                print(f"⚠️ Cointegration test failed: {e}")
                self._is_cointegrated = False
                self._coint_pvalue = 1.0
                self._hedge_ratio = 1.0
                self._spread_volatility = 0.0
                self._half_life = 0.0

            # Determine signal
            if self._zscore > 2.0:
                self._signal = "SHORT"
            elif self._zscore < -2.0:
                self._signal = "LONG"
            else:
                self._signal = "NEUTRAL"

            self.correlationChanged.emit()
            self.zscoreChanged.emit()
            self.halfLifeChanged.emit()
            self.signalChanged.emit()
            self.cointegrationChanged.emit()
            self.hedgeRatioChanged.emit()
            self.volatilityChanged.emit()

            # Prepare chart data
            # Normalize prices to start at 100 for comparison
            norm1 = (coin1_prices / coin1_prices[0]) * 100
            norm2 = (coin2_prices / coin2_prices[0]) * 100

            # Normalize ratio to start at 100
            normalized_ratio = (ratio / ratio[0]) * 100

            # Convert timestamps to milliseconds (Unix epoch * 1000 for QML)
            timestamps = df1['timestamp'].values

            # Convert timestamps - handle both string and Timestamp objects
            def to_millis(ts):
                if isinstance(ts, (int, float)):
                    return int(ts)  # Already milliseconds
                elif isinstance(ts, pd.Timestamp):
                    return int(ts.value // 1_000_000)  # nanoseconds to milliseconds
                else:
                    return int(pd.Timestamp(ts).timestamp() * 1000)

            self._ratio_timestamps = [to_millis(ts) for ts in timestamps]
            self._ratio_values = [float(r) for r in normalized_ratio]

            self._zscore_timestamps = [to_millis(ts) for ts in timestamps]
            self._zscore_values = [float(z) for z in zscore]

            self._coin1_timestamps = [to_millis(ts) for ts in timestamps]
            self._coin1_values = [float(p) for p in norm1]

            self._coin2_timestamps = [to_millis(ts) for ts in timestamps]
            self._coin2_values = [float(p) for p in norm2]

            # Calculate spread OHLC (spread = coin1_price - coin2_price)
            # We already have close values, now calculate open/high/low from the full OHLC data
            spread_open = df1['open'].values - df2['open'].values
            spread_high = df1['high'].values - df2['high'].values
            spread_low = df1['low'].values - df2['low'].values
            spread_close = coin1_prices - coin2_prices  # Already calculated as ratio denominator

            # Normalize spread to start at 100 (like ratio)
            base_spread = spread_close[0]
            normalized_spread_open = (spread_open / base_spread) * 100
            normalized_spread_high = (spread_high / base_spread) * 100
            normalized_spread_low = (spread_low / base_spread) * 100
            normalized_spread_close = (spread_close / base_spread) * 100

            self._spread_timestamps = [int(pd.Timestamp(ts).timestamp() * 1000) for ts in timestamps]
            self._spread_open = [float(s) for s in normalized_spread_open]
            self._spread_high = [float(s) for s in normalized_spread_high]
            self._spread_low = [float(s) for s in normalized_spread_low]
            self._spread_close = [float(s) for s in normalized_spread_close]

            # Calculate EMA and Bollinger Bands for ratio
            ema_period = 20
            bb_period = 20
            bb_std = 2

            # Use non-normalized ratio for indicators
            raw_ratio = coin1_prices / coin2_prices
            ratio_series = pd.Series(raw_ratio)

            # Calculate EMA
            ema = ratio_series.ewm(span=ema_period, adjust=False).mean()

            # Calculate Bollinger Bands
            bb_ma = ratio_series.rolling(window=bb_period).mean()
            bb_std_dev = ratio_series.rolling(window=bb_period).std()
            bb_upper = bb_ma + (bb_std * bb_std_dev)
            bb_lower = bb_ma - (bb_std * bb_std_dev)

            # Normalize EMA and BB to match normalized ratio
            base_ratio = raw_ratio[0]
            normalized_ema = (ema / base_ratio) * 100
            normalized_bb_upper = (bb_upper / base_ratio) * 100
            normalized_bb_lower = (bb_lower / base_ratio) * 100

            self._ratio_ema_timestamps = [int(pd.Timestamp(ts).timestamp() * 1000) for ts in timestamps]
            self._ratio_ema = [float(v) if not np.isnan(v) else None for v in normalized_ema]
            self._ratio_bb_upper = [float(v) if not np.isnan(v) else None for v in normalized_bb_upper]
            self._ratio_bb_lower = [float(v) if not np.isnan(v) else None for v in normalized_bb_lower]

            # Calculate rolling correlation
            corr_window = 20
            rolling_corr = df1['close'].rolling(window=corr_window).corr(df2['close'])

            self._rolling_corr_timestamps = [int(pd.Timestamp(ts).timestamp() * 1000) for ts in timestamps]
            self._rolling_corr_values = [float(v) if not np.isnan(v) else None for v in rolling_corr]

            # Calculate rolling beta with confidence intervals
            beta_window = 20

            # Calculate returns
            returns1 = df1['close'].pct_change()
            returns2 = df2['close'].pct_change()

            # Rolling beta calculation
            beta_values = []
            beta_ci_upper_values = []
            beta_ci_lower_values = []

            for i in range(len(returns1)):
                if i < beta_window:
                    beta_values.append(None)
                    beta_ci_upper_values.append(None)
                    beta_ci_lower_values.append(None)
                else:
                    window_returns1 = returns1.iloc[i-beta_window:i]
                    window_returns2 = returns2.iloc[i-beta_window:i]

                    # Calculate beta (covariance / variance)
                    covariance = window_returns1.cov(window_returns2)
                    variance = window_returns2.var()

                    if variance > 0:
                        beta = covariance / variance

                        # Simple CI estimate using std error
                        residuals = window_returns1 - (beta * window_returns2)
                        std_error = residuals.std() / np.sqrt(beta_window)
                        ci_margin = 1.96 * std_error  # 95% CI

                        beta_values.append(float(beta))
                        beta_ci_upper_values.append(float(beta + ci_margin))
                        beta_ci_lower_values.append(float(beta - ci_margin))
                    else:
                        beta_values.append(None)
                        beta_ci_upper_values.append(None)
                        beta_ci_lower_values.append(None)

            self._beta_timestamps = [int(pd.Timestamp(ts).timestamp() * 1000) for ts in timestamps]
            self._beta_values = beta_values
            self._beta_ci_upper = beta_ci_upper_values
            self._beta_ci_lower = beta_ci_lower_values

            # Calculate rolling spread volatility
            vol_window = 20
            # Calculate spread using hedge ratio from cointegration
            spread_series = coin1_prices - self._hedge_ratio * coin2_prices
            spread_returns = pd.Series(spread_series).pct_change()
            rolling_vol = spread_returns.rolling(window=vol_window).std()

            # Annualize the rolling volatility
            periods_per_year = {'5min': 105120, '1hour': 8760, '4hour': 2190}
            annualization_factor = np.sqrt(periods_per_year.get(granularity, 8760))
            annualized_rolling_vol = rolling_vol * annualization_factor * 100  # As percentage

            self._volatility_timestamps = [int(pd.Timestamp(ts).timestamp() * 1000) for ts in timestamps]
            self._volatility_values = [float(v) if not np.isnan(v) else None for v in annualized_rolling_vol]

            self.chartDataChanged.emit()
            self.priceChangeChanged.emit()

            self.pairLoaded.emit(coin1, coin2)
            self.analysisComplete.emit()

        except Exception as e:
            import traceback
            error_msg = f"Error loading pair: {e}\n{traceback.format_exc()}"
            print(error_msg)
            self.errorOccurred.emit(str(e))

        finally:
            self._is_loading = False
            self.isLoadingChanged.emit()

    @pyqtSlot()
    def refresh(self):
        """Refresh analysis for current pair."""
        if self._coin1 and self._coin2:
            self.loadPair(self._coin1, self._coin2)

    @pyqtSlot(result=str)
    def getChartData(self):
        """
        Get chart data for the current pair.
        Returns JSON string with chart data.
        TODO: Implement actual chart data retrieval.
        """
        # Placeholder for chart data
        return '{"prices": [], "ratio": [], "zscore": []}'
