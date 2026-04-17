"""
Portfolio Optimizer - Constrained Portfolio Construction
Converts signals into portfolio weights with constraints
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from scipy.optimize import minimize


class PortfolioOptimizer:
    """
    Constructs portfolio weights from signals with constraints:
    - Long-only
    - Full investment (weights sum to 1)
    - Individual stock weight limits
    - Optional sector constraints
    """

    def __init__(
        self,
        max_stock_weight: float = 0.10,
        min_stock_weight: float = 0.0,
        max_sector_weight: Optional[float] = None
    ):
        """
        Args:
            max_stock_weight: Maximum weight per stock (default 10%)
            min_stock_weight: Minimum weight per stock (default 0%)
            max_sector_weight: Maximum weight per sector (optional)
        """
        self.max_stock_weight = max_stock_weight
        self.min_stock_weight = min_stock_weight
        self.max_sector_weight = max_sector_weight

    def optimize(
        self,
        signals: pd.DataFrame,
        method: str = 'top_n',
        n_stocks: int = 20,
        sector_col: Optional[str] = None
    ) -> pd.Series:
        """
        Optimize portfolio weights from signals

        Args:
            signals: DataFrame with columns [stock_code, signal, sector (optional)]
            method: Optimization method ('top_n', 'proportional', 'equal_weight')
            n_stocks: Number of stocks to hold (for top_n method)
            sector_col: Column name for sector constraints

        Returns:
            Series with stock_code as index and weights as values
        """
        if len(signals) == 0:
            return pd.Series(dtype=float)

        if method == 'top_n':
            weights = self._optimize_top_n(signals, n_stocks)
        elif method == 'proportional':
            weights = self._optimize_proportional(signals, n_stocks)
        elif method == 'equal_weight':
            weights = self._optimize_equal_weight(signals, n_stocks)
        else:
            raise ValueError(f"Unknown method: {method}")

        # Apply sector constraints if specified
        if sector_col and self.max_sector_weight:
            weights = self._apply_sector_constraints(
                weights,
                signals,
                sector_col
            )

        # Ensure constraints are met
        weights = self._enforce_constraints(weights)

        return weights

    def _optimize_top_n(
        self,
        signals: pd.DataFrame,
        n_stocks: int
    ) -> pd.Series:
        """
        Select top N stocks by signal, equal-weighted

        Args:
            signals: DataFrame with signal column
            n_stocks: Number of stocks to select

        Returns:
            Series of weights
        """
        # Sort by signal descending
        sorted_signals = signals.sort_values('signal', ascending=False)

        # Select top N
        top_n = sorted_signals.head(n_stocks)

        # Equal weight
        weights = pd.Series(
            1.0 / len(top_n),
            index=top_n['stock_code']
        )

        return weights

    def _optimize_proportional(
        self,
        signals: pd.DataFrame,
        n_stocks: int
    ) -> pd.Series:
        """
        Select top N stocks, weight proportional to signal strength

        Args:
            signals: DataFrame with signal column
            n_stocks: Number of stocks to select

        Returns:
            Series of weights
        """
        # Sort by signal descending
        sorted_signals = signals.sort_values('signal', ascending=False)

        # Select top N
        top_n = sorted_signals.head(n_stocks).copy()

        # Shift signals to be positive
        min_signal = top_n['signal'].min()
        if min_signal < 0:
            top_n['signal_shifted'] = top_n['signal'] - min_signal + 0.01
        else:
            top_n['signal_shifted'] = top_n['signal']

        # Proportional weights
        total_signal = top_n['signal_shifted'].sum()
        if total_signal < 1e-8:
            # Fall back to equal weight
            weights = pd.Series(
                1.0 / len(top_n),
                index=top_n['stock_code']
            )
        else:
            weights = pd.Series(
                top_n['signal_shifted'].values / total_signal,
                index=top_n['stock_code']
            )

        return weights

    def _optimize_equal_weight(
        self,
        signals: pd.DataFrame,
        n_stocks: int
    ) -> pd.Series:
        """
        Select top N stocks by signal, equal-weighted (same as top_n)

        Args:
            signals: DataFrame with signal column
            n_stocks: Number of stocks to select

        Returns:
            Series of weights
        """
        return self._optimize_top_n(signals, n_stocks)

    def _apply_sector_constraints(
        self,
        weights: pd.Series,
        signals: pd.DataFrame,
        sector_col: str
    ) -> pd.Series:
        """
        Apply sector weight constraints

        Args:
            weights: Current portfolio weights
            signals: DataFrame with sector information
            sector_col: Column name for sector

        Returns:
            Adjusted weights
        """
        if self.max_sector_weight is None:
            return weights

        # Merge weights with sector info
        df = pd.DataFrame({
            'stock_code': weights.index,
            'weight': weights.values
        })
        df = df.merge(
            signals[['stock_code', sector_col]],
            on='stock_code',
            how='left'
        )

        # Calculate sector weights
        sector_weights = df.groupby(sector_col)['weight'].sum()

        # Check for violations
        violations = sector_weights[sector_weights > self.max_sector_weight]

        if len(violations) == 0:
            return weights

        # Scale down overweight sectors
        for sector in violations.index:
            sector_mask = df[sector_col] == sector
            scale_factor = self.max_sector_weight / violations[sector]
            df.loc[sector_mask, 'weight'] *= scale_factor

        # Renormalize to sum to 1
        df['weight'] = df['weight'] / df['weight'].sum()

        return pd.Series(df['weight'].values, index=df['stock_code'])

    def _enforce_constraints(self, weights: pd.Series) -> pd.Series:
        """
        Enforce individual stock weight constraints

        Args:
            weights: Portfolio weights

        Returns:
            Constrained weights
        """
        # Clip to min/max
        weights = weights.clip(
            lower=self.min_stock_weight,
            upper=self.max_stock_weight
        )

        # Renormalize to sum to 1
        total = weights.sum()
        if total > 1e-8:
            weights = weights / total

        return weights

    def get_portfolio_stats(
        self,
        weights: pd.Series,
        signals: pd.DataFrame,
        sector_col: Optional[str] = None
    ) -> Dict:
        """
        Calculate portfolio statistics

        Args:
            weights: Portfolio weights
            signals: DataFrame with signal and sector info
            sector_col: Column name for sector

        Returns:
            Dictionary of statistics
        """
        stats = {
            'n_stocks': len(weights),
            'max_weight': weights.max(),
            'min_weight': weights.min(),
            'weight_std': weights.std(),
            'total_weight': weights.sum()
        }

        # Merge with signals
        df = pd.DataFrame({
            'stock_code': weights.index,
            'weight': weights.values
        })
        df = df.merge(signals, on='stock_code', how='left')

        # Average signal
        stats['avg_signal'] = (df['weight'] * df['signal']).sum()

        # Sector concentration
        if sector_col and sector_col in df.columns:
            sector_weights = df.groupby(sector_col)['weight'].sum()
            stats['n_sectors'] = len(sector_weights)
            stats['max_sector_weight'] = sector_weights.max()
            stats['sector_hhi'] = (sector_weights ** 2).sum()

        return stats
