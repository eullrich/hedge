"""Correlation and statistical metrics."""
import numpy as np


def calculate_correlation(prices1: np.ndarray, prices2: np.ndarray) -> float:
    """Calculate correlation coefficient between two price series."""
    if len(prices1) < 2 or len(prices2) < 2:
        return 0.0

    if len(prices1) != len(prices2):
        min_len = min(len(prices1), len(prices2))
        prices1 = prices1[-min_len:]
        prices2 = prices2[-min_len:]

    correlation = np.corrcoef(prices1, prices2)[0, 1]
    return float(correlation) if not np.isnan(correlation) else 0.0
