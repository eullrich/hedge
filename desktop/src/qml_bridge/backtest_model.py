"""QML bridge for Backtesting functionality."""
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty, QThread
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.database import DatabaseManager, OHLCVData
from src.api import HyperliquidClient
from src.utils import calculate_rsi_series, calculate_stochastic


class BacktestModel(QObject):
    """Qt model for exposing backtest functionality to QML."""

    # Signals
    backtestStarted = pyqtSignal()
    backtestComplete = pyqtSignal()
    backtestProgress = pyqtSignal(int)  # progress percentage
    errorOccurred = pyqtSignal(str)  # error message

    # Property change signals
    isRunningChanged = pyqtSignal()
    resultsChanged = pyqtSignal()
    dataAvailableChanged = pyqtSignal()
    dataStartDateChanged = pyqtSignal()
    dataEndDateChanged = pyqtSignal()
    dataPointCountChanged = pyqtSignal()

    def __init__(self, db_manager: DatabaseManager, api_client: HyperliquidClient, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.api_client = api_client

        # Internal state
        self._is_running = False
        self._results = {}
        self._data_available = False
        self._data_start_date = ""
        self._data_end_date = ""
        self._data_point_count = 0

    # Properties
    @pyqtProperty(bool, notify=isRunningChanged)
    def isRunning(self):
        return self._is_running

    @pyqtProperty('QVariantMap', notify=resultsChanged)
    def results(self):
        """Return backtest results as QVariantMap (dict)."""
        return self._results

    @pyqtProperty(bool, notify=dataAvailableChanged)
    def dataAvailable(self):
        return self._data_available

    @pyqtProperty(str, notify=dataStartDateChanged)
    def dataStartDate(self):
        return self._data_start_date

    @pyqtProperty(str, notify=dataEndDateChanged)
    def dataEndDate(self):
        return self._data_end_date

    @pyqtProperty(int, notify=dataPointCountChanged)
    def dataPointCount(self):
        return self._data_point_count

    @pyqtSlot(str, str, str, str, str, str, float, int, int)
    def runBacktest(self, coin1: str, coin2: str, start_date: str, end_date: str,
                    timeframe: str = "1hour", strategy: str = "z_rsi",
                    z_threshold: float = 2.0, rsi_period: int = 14, window_size: int = 30):
        """
        Run backtest for a trading pair over a date range.

        Args:
            coin1: First coin symbol
            coin2: Second coin symbol
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            timeframe: Granularity ('5min', '1hour', '4hour')
            strategy: Strategy variant ('pure_z', 'z_rsi', 'z_stoch', 'divergence')
            z_threshold: Z-score entry threshold (default 2.0)
            rsi_period: RSI period (default 14)
            window_size: Rolling window for z-score (default 30)
        """
        if self._is_running:
            self.errorOccurred.emit("Backtest already running")
            return

        self._is_running = True
        self.isRunningChanged.emit()
        self.backtestStarted.emit()

        try:
            print(f"Running backtest for {coin1}/{coin2} from {start_date} to {end_date}")
            print(f"Strategy: {strategy}, Timeframe: {timeframe}, Z-threshold: {z_threshold}")

            self.backtestProgress.emit(0)

            # 1. Fetch OHLCV data from database
            df1, df2 = self._fetch_ohlcv_data(coin1, coin2, start_date, end_date, timeframe)
            if df1 is None or df2 is None:
                raise ValueError("Insufficient data for backtesting")

            self.backtestProgress.emit(25)

            # 2. Generate signals based on strategy
            signals = self._generate_signals(df1, df2, strategy, z_threshold, rsi_period, window_size)

            self.backtestProgress.emit(50)

            # 3. Simulate trades with transaction costs
            trades, equity_curve = self._simulate_trades(signals, df1, df2)

            self.backtestProgress.emit(75)

            # 4. Calculate performance metrics
            metrics = self._calculate_metrics(trades, equity_curve)

            self.backtestProgress.emit(100)

            # Store results
            self._results = {
                'pair': f"{coin1}/{coin2}",
                'total_return': metrics['total_return'],
                'sharpe_ratio': metrics['sharpe_ratio'],
                'max_drawdown': metrics['max_drawdown'],
                'win_rate': metrics['win_rate'],
                'total_trades': metrics['total_trades'],
                'profitable_trades': metrics['profitable_trades'],
                'avg_trade_duration': metrics['avg_trade_duration'],
                'avg_profit_per_trade': metrics['avg_profit_per_trade'],
            }
            self.resultsChanged.emit()
            self.backtestComplete.emit()

        except Exception as e:
            error_msg = f"Error running backtest: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.errorOccurred.emit(error_msg)

        finally:
            self._is_running = False
            self.isRunningChanged.emit()

    def _fetch_ohlcv_data(self, coin1: str, coin2: str, start_date: str, end_date: str, timeframe: str):
        """Fetch OHLCV data from database for both coins."""
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)

            with self.db.get_session() as session:
                # Fetch coin1 data
                query1 = session.query(OHLCVData).filter(
                    OHLCVData.coin_id == coin1,
                    OHLCVData.granularity == timeframe,
                    OHLCVData.timestamp >= start_dt,
                    OHLCVData.timestamp <= end_dt
                ).order_by(OHLCVData.timestamp)

                data1 = query1.all()

                # Fetch coin2 data
                query2 = session.query(OHLCVData).filter(
                    OHLCVData.coin_id == coin2,
                    OHLCVData.granularity == timeframe,
                    OHLCVData.timestamp >= start_dt,
                    OHLCVData.timestamp <= end_dt
                ).order_by(OHLCVData.timestamp)

                data2 = query2.all()

            if not data1 or not data2:
                return None, None

            # Convert to DataFrames
            df1 = pd.DataFrame([{
                'timestamp': d.timestamp,
                'open': d.open,
                'high': d.high,
                'low': d.low,
                'close': d.close,
                'volume': d.volume
            } for d in data1])

            df2 = pd.DataFrame([{
                'timestamp': d.timestamp,
                'open': d.open,
                'high': d.high,
                'low': d.low,
                'close': d.close,
                'volume': d.volume
            } for d in data2])

            # Set timestamp as index and remove duplicates
            df1.set_index('timestamp', inplace=True)
            df2.set_index('timestamp', inplace=True)

            # Remove duplicate timestamps (keep last)
            df1 = df1[~df1.index.duplicated(keep='last')]
            df2 = df2[~df2.index.duplicated(keep='last')]

            # Align timestamps (inner join to only keep matching timestamps)
            df1, df2 = df1.align(df2, join='inner')

            if len(df1) < 50:  # Need minimum data for indicators
                return None, None

            return df1, df2

        except Exception as e:
            print(f"Error fetching OHLCV data: {e}")
            return None, None

    def _generate_signals(self, df1: pd.DataFrame, df2: pd.DataFrame, strategy: str,
                         z_threshold: float, rsi_period: int, window_size: int) -> pd.DataFrame:
        """Generate trading signals based on strategy."""
        # Calculate price ratio
        ratio = df1['close'] / df2['close']

        # Calculate z-score
        ratio_mean = ratio.rolling(window=window_size).mean()
        ratio_std = ratio.rolling(window=window_size).std()
        z_score = (ratio - ratio_mean) / ratio_std

        # Initialize signals DataFrame
        signals = pd.DataFrame(index=df1.index)
        signals['z_score'] = z_score
        signals['position'] = 0  # 0 = no position, 1 = long spread, -1 = short spread

        if strategy == 'pure_z':
            # Pure Z-Score strategy
            signals.loc[z_score < -z_threshold, 'position'] = 1   # Long spread when undervalued
            signals.loc[z_score > z_threshold, 'position'] = -1   # Short spread when overvalued
            signals.loc[abs(z_score) < 0.1, 'position'] = 0       # Exit when z-score near zero

        elif strategy == 'z_rsi':
            # Z-Score + RSI momentum filter
            rsi1 = calculate_rsi_series(df1['close'], period=rsi_period)
            rsi2 = calculate_rsi_series(df2['close'], period=rsi_period)

            signals['rsi1'] = rsi1
            signals['rsi2'] = rsi2

            # Long spread: z<-threshold AND coin1 oversold AND coin2 overbought
            long_condition = (z_score < -z_threshold) & (rsi1 < 30) & (rsi2 > 70)
            # Short spread: z>threshold AND coin1 overbought AND coin2 oversold
            short_condition = (z_score > z_threshold) & (rsi1 > 70) & (rsi2 < 30)
            # Exit: z-score normalized OR both RSIs neutral
            exit_condition = (abs(z_score) < 0.1) | ((rsi1 > 40) & (rsi1 < 60) & (rsi2 > 40) & (rsi2 < 60))

            signals.loc[long_condition, 'position'] = 1
            signals.loc[short_condition, 'position'] = -1
            signals.loc[exit_condition, 'position'] = 0

        elif strategy == 'z_stoch':
            # Z-Score + Stochastic filter
            stoch1 = calculate_stochastic(df1['close'], period=rsi_period)
            stoch2 = calculate_stochastic(df2['close'], period=rsi_period)

            signals['stoch1'] = stoch1
            signals['stoch2'] = stoch2

            # Long spread: z<-threshold AND coin1 oversold AND coin2 overbought
            long_condition = (z_score < -z_threshold) & (stoch1 < 20) & (stoch2 > 80)
            # Short spread: z>threshold AND coin1 overbought AND coin2 oversold
            short_condition = (z_score > z_threshold) & (stoch1 > 80) & (stoch2 < 20)
            # Exit: z-score normalized
            exit_condition = abs(z_score) < 0.1

            signals.loc[long_condition, 'position'] = 1
            signals.loc[short_condition, 'position'] = -1
            signals.loc[exit_condition, 'position'] = 0

        elif strategy == 'divergence':
            # Price divergence detection with z-score confirmation
            # Calculate price momentum
            price_change1 = df1['close'].pct_change(periods=10)
            price_change2 = df2['close'].pct_change(periods=10)

            # Divergence: prices moving opposite directions
            divergence = (price_change1 * price_change2) < 0

            signals['divergence'] = divergence

            # Long when divergence + z<-threshold
            long_condition = divergence & (z_score < -z_threshold)
            # Short when divergence + z>threshold
            short_condition = divergence & (z_score > z_threshold)
            # Exit when z normalizes
            exit_condition = abs(z_score) < 0.1

            signals.loc[long_condition, 'position'] = 1
            signals.loc[short_condition, 'position'] = -1
            signals.loc[exit_condition, 'position'] = 0

        # Apply stop loss: exit if |z| > 3
        signals.loc[abs(z_score) > 3, 'position'] = 0

        # Forward fill positions (hold until signal changes)
        signals['position'] = signals['position'].replace(0, np.nan).ffill().fillna(0)

        return signals

    def _simulate_trades(self, signals: pd.DataFrame, df1: pd.DataFrame, df2: pd.DataFrame):
        """Simulate trades with transaction costs."""
        POSITION_SIZE = 10000  # $10k per leg
        TRANSACTION_COST = 0.0005  # 0.05% per leg (Hyperliquid maker fee)

        trades = []
        equity_curve = []
        current_position = 0
        entry_price1 = 0
        entry_price2 = 0
        entry_time = None
        cash = 0  # Track cumulative P&L

        for i, (timestamp, row) in enumerate(signals.iterrows()):
            position = row['position']
            # Ensure we get scalar values (handle potential Series from duplicate indices)
            price1_val = df1.loc[timestamp, 'close']
            price2_val = df2.loc[timestamp, 'close']
            price1 = price1_val.iloc[0] if isinstance(price1_val, pd.Series) else price1_val
            price2 = price2_val.iloc[0] if isinstance(price2_val, pd.Series) else price2_val

            # Position change detected
            if position != current_position:
                # Close existing position if any
                if current_position != 0:
                    # Calculate P&L
                    if current_position == 1:  # Long spread
                        pnl1 = POSITION_SIZE * (price1 - entry_price1) / entry_price1
                        pnl2 = -POSITION_SIZE * (price2 - entry_price2) / entry_price2
                    else:  # Short spread
                        pnl1 = -POSITION_SIZE * (price1 - entry_price1) / entry_price1
                        pnl2 = POSITION_SIZE * (price2 - entry_price2) / entry_price2

                    # Subtract exit costs
                    exit_costs = 2 * POSITION_SIZE * TRANSACTION_COST  # Both legs
                    total_pnl = pnl1 + pnl2 - exit_costs

                    cash += total_pnl

                    # Record trade
                    trade_duration = (timestamp - entry_time).total_seconds() / 3600  # Hours
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': timestamp,
                        'duration_hours': trade_duration,
                        'position': 'long' if current_position == 1 else 'short',
                        'entry_price1': entry_price1,
                        'entry_price2': entry_price2,
                        'exit_price1': price1,
                        'exit_price2': price2,
                        'pnl': total_pnl,
                        'z_score_entry': signals.loc[entry_time, 'z_score'],
                        'z_score_exit': row['z_score']
                    })

                    current_position = 0

                # Open new position if signal is not 0
                if position != 0:
                    entry_price1 = price1
                    entry_price2 = price2
                    entry_time = timestamp
                    current_position = position

                    # Subtract entry costs
                    entry_costs = 2 * POSITION_SIZE * TRANSACTION_COST  # Both legs
                    cash -= entry_costs

            # Record equity curve
            equity_curve.append({
                'timestamp': timestamp,
                'equity': cash
            })

        return trades, pd.DataFrame(equity_curve)

    def _calculate_metrics(self, trades: list, equity_curve: pd.DataFrame) -> dict:
        """Calculate performance metrics."""
        if not trades:
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'total_trades': 0,
                'profitable_trades': 0,
                'avg_trade_duration': 0.0,
                'avg_profit_per_trade': 0.0
            }

        trades_df = pd.DataFrame(trades)

        # Total return
        final_equity = equity_curve['equity'].iloc[-1]
        total_return = (final_equity / 20000) * 100  # Initial capital = 2 x $10k

        # Win rate
        profitable = (trades_df['pnl'] > 0).sum()
        win_rate = (profitable / len(trades_df)) * 100

        # Average trade duration (convert hours to days)
        avg_duration = trades_df['duration_hours'].mean() / 24

        # Average profit per trade
        avg_profit = trades_df['pnl'].mean()

        # Max drawdown
        equity_curve['cummax'] = equity_curve['equity'].cummax()
        equity_curve['drawdown'] = (equity_curve['equity'] - equity_curve['cummax']) / 20000 * 100
        max_drawdown = equity_curve['drawdown'].min()

        # Sharpe ratio (annualized)
        if len(trades_df) > 1:
            returns = trades_df['pnl'] / 20000  # Returns as fraction
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        return {
            'total_return': float(total_return),
            'sharpe_ratio': float(sharpe_ratio),
            'max_drawdown': float(max_drawdown),
            'win_rate': float(win_rate),
            'total_trades': len(trades_df),
            'profitable_trades': int(profitable),
            'avg_trade_duration': float(avg_duration),
            'avg_profit_per_trade': float(avg_profit)
        }

    @pyqtSlot(str, str, str, str, str)
    def optimizeParameters(self, coin1: str, coin2: str, start_date: str, end_date: str, timeframe: str = "1hour"):
        """
        Run grid search optimization to find best parameters.

        Args:
            coin1: First coin symbol
            coin2: Second coin symbol
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            timeframe: Granularity ('5min', '1hour', '4hour')
        """
        if self._is_running:
            self.errorOccurred.emit("Optimization already running")
            return

        self._is_running = True
        self.isRunningChanged.emit()
        self.backtestStarted.emit()

        try:
            print(f"Optimizing parameters for {coin1}/{coin2}")

            # Fetch data once
            df1, df2 = self._fetch_ohlcv_data(coin1, coin2, start_date, end_date, timeframe)
            if df1 is None or df2 is None:
                raise ValueError("Insufficient data for optimization")

            # Grid search parameters
            z_thresholds = [1.5, 2.0, 2.5, 3.0]
            rsi_periods = [10, 14, 20]
            window_sizes = [20, 30, 40]
            strategies = ['z_rsi', 'pure_z', 'z_stoch']

            total_combinations = len(z_thresholds) * len(rsi_periods) * len(window_sizes) * len(strategies)
            current_combo = 0
            best_sharpe = -999
            best_params = {}

            # Grid search
            for strategy in strategies:
                for z_thresh in z_thresholds:
                    for rsi_period in rsi_periods:
                        for window_size in window_sizes:
                            current_combo += 1
                            progress = int((current_combo / total_combinations) * 100)
                            self.backtestProgress.emit(progress)

                            try:
                                # Run backtest with these parameters
                                signals = self._generate_signals(df1, df2, strategy, z_thresh, rsi_period, window_size)
                                trades, equity_curve = self._simulate_trades(signals, df1, df2)
                                metrics = self._calculate_metrics(trades, equity_curve)

                                # Track best by Sharpe ratio
                                if metrics['sharpe_ratio'] > best_sharpe:
                                    best_sharpe = metrics['sharpe_ratio']
                                    best_params = {
                                        'strategy': strategy,
                                        'z_threshold': z_thresh,
                                        'rsi_period': rsi_period,
                                        'window_size': window_size,
                                        'metrics': metrics
                                    }
                            except Exception as e:
                                print(f"Error testing params: {e}")
                                continue

            # Store best results
            if best_params:
                self._results = {
                    'pair': f"{coin1}/{coin2}",
                    'optimized': True,
                    'strategy': best_params['strategy'],
                    'z_threshold': best_params['z_threshold'],
                    'rsi_period': best_params['rsi_period'],
                    'window_size': best_params['window_size'],
                    'total_return': best_params['metrics']['total_return'],
                    'sharpe_ratio': best_params['metrics']['sharpe_ratio'],
                    'max_drawdown': best_params['metrics']['max_drawdown'],
                    'win_rate': best_params['metrics']['win_rate'],
                    'total_trades': best_params['metrics']['total_trades'],
                    'profitable_trades': best_params['metrics']['profitable_trades'],
                    'avg_trade_duration': best_params['metrics']['avg_trade_duration'],
                    'avg_profit_per_trade': best_params['metrics']['avg_profit_per_trade'],
                }
                print(f"Best params: Strategy={best_params['strategy']}, Z={best_params['z_threshold']}, "
                      f"RSI={best_params['rsi_period']}, Window={best_params['window_size']}, "
                      f"Sharpe={best_sharpe:.2f}")
            else:
                raise ValueError("No valid parameter combinations found")

            self.resultsChanged.emit()
            self.backtestComplete.emit()

        except Exception as e:
            error_msg = f"Error optimizing parameters: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.errorOccurred.emit(error_msg)

        finally:
            self._is_running = False
            self.isRunningChanged.emit()

    @pyqtSlot(str, str, str)
    def updateAvailableData(self, coin1: str, coin2: str, timeframe: str):
        """Check available data for the given pair and timeframe."""
        print(f"[Backtest] Checking data availability for {coin1}/{coin2} ({timeframe})")

        if not coin1 or not coin2:
            print(f"[Backtest] Empty coin fields, returning early")
            self._data_available = False
            self._data_start_date = ""
            self._data_end_date = ""
            self._data_point_count = 0
            self.dataAvailableChanged.emit()
            self.dataStartDateChanged.emit()
            self.dataEndDateChanged.emit()
            self.dataPointCountChanged.emit()
            return

        try:
            with self.db.get_session() as session:
                # Check total count first
                total_count1 = session.query(OHLCVData).filter(
                    OHLCVData.coin_id == coin1,
                    OHLCVData.granularity == timeframe
                ).count()

                print(f"[Backtest] {coin1} has {total_count1} candles at {timeframe} granularity")

                # Get date range for coin1
                query1_asc = session.query(
                    OHLCVData.timestamp
                ).filter(
                    OHLCVData.coin_id == coin1,
                    OHLCVData.granularity == timeframe
                ).order_by(OHLCVData.timestamp.asc())

                query1_desc = session.query(
                    OHLCVData.timestamp
                ).filter(
                    OHLCVData.coin_id == coin1,
                    OHLCVData.granularity == timeframe
                ).order_by(OHLCVData.timestamp.desc())

                first1 = query1_asc.first()
                last1 = query1_desc.first()

                print(f"[Backtest] {coin1} data range: {first1} to {last1}")

                # Check total count for coin2
                total_count2 = session.query(OHLCVData).filter(
                    OHLCVData.coin_id == coin2,
                    OHLCVData.granularity == timeframe
                ).count()

                print(f"[Backtest] {coin2} has {total_count2} candles at {timeframe} granularity")

                # Get date range for coin2
                query2_asc = session.query(
                    OHLCVData.timestamp
                ).filter(
                    OHLCVData.coin_id == coin2,
                    OHLCVData.granularity == timeframe
                ).order_by(OHLCVData.timestamp.asc())

                query2_desc = session.query(
                    OHLCVData.timestamp
                ).filter(
                    OHLCVData.coin_id == coin2,
                    OHLCVData.granularity == timeframe
                ).order_by(OHLCVData.timestamp.desc())

                first2 = query2_asc.first()
                last2 = query2_desc.first()

                print(f"[Backtest] {coin2} data range: {first2} to {last2}")

                if first1 and last1 and first2 and last2:
                    # Use overlapping range
                    start_date = max(first1[0], first2[0])
                    end_date = min(last1[0], last2[0])

                    # Count available candles
                    count_query = session.query(OHLCVData).filter(
                        OHLCVData.coin_id == coin1,
                        OHLCVData.granularity == timeframe,
                        OHLCVData.timestamp >= start_date,
                        OHLCVData.timestamp <= end_date
                    )
                    count = count_query.count()

                    print(f"[Backtest] Overlapping range: {start_date} to {end_date}, count: {count}")

                    if count >= 50 and start_date < end_date:  # Need at least 50 candles for meaningful backtest
                        self._data_available = True
                        self._data_start_date = start_date.strftime('%Y-%m-%d')
                        self._data_end_date = end_date.strftime('%Y-%m-%d')
                        self._data_point_count = count
                        print(f"[Backtest] ✓ Data available: {self._data_start_date} to {self._data_end_date} ({count} candles)")
                    else:
                        self._data_available = False
                        self._data_start_date = ""
                        self._data_end_date = ""
                        self._data_point_count = 0
                        print(f"[Backtest] ✗ Insufficient data (count={count}, valid_range={start_date < end_date})")
                        print(f"[Backtest] 💡 Click 'Force Refresh' in the status bar to populate database with historical data")
                else:
                    # Check if data exists at any granularity
                    all_gran_query1 = session.query(OHLCVData).filter(OHLCVData.coin_id == coin1)
                    all_gran_query2 = session.query(OHLCVData).filter(OHLCVData.coin_id == coin2)
                    count1 = all_gran_query1.count()
                    count2 = all_gran_query2.count()
                    print(f"[Backtest] ✗ No data found for {timeframe}. {coin1} has {count1} total candles, {coin2} has {count2} total candles across all granularities")
                    print(f"[Backtest] 💡 Click 'Force Refresh' in the status bar to populate database with historical data")

                    self._data_available = False
                    self._data_start_date = ""
                    self._data_end_date = ""
                    self._data_point_count = 0

        except Exception as e:
            print(f"[Backtest] Error checking available data: {e}")
            import traceback
            traceback.print_exc()
            self._data_available = False
            self._data_start_date = ""
            self._data_end_date = ""
            self._data_point_count = 0

        self.dataAvailableChanged.emit()
        self.dataStartDateChanged.emit()
        self.dataEndDateChanged.emit()
        self.dataPointCountChanged.emit()

    @pyqtSlot()
    def cancel(self):
        """Cancel running backtest."""
        if self._is_running:
            # TODO: Implement cancellation logic
            self._is_running = False
            self.isRunningChanged.emit()
            print("Backtest cancelled")
