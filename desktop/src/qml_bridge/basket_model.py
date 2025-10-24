"""QML bridge for managing coin baskets."""
from PyQt6.QtCore import QAbstractListModel, Qt, pyqtSignal, pyqtSlot, QModelIndex
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.database import DatabaseManager
from src.database.ohlcv_models import CoinBasket, CoinBasketMember
from src.services.basket_calculator import BasketCalculator


class BasketModel(QAbstractListModel):
    """Qt model for exposing coin baskets to QML."""

    basketCreated = pyqtSignal(int, str)  # basket_id, name

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.calculator = BasketCalculator(db_manager)
        self._baskets: List[Dict[str, Any]] = []
        self.refresh()

    def rowCount(self, parent=QModelIndex()):
        """Return number of baskets."""
        return len(self._baskets)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return basket data."""
        if not index.isValid() or index.row() >= len(self._baskets):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return self._baskets[index.row()]

        return None

    def roleNames(self):
        """Return role names for QML."""
        return {
            Qt.ItemDataRole.DisplayRole: b'display',
        }

    @pyqtSlot()
    def refresh(self):
        """Refresh baskets from database."""
        self.beginResetModel()

        try:
            self._baskets = []

            with self.db.get_session() as session:
                baskets = session.query(CoinBasket).filter(
                    CoinBasket.is_active == True
                ).all()

                for basket in baskets:
                    # Get member count and coins
                    members = session.query(CoinBasketMember).filter(
                        CoinBasketMember.basket_id == basket.id
                    ).all()

                    member_coins = [m.coin_id for m in members]

                    self._baskets.append({
                        'id': basket.id,
                        'name': basket.name,
                        'description': basket.description or '',
                        'weighting_method': basket.weighting_method,
                        'member_count': len(members),
                        'member_coins': ','.join(member_coins),  # For QML
                        'created_at': basket.created_at.isoformat() if basket.created_at else ''
                    })

            print(f"📋 Loaded {len(self._baskets)} baskets")

        except Exception as e:
            print(f"❌ Error loading baskets: {e}")
            import traceback
            traceback.print_exc()

        self.endResetModel()

    @pyqtSlot(str, 'QVariantList', result=int)
    def createBasket(self, name: str, coin_ids: List[str]) -> int:
        """
        Create a new basket from coin IDs.

        Args:
            name: Basket name
            coin_ids: List of coin IDs

        Returns:
            Basket ID if successful, -1 otherwise
        """
        try:
            with self.db.get_session() as session:
                basket_id = self.calculator.create_basket_from_coins(
                    session=session,
                    name=name,
                    coin_ids=coin_ids,
                    weighting_method='equal',
                    description=f"Basket of {len(coin_ids)} coins"
                )

                if basket_id:
                    self.refresh()
                    self.basketCreated.emit(basket_id, name)
                    return basket_id

            return -1

        except Exception as e:
            print(f"❌ Error creating basket: {e}")
            import traceback
            traceback.print_exc()
            return -1

    @pyqtSlot(int, result=str)
    def getBasketDisplayName(self, basket_id: int) -> str:
        """Get display name for a basket."""
        try:
            with self.db.get_session() as session:
                return self.calculator.get_basket_display_name(session, basket_id)
        except Exception as e:
            print(f"❌ Error getting basket display name: {e}")
            return f"Basket#{basket_id}"

    @pyqtSlot(int, result='QVariantList')
    def getBasketMembers(self, basket_id: int) -> List[str]:
        """Get list of coin IDs in a basket."""
        try:
            with self.db.get_session() as session:
                members = self.calculator.get_basket_members(basket_id, session)
                return [coin_id for coin_id, _ in members]
        except Exception as e:
            print(f"❌ Error getting basket members: {e}")
            return []

    @pyqtSlot(int)
    def deleteBasket(self, basket_id: int):
        """Delete a basket."""
        try:
            with self.db.get_session() as session:
                basket = session.query(CoinBasket).filter(CoinBasket.id == basket_id).first()
                if basket:
                    basket.is_active = False
                    session.commit()
                    self.refresh()
                    print(f"✅ Deleted basket {basket_id}")
        except Exception as e:
            print(f"❌ Error deleting basket: {e}")
            import traceback
            traceback.print_exc()
