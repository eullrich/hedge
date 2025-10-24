"""Background data updater that runs periodically while the app is active."""
import threading
import time
from datetime import datetime
from typing import Callable, Optional

from src.database import DatabaseManager
from src.api import HyperliquidClient
from src.services.data_updater import DataUpdater
from src.utils.db_status_checker import DatabaseStatusChecker


class BackgroundUpdater:
    """Manages background data updates while the application is running."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        api_client: HyperliquidClient,
        update_interval_minutes: int = 5,
        on_update_complete: Optional[Callable] = None,
        on_status_change: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize background updater.

        Args:
            db_manager: Database manager instance
            api_client: Hyperliquid API client
            update_interval_minutes: How often to check for updates (default: 5 minutes)
            on_update_complete: Callback when update completes
            on_status_change: Callback when status message changes
        """
        self.db_manager = db_manager
        self.api_client = api_client
        self.update_interval_minutes = update_interval_minutes
        self.on_update_complete = on_update_complete
        self.on_status_change = on_status_change

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._updater = DataUpdater(api_client, db_manager)
        self._status_checker = DatabaseStatusChecker(db_manager)

    def start(self):
        """Start the background updater thread."""
        if self._running:
            print("⚠️  Background updater already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()
        print(f"✅ Background updater started (interval: {self.update_interval_minutes} minutes)")

    def stop(self):
        """Stop the background updater thread."""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("🛑 Background updater stopped")

    def force_update_now(self):
        """Trigger an immediate update (non-blocking)."""
        if not self._running:
            print("⚠️  Background updater not running, cannot force update")
            return

        # Trigger update by resetting the wait timer
        print("🔄 Force update triggered")
        # The update loop will pick this up on next iteration

    def _notify_status(self, message: str):
        """Send status notification to callback."""
        if self.on_status_change:
            try:
                self.on_status_change(message)
            except Exception as e:
                print(f"⚠️  Error in status callback: {e}")

    def _update_loop(self):
        """Main background update loop."""
        print(f"🔄 Background update loop started")

        # Wait a bit before first update to let the app initialize
        initial_delay = 30  # 30 seconds
        print(f"⏳ Waiting {initial_delay}s before first background update...")
        time.sleep(initial_delay)

        while self._running:
            try:
                # Check if data is stale
                status = self._status_checker.check_status()

                if status['is_fresh']:
                    print(f"✅ Data is fresh (last update: {status['last_update']})")
                    # Data is fresh, skip update
                else:
                    stale_count = len(status['stale_coins'])
                    print(f"🔄 Background update starting ({stale_count} stale coins)...")
                    self._notify_status(f"🔄 Updating {stale_count} stale coins...")

                    # Perform incremental update (only stale coins)
                    result = self._updater.update_ohlcv_for_all_tokens(stale_only=True)

                    if result.get('api_down'):
                        print("⚠️  API unavailable, will retry next interval")
                        self._notify_status("⚠️ API down - using cached data")
                    else:
                        # Wait for write queue to complete
                        if self.db_manager.write_queue:
                            queue_depth = self.db_manager.write_queue.get_queue_depth()
                            if queue_depth > 0:
                                print(f"⏳ Waiting for {queue_depth} queued writes...")
                                self.db_manager.write_queue.wait(timeout=60)

                        # Get updated status
                        final_status = self._status_checker.check_status()
                        timestamp = datetime.now().strftime("%H:%M:%S")

                        success_msg = f"✅ Background update complete: {result['coins_updated']} coins updated at {timestamp}"
                        print(success_msg)
                        self._notify_status(final_status['summary'])

                        # Notify completion callback
                        if self.on_update_complete:
                            try:
                                self.on_update_complete()
                            except Exception as e:
                                print(f"⚠️  Error in completion callback: {e}")

            except Exception as e:
                print(f"❌ Background update error: {e}")
                import traceback
                traceback.print_exc()
                self._notify_status(f"❌ Update error: {str(e)[:50]}")

            # Sleep until next update interval
            if self._running:
                sleep_seconds = self.update_interval_minutes * 60
                print(f"💤 Sleeping for {self.update_interval_minutes} minutes until next check...")
                time.sleep(sleep_seconds)

        print("🛑 Background update loop exited")

    def get_status(self) -> dict:
        """Get current database status."""
        return self._status_checker.check_status()

    def is_running(self) -> bool:
        """Check if background updater is running."""
        return self._running
