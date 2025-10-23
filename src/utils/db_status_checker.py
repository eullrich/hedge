"""Database status checker for candle data freshness and completeness."""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from ..database import DatabaseManager


class DatabaseStatusChecker:
    """Check database status for candle data freshness and completeness."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize checker with database manager."""
        self.db = db_manager

    def check_status(self) -> Dict[str, Any]:
        """
        Check comprehensive database status.

        Returns:
            Dict with status information:
            - is_fresh: bool (True if all data is up to date)
            - summary: str (human-readable summary)
            - details: dict with detailed stats
            - stale_coins: list of coins with stale data
            - needs_pruning: bool (True if old data exists)
        """
        with self.db.get_session() as session:
            # Check latest candle timestamps
            latest_query = text("""
                SELECT
                    coin_id,
                    granularity,
                    MAX(timestamp) as latest_candle,
                    COUNT(*) as candle_count,
                    MIN(timestamp) as oldest_candle,
                    ROUND((JULIANDAY('now') - JULIANDAY(MAX(timestamp))) * 24, 2) as hours_stale
                FROM ohlcv_data
                GROUP BY coin_id, granularity
                ORDER BY coin_id, granularity
            """)
            latest_results = session.execute(latest_query).fetchall()

            # Check for stale data (data older than expected)
            # Use 'localtime' instead of 'now' to match how timestamps are stored
            stale_query = text("""
                SELECT
                    coin_id,
                    granularity,
                    MAX(timestamp) as latest,
                    ROUND((JULIANDAY(datetime('now', 'localtime')) - JULIANDAY(MAX(timestamp))) * 24, 2) as hours_old
                FROM ohlcv_data
                GROUP BY coin_id, granularity
                HAVING
                    (granularity = '5min' AND hours_old > 1) OR
                    (granularity = '1hour' AND hours_old > 4) OR
                    (granularity = '4hour' AND hours_old > 8)
            """)
            stale_results = session.execute(stale_query).fetchall()

            # Check for data that needs pruning
            prune_query = text("""
                SELECT
                    granularity,
                    COUNT(*) as old_candles_to_prune
                FROM ohlcv_data
                WHERE
                    (granularity = '5min' AND timestamp < datetime('now', '-1 day')) OR
                    (granularity = '1hour' AND timestamp < datetime('now', '-7 days')) OR
                    (granularity = '4hour' AND timestamp < datetime('now', '-90 days'))
                GROUP BY granularity
            """)
            prune_results = session.execute(prune_query).fetchall()

            # Get total candle count and coin count
            total_query = text("""
                SELECT
                    COUNT(*) as total_candles,
                    COUNT(DISTINCT coin_id) as total_coins
                FROM ohlcv_data
            """)
            total_result = session.execute(total_query).fetchone()

            # Check last update log
            last_update = self.db.get_latest_update_log(session, update_type='ohlcv')

        # Process results
        total_candles = total_result[0] if total_result else 0
        total_coins = total_result[1] if total_result else 0

        stale_coins = [
            {
                'coin_id': row[0],
                'granularity': row[1],
                'latest': row[2],
                'hours_old': float(row[3])
            }
            for row in stale_results
        ]

        needs_pruning = len(prune_results) > 0
        prune_counts = {row[0]: row[1] for row in prune_results}

        # Determine freshness
        is_fresh = len(stale_coins) == 0

        # Build summary
        if is_fresh:
            summary = f"✅ Database up to date ({total_coins} coins, {total_candles:,} candles)"
        else:
            stale_count = len(set(c['coin_id'] for c in stale_coins))
            summary = f"⚠️ {stale_count} coins with stale data"

        # Add last update info
        if last_update:
            time_since = datetime.now() - last_update.started_at
            hours = int(time_since.total_seconds() / 3600)
            if hours < 1:
                mins = int(time_since.total_seconds() / 60)
                update_str = f"{mins}m ago"
            else:
                update_str = f"{hours}h ago"
            summary += f" | Updated {update_str}"

        return {
            'is_fresh': is_fresh,
            'summary': summary,
            'total_coins': total_coins,
            'total_candles': total_candles,
            'stale_coins': stale_coins,
            'needs_pruning': needs_pruning,
            'prune_counts': prune_counts,
            'last_update': last_update.started_at if last_update else None,
            'last_update_status': last_update.status if last_update else None,
            'last_update_coins_updated': last_update.coins_updated if last_update else 0,
            'last_update_coins_failed': last_update.coins_failed if last_update else 0,
        }

    def get_coin_status(self, coin_id: str) -> Dict[str, Any]:
        """
        Get status for a specific coin.

        Args:
            coin_id: Coin ID to check

        Returns:
            Dict with coin-specific status
        """
        with self.db.get_session() as session:
            query = text("""
                SELECT
                    granularity,
                    COUNT(*) as candle_count,
                    MIN(timestamp) as oldest,
                    MAX(timestamp) as latest,
                    ROUND((JULIANDAY('now') - JULIANDAY(MAX(timestamp))) * 24, 2) as hours_stale
                FROM ohlcv_data
                WHERE coin_id = :coin_id
                GROUP BY granularity
            """)
            results = session.execute(query, {'coin_id': coin_id}).fetchall()

        if not results:
            return {
                'exists': False,
                'coin_id': coin_id,
                'message': f"No data found for {coin_id}"
            }

        granularities = {}
        for row in results:
            gran = row[0]
            granularities[gran] = {
                'count': row[1],
                'oldest': row[2],
                'latest': row[3],
                'hours_stale': float(row[4]),
                'is_stale': self._is_stale(gran, float(row[4]))
            }

        return {
            'exists': True,
            'coin_id': coin_id,
            'granularities': granularities
        }

    def _is_stale(self, granularity: str, hours_old: float) -> bool:
        """Check if data is stale based on granularity."""
        thresholds = {
            '5min': 1,    # 1 hour
            '1hour': 4,   # 4 hours
            '4hour': 8,   # 8 hours
        }
        return hours_old > thresholds.get(granularity, 24)

    def get_status_emoji(self) -> str:
        """Get a quick emoji status indicator."""
        status = self.check_status()
        if status['is_fresh']:
            return "✅"
        elif len(status['stale_coins']) < 5:
            return "⚠️"
        else:
            return "❌"

    def get_short_status(self) -> str:
        """Get a concise status string for status bar."""
        status = self.check_status()
        return status['summary']
