"""Service for calculating basket prices and ratios from constituent coins."""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import DatabaseManager
from src.database.ohlcv_models import CoinBasket, CoinBasketMember


class BasketCalculator:
    """Calculate basket prices and ratios from constituent coins."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_basket_members(self, basket_id: int, session) -> List[Tuple[str, float]]:
        """
        Get basket members with their weights.

        Args:
            basket_id: ID of the basket
            session: Database session

        Returns:
            List of (coin_id, weight) tuples
        """
        members = session.query(CoinBasketMember).filter(
            CoinBasketMember.basket_id == basket_id
        ).all()

        return [(m.coin_id, m.weight) for m in members]

    def calculate_basket_price(
        self,
        session,
        basket_id: int,
        start_date: datetime,
        end_date: datetime,
        granularity: str = '1hour'
    ) -> Optional[pd.DataFrame]:
        """
        Calculate time-series basket price from constituent coins.

        Args:
            session: Database session
            basket_id: ID of the basket
            start_date: Start date for OHLCV data
            end_date: End date for OHLCV data
            granularity: Data granularity ('5min', '1hour', '4hour')

        Returns:
            DataFrame with timestamp index and OHLCV columns, or None if insufficient data
        """
        # Get basket and members
        basket = session.query(CoinBasket).filter(CoinBasket.id == basket_id).first()
        if not basket:
            print(f"❌ Basket {basket_id} not found")
            return None

        members = self.get_basket_members(basket_id, session)
        if not members:
            print(f"❌ Basket {basket_id} has no members")
            return None

        # Fetch OHLCV data for all basket members
        coin_dataframes = {}
        for coin_id, weight in members:
            coin_data = self.db.get_ohlcv_data(
                session,
                coin_id=coin_id,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity
            )

            if not coin_data:
                print(f"⚠️  No data for {coin_id} in basket {basket.name}")
                continue

            df = pd.DataFrame([{
                'timestamp': c.timestamp,
                'open': c.open,
                'high': c.high,
                'low': c.low,
                'close': c.close,
                'volume': c.volume
            } for c in coin_data])

            df.set_index('timestamp', inplace=True)

            # Remove duplicate timestamps (keep last)
            df = df[~df.index.duplicated(keep='last')]

            coin_dataframes[coin_id] = (df, weight)

        if not coin_dataframes:
            print(f"❌ No data available for any members of basket {basket.name}")
            return None

        # Align timestamps (inner join to only keep matching timestamps)
        all_timestamps = None
        for coin_id, (df, _) in coin_dataframes.items():
            if all_timestamps is None:
                all_timestamps = set(df.index)
            else:
                all_timestamps = all_timestamps.intersection(set(df.index))

        if not all_timestamps:
            print(f"❌ No overlapping timestamps for basket {basket.name}")
            return None

        aligned_timestamps = sorted(list(all_timestamps))

        # Calculate weighted basket OHLCV
        basket_df = pd.DataFrame(index=aligned_timestamps)

        # Normalize weights
        if basket.weighting_method == 'equal':
            # Equal weighting
            total_weight = len(coin_dataframes)
            normalized_weights = {coin_id: 1.0 / total_weight for coin_id in coin_dataframes.keys()}
        else:
            # Use provided weights
            total_weight = sum(weight for _, weight in coin_dataframes.values())
            normalized_weights = {coin_id: weight / total_weight for coin_id, (_, weight) in coin_dataframes.items()}

        # Calculate weighted average for each OHLCV field
        for field in ['open', 'high', 'low', 'close']:
            basket_df[field] = 0.0
            for coin_id, (df, _) in coin_dataframes.items():
                weight = normalized_weights[coin_id]
                basket_df[field] += df.loc[aligned_timestamps, field] * weight

        # Volume is sum of all members (not weighted average)
        basket_df['volume'] = 0.0
        for coin_id, (df, _) in coin_dataframes.items():
            basket_df['volume'] += df.loc[aligned_timestamps, 'volume']

        return basket_df

    def calculate_basket_ratio(
        self,
        session,
        numerator_basket_id: int,
        denominator_basket_id: int,
        start_date: datetime,
        end_date: datetime,
        granularity: str = '1hour'
    ) -> Optional[pd.Series]:
        """
        Calculate ratio between two baskets (or basket vs single coin).

        Args:
            session: Database session
            numerator_basket_id: ID of numerator basket
            denominator_basket_id: ID of denominator basket
            start_date: Start date
            end_date: End date
            granularity: Data granularity

        Returns:
            Series with timestamp index and ratio values, or None if insufficient data
        """
        # Calculate basket prices
        numerator_df = self.calculate_basket_price(
            session, numerator_basket_id, start_date, end_date, granularity
        )
        denominator_df = self.calculate_basket_price(
            session, denominator_basket_id, start_date, end_date, granularity
        )

        if numerator_df is None or denominator_df is None:
            return None

        # Align timestamps
        aligned_df = numerator_df.join(
            denominator_df,
            how='inner',
            lsuffix='_num',
            rsuffix='_denom'
        )

        if len(aligned_df) == 0:
            print("❌ No overlapping timestamps between baskets")
            return None

        # Calculate ratio using close prices
        ratio = aligned_df['close_num'] / aligned_df['close_denom']

        return ratio

    def create_basket_from_coins(
        self,
        session,
        name: str,
        coin_ids: List[str],
        weights: Optional[List[float]] = None,
        weighting_method: str = 'equal',
        description: str = ''
    ) -> Optional[int]:
        """
        Create a new basket from a list of coins.

        Args:
            session: Database session
            name: Basket name
            coin_ids: List of coin IDs
            weights: Optional list of weights (must match coin_ids length)
            weighting_method: 'equal' or 'market_cap'
            description: Optional description

        Returns:
            Basket ID if successful, None otherwise
        """
        try:
            # Check if basket name already exists
            existing = session.query(CoinBasket).filter(CoinBasket.name == name).first()
            if existing:
                print(f"⚠️  Basket '{name}' already exists")
                return existing.id

            # Create basket
            basket = CoinBasket(
                name=name,
                description=description,
                weighting_method=weighting_method
            )
            session.add(basket)
            session.flush()  # Get basket ID

            # Add members
            if weights is None:
                weights = [1.0] * len(coin_ids)
            elif len(weights) != len(coin_ids):
                print(f"❌ Weight count ({len(weights)}) doesn't match coin count ({len(coin_ids)})")
                session.rollback()
                return None

            for coin_id, weight in zip(coin_ids, weights):
                member = CoinBasketMember(
                    basket_id=basket.id,
                    coin_id=coin_id.upper(),
                    weight=weight
                )
                session.add(member)

            session.commit()
            print(f"✅ Created basket '{name}' with {len(coin_ids)} coins")
            return basket.id

        except Exception as e:
            print(f"❌ Error creating basket: {e}")
            session.rollback()
            return None

    def get_basket_display_name(self, session, basket_id: int) -> str:
        """
        Get a display-friendly name for a basket showing its composition.

        Args:
            session: Database session
            basket_id: ID of the basket

        Returns:
            Display name like "BTC+ETH+SOL" or basket name
        """
        basket = session.query(CoinBasket).filter(CoinBasket.id == basket_id).first()
        if not basket:
            return f"Basket#{basket_id}"

        members = self.get_basket_members(basket_id, session)
        if not members:
            return basket.name

        # Return coin composition if basket has 5 or fewer members
        if len(members) <= 5:
            coin_ids = [coin_id for coin_id, _ in members]
            return '+'.join(coin_ids)
        else:
            return f"{basket.name} ({len(members)} coins)"
