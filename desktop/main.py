#!/usr/bin/env python3
"""
Hedge Desktop - Full QML Version
Professional desktop application built with Qt Quick (QML)
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QUrl

from desktop.src.qml_bridge.watchlist_model import WatchlistModel
from desktop.src.qml_bridge.discovery_model import DiscoveryModel
from desktop.src.qml_bridge.analysis_model import AnalysisModel
from desktop.src.qml_bridge.backtest_model import BacktestModel
from desktop.src.qml_bridge.market_data_model import MarketDataModel
from src.database import DatabaseManager
from src.api import HyperliquidClient
from src.utils.db_status_checker import DatabaseStatusChecker
from src.services.data_updater import DataUpdater
import threading


def main():
    """Launch full QML application."""
    # Set Qt Quick Controls style to Material before creating QGuiApplication
    os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Material'
    os.environ['QT_QUICK_CONTROLS_MATERIAL_THEME'] = 'Dark'
    os.environ['QT_QUICK_CONTROLS_MATERIAL_VARIANT'] = 'Dense'  # Desktop optimized

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Hedge")
    app.setOrganizationName("HedgeTrading")
    app.setApplicationVersion("2.0.0")

    # Initialize backend
    db_manager = DatabaseManager()
    api_client = HyperliquidClient()  # Singleton - shared across app
    status_checker = DatabaseStatusChecker(db_manager)

    # DISABLED: Automatic update on startup (use Force Refresh button instead)
    # This avoids rate limiting issues and gives you control over when to update
    print("ℹ️  Automatic updates disabled - use 'Force Refresh' button to update data")

    def startup_update_DISABLED():
        try:
            # Check initial database status
            initial_status = status_checker.check_status()
            print(f"📊 Database status: {initial_status['summary']}")

            # Update status bar with initial status
            if root_objects := engine.rootObjects():
                root = root_objects[0]
                root.setStatus(initial_status['summary'])
                if initial_status['last_update']:
                    timestamp = initial_status['last_update'].strftime("%H:%M:%S")
                    root.setLastUpdate(timestamp)

            # Skip update if data is fresh (smart update)
            if initial_status['is_fresh']:
                print("✅ Data is fresh, skipping full update")
                print(f"   Last update: {initial_status['last_update']}")
                print(f"   Total: {initial_status['total_coins']} coins, {initial_status['total_candles']:,} candles")

                # Still calculate correlations if cache is stale/empty
                api_client = HyperliquidClient()
                updater = DataUpdater(api_client, db_manager)

                print(f"\n🔄 Checking correlation cache...")
                corr_result = updater.calculate_pairwise_correlations()
                print(f"✅ Correlation cache: {corr_result['pairs_calculated']} pairs")
                return

            # Data is stale - proceed with update
            stale_count = len(initial_status['stale_coins'])
            print(f"⚠️  {stale_count} coins have stale data, updating...")

            # Update status bar to show updating
            if root_objects := engine.rootObjects():
                root = root_objects[0]
                root.setStatus("🔄 Updating stale data...")

            api_client = HyperliquidClient()
            updater = DataUpdater(api_client, db_manager)

            # Step 1: Update OHLCV candle data for all tokens
            result = updater.update_ohlcv_for_all_tokens()

            # Check if API is down
            if result.get('api_down'):
                print("⚠️ API unavailable - using existing database")
                if root_objects := engine.rootObjects():
                    root = root_objects[0]
                    root.setStatus("⚠️ API down - using cached data")
                return

            print(f"✅ OHLCV update complete: {result['coins_updated']} tokens updated")

            # Step 2: Calculate pairwise correlations for discovery (instant scans)
            print(f"\n🔄 Calculating pairwise correlations for common reference coins...")
            corr_result = updater.calculate_pairwise_correlations()
            print(f"✅ Correlation cache complete: {corr_result['pairs_calculated']} pairs calculated")

            # Update status bar with final status
            final_status = status_checker.check_status()
            if root_objects := engine.rootObjects():
                root = root_objects[0]
                root.setStatus(final_status['summary'])
                timestamp = datetime.now().strftime("%H:%M:%S")
                root.setLastUpdate(timestamp)

        except Exception as e:
            print(f"⚠️  Startup update error: {e}")
            import traceback
            traceback.print_exc()

            # Update status bar with error
            if root_objects := engine.rootObjects():
                root = root_objects[0]
                root.setStatus(f"❌ Update error: {str(e)[:50]}")

    # DISABLED: Run update in background thread so UI loads immediately
    # update_thread = threading.Thread(target=startup_update_DISABLED, daemon=True)
    # update_thread.start()
    # Instead, just show current status
    initial_status = status_checker.check_status()
    print(f"📊 Database status: {initial_status['summary']}")

    # Create QML engine
    engine = QQmlApplicationEngine()

    # Create and expose models to QML
    watchlist_model = WatchlistModel(db_manager, api_client)
    discovery_model = DiscoveryModel(db_manager, api_client, watchlist_model)
    analysis_model = AnalysisModel(db_manager, api_client)
    backtest_model = BacktestModel(db_manager, api_client)
    market_data_model = MarketDataModel(api_client)

    engine.rootContext().setContextProperty("watchlistModel", watchlist_model)
    engine.rootContext().setContextProperty("discoveryModel", discovery_model)
    engine.rootContext().setContextProperty("analysisModel", analysis_model)
    engine.rootContext().setContextProperty("backtestModel", backtest_model)
    engine.rootContext().setContextProperty("marketDataModel", market_data_model)

    # Load main QML application
    qml_file = Path(__file__).parent / "qml" / "MainApp.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        print("❌ Error loading QML")
        return -1

    # Get root window
    root = engine.rootObjects()[0]

    # Set initial status from database
    final_status = status_checker.check_status()
    root.setStatus(final_status['summary'] + " | Use 'Force Refresh' to update")
    if final_status.get('last_update'):
        timestamp = final_status['last_update'].strftime("%H:%M:%S")
        root.setLastUpdate(timestamp)

    # Connect signals
    def on_refresh_data():
        print("🔄 Refreshing data...")
        try:
            root.setStatus("🔄 Updating database...")

            api_client = HyperliquidClient()
            updater = DataUpdater(api_client, db_manager)
            result = updater.update_ohlcv_for_all_tokens()

            # Wait for write queue to finish before checking status
            if db_manager.write_queue:
                queue_depth = db_manager.write_queue.get_queue_depth()
                if queue_depth > 0:
                    print(f"⏳ Waiting for {queue_depth} queued writes to complete...")
                    db_manager.write_queue.wait(timeout=120)
                    print("✅ Write queue drained")

            # Check final status and update UI
            final_status = status_checker.check_status()
            timestamp = datetime.now().strftime("%H:%M:%S")
            root.setLastUpdate(timestamp)
            root.setStatus(final_status['summary'])

            watchlist_model.refresh()
            print(f"✅ Updated {result['coins_updated']} tokens")
        except Exception as e:
            print(f"❌ Error: {e}")
            root.setStatus(f"❌ Error: {str(e)[:60]}")

    def on_force_refresh_data():
        """Force full data refresh, ignoring freshness check."""
        print("🔄 Force refresh requested...")
        try:
            root.setStatus("🔄 Force updating all data...")

            api_client = HyperliquidClient()
            updater = DataUpdater(api_client, db_manager)

            # Force update by directly calling update method (bypasses freshness check)
            result = updater.update_ohlcv_for_all_tokens()

            # Wait for write queue to finish before checking status
            if db_manager.write_queue:
                queue_depth = db_manager.write_queue.get_queue_depth()
                if queue_depth > 0:
                    print(f"⏳ Waiting for {queue_depth} queued writes to complete...")
                    db_manager.write_queue.wait(timeout=120)
                    print("✅ Write queue drained")

            # Check final status and update UI
            final_status = status_checker.check_status()
            timestamp = datetime.now().strftime("%H:%M:%S")
            root.setLastUpdate(timestamp)
            root.setStatus(final_status['summary'])

            watchlist_model.refresh()
            print(f"✅ Force refresh complete: {result['coins_updated']} tokens updated, {result['coins_failed']} failed")
            if result.get('errors') and len(result['errors']) > 0:
                print(f"⚠️ First 5 errors: {result['errors'][:5]}")
        except Exception as e:
            print(f"❌ Error: {e}")
            root.setStatus(f"❌ Error: {str(e)[:60]}")

    def on_pair_selected(coin1: str, coin2: str):
        print(f"🔍 Pair selected: {coin1}/{coin2}")

    root.refreshData.connect(on_refresh_data)
    root.forceRefreshData.connect(on_force_refresh_data)
    root.pairSelected.connect(on_pair_selected)

    print("=" * 70)
    print("Hedge - Crypto Pair Trading Analysis (Qt Quick/QML)")
    print("=" * 70)
    print("Material Design Dark theme")
    print("Dense variant (desktop optimized)")
    print("Watchlist - View saved pairs")
    print("Discovery - Find new trading pairs")
    print("Analysis - Deep dive into pair analysis")
    print("Backtest - Test strategies")
    print("=" * 70)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
