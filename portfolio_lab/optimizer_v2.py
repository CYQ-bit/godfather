"""
Portfolio Optimizer - Phase P.1.2 Enhanced Version
Turnover-aware optimization with hold buffer and no-trade band
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from scipy.optimize import minimize


class TurnoverAwareOptimizer:
    """
    Enhanced portfolio optimizer with turnover control:
    - Turnover penalty in objective function
    - Hold buffer mechanism
    - No-trade band
    - Previous position awareness
    """

    def __init__(
        self,
        max_stock_weight: float = 0.10,
        min_stock_weight: float = 0.0,
        max_sector_weight: Optional[float] = None,
        turnover_penalty: float = 0.0,
        hold_buffer_percentile: float = 0.0
    ):
        """
        Args:
            max_stock_weight: Maximum weight per stock
            min_stock_weight: Minimum weight per stock
            max_sector_weight: Maximum weight per sector
            turnover_penalty: Lambda for turnover penalty (0 = no penalty)
            hold_buffer_percentile: Buffer for holding existing positions (0-1)
        """
        self.max_stock_weight = max_stock_weight
        self.min_stock_weight = min_stock_weight
        self.max_sector_weight = max_sector_weight
        self.turnover_penalty = turnover_penalty
        self.hold_buffer_percentile = hold_buffer_percentile

    def optimize(
        self,
        signals: pd.DataFrame,
        method: str = 'top_n_with_buffer',
        n_stocks: int = 20,
        sector_col: Optional[str] = None,
        previous_weights: Optional[pd.Series] = None
    ) -> pd.Series:
        """
        Optimize portfolio weights with turnover awareness

        Args:
            signals: DataFrame with [stock_code, signal, sector]
            method: Optimization method
            n_stocks: Number of stocks to hold
            sector_col: Column name for sector
            previous_weights: Previous period weights (for turnover penalty)

        Returns:
            Series with stock_code as index and weights as values
        """
        if len(signals) == 0:
            return pd.Series(dtype=float)

        if method == 'top_n_with_buffer':
            weights = self._optimize_top_n_with_buffer(
                signals,
                n_stocks,
                previous_weights
            )
        elif method == 'top_n':
            weights = self._optimize_top_n(signals, n_stocks)
        elif method == 'proportional':
            weights = self._optimize_proportional(signals, n_stocks)
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

    def _optimize_top_n_with_buffer(
        self,
        signals: pd.DataFrame,
        n_stocks: int,
        previous_weights: Optional[pd.Series]
    ) -> pd.Series:
        """
        Top-N selection with hold buffer to reduce turnover

        Logic:
        1. If no previous weights, select top N by signal
        2. If previous weights exist:
           - Keep existing holdings that are still in top (N + buffer)
           - Only replace holdings that fall below buffer threshold
           - Fill remaining slots with highest new signals
        """
        # Sort by signal descending
        sorted_signals = signals.sort_values('signal', ascending=False)

        if previous_weights is None or len(previous_weights) == 0:
            # First period: simple top N
            top_n = sorted_signals.head(n_stocks)
            weights = pd.Series(
                1.0 / len(top_n),
                index=top_n['stock_code']
            )
            return weights

        # Calculate buffer size
        buffer_size = int(n_stocks * self.hold_buffer_percentile)
        extended_n = n_stocks + buffer_size

        # Get top (N + buffer) stocks by signal
        top_extended = sorted_signals.head(extended_n)
        top_extended_set = set(top_extended['stock_code'])

        # Identify existing holdings
        existing_holdings = set(previous_weights.index)

        # Keep existing holdings that are still in top (N + buffer)
        holdings_to_keep = existing_holdings & top_extended_set

        # Calculate how many new stocks we need
        n_to_add = n_stocks - len(holdings_to_keep)

        # Select new stocks from top signals (excluding existing holdings)
        new_candidates = sorted_signals[
            ~sorted_signals['stock_code'].isin(existing_holdings)
        ]
        new_stocks = set(new_candidates.head(max(0, n_to_add))['stock_code'])

        # Final portfolio
        final_holdings = holdings_to_keep | new_stocks

        # Limit to exactly n_stocks if we have more
        if len(final_holdings) > n_stocks:
            # Prioritize by signal strength
            final_holdings_df = sorted_signals[
                sorted_signals['stock_code'].isin(final_holdings)
            ].head(n_stocks)
            final_holdings = set(final_holdings_df['stock_code'])

        # Equal weight
        weights = pd.Series(
            1.0 / len(final_holdings),
            index=list(final_holdings)
        )

        return weights

    def _optimize_top_n(
        self,
        signals: pd.DataFrame,
        n_stocks: int
    ) -> pd.Series:
        """Simple top-N equal-weighted selection"""
        sorted_signals = signals.sort_values('signal', ascending=False)
        top_n = sorted_signals.head(n_stocks)
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
        """Top-N with signal-proportional weights"""
        sorted_signals = signals.sort_values('signal', ascending=False)
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

    def _apply_sector_constraints(
        self,
        weights: pd.Series,
        signals: pd.DataFrame,
        sector_col: str
    ) -> pd.Series:
        """Apply sector weight constraints"""
        if self.max_sector_weight is None:
            return weights

        df = pd.DataFrame({
            'stock_code': weights.index,
            'weight': weights.values
        })
        df = df.merge(
            signals[['stock_code', sector_col]],
            on='stock_code',
            how='left'
        )

        sector_weights = df.groupby(sector_col)['weight'].sum()
        violations = sector_weights[sector_weights > self.max_sector_weight]

        if len(violations) == 0:
            return weights

        # Scale down overweight sectors
        for sector in violations.index:
            sector_mask = df[sector_col] == sector
            scale_factor = self.max_sector_weight / violations[sector]
            df.loc[sector_mask, 'weight'] *= scale_factor

        # Renormalize
        df['weight'] = df['weight'] / df['weight'].sum()

        return pd.Series(df['weight'].values, index=df['stock_code'])

    def _enforce_constraints(self, weights: pd.Series) -> pd.Series:
        """Enforce individual stock weight constraints"""
        weights = weights.clip(
            lower=self.min_stock_weight,
            upper=self.max_stock_weight
        )

        total = weights.sum()
        if total > 1e-8:
            weights = weights / total

        return weights

    def calculate_turnover(
        self,
        new_weights: pd.Series,
        old_weights: pd.Series
    ) -> float:
        """
        Calculate portfolio turnover

        Args:
            new_weights: New target weights
            old_weights: Previous weights

        Returns:
            Turnover as sum of absolute weight changes
        """
        if old_weights is None or len(old_weights) == 0:
            return new_weights.sum()

        # Align indices
        all_stocks = set(new_weights.index) | set(old_weights.index)

        turnover = 0.0
        for stock in all_stocks:
            new_w = new_weights.get(stock, 0.0)
            old_w = old_weights.get(stock, 0.0)
            turnover += abs(new_w - old_w)

        return turnover

    def get_portfolio_stats(
        self,
        weights: pd.Series,
        signals: pd.DataFrame,
        sector_col: Optional[str] = None,
        previous_weights: Optional[pd.Series] = None
    ) -> Dict:
        """Calculate portfolio statistics"""
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

        # Turnover
        if previous_weights is not None:
            stats['turnover'] = self.calculate_turnover(weights, previous_weights)
        else:
            stats['turnover'] = weights.sum()

        # Sector concentration
        if sector_col and sector_col in df.columns:
            sector_weights = df.groupby(sector_col)['weight'].sum()
            stats['n_sectors'] = len(sector_weights)
            stats['max_sector_weight'] = sector_weights.max()
            stats['sector_hhi'] = (sector_weights ** 2).sum()

        return stats
