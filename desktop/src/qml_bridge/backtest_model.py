"""QML bridge for Backtesting functionality."""
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.database import DatabaseManager
from src.api import HyperliquidClient


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

    def __init__(self, db_manager: DatabaseManager, api_client: HyperliquidClient, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.api_client = api_client

        # Internal state
        self._is_running = False
        self._results = {}

    # Properties
    @pyqtProperty(bool, notify=isRunningChanged)
    def isRunning(self):
        return self._is_running

    @pyqtProperty('QVariantMap', notify=resultsChanged)
    def results(self):
        """Return backtest results as QVariantMap (dict)."""
        return self._results

    @pyqtSlot(str, str, str, str)
    def runBacktest(self, coin1: str, coin2: str, start_date: str, end_date: str):
        """
        Run backtest for a trading pair over a date range.

        Args:
            coin1: First coin symbol
            coin2: Second coin symbol
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
        """
        if self._is_running:
            self.errorOccurred.emit("Backtest already running")
            return

        self._is_running = True
        self.isRunningChanged.emit()
        self.backtestStarted.emit()

        try:
            # TODO: Implement actual backtest logic with Backtrader
            # For now, just create mock results
            print(f"Running backtest for {coin1}/{coin2} from {start_date} to {end_date}")

            # Simulate progress
            for i in range(0, 101, 10):
                self.backtestProgress.emit(i)

            # Mock results
            self._results = {
                'pair': f"{coin1}/{coin2}",
                'total_return': 15.3,
                'sharpe_ratio': 1.85,
                'max_drawdown': -8.2,
                'win_rate': 62.5,
                'total_trades': 48,
                'profitable_trades': 30,
            }
            self.resultsChanged.emit()
            self.backtestComplete.emit()

        except Exception as e:
            error_msg = f"Error running backtest: {e}"
            print(error_msg)
            self.errorOccurred.emit(error_msg)

        finally:
            self._is_running = False
            self.isRunningChanged.emit()

    @pyqtSlot()
    def cancel(self):
        """Cancel running backtest."""
        if self._is_running:
            # TODO: Implement cancellation logic
            self._is_running = False
            self.isRunningChanged.emit()
            print("Backtest cancelled")
