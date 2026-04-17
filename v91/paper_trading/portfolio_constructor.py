"""
Portfolio Constructor Module - Godfather V9.0 Phase PT.1.1
Convert signals to target portfolio weights using frozen P.1.2 optimal config
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime


class PortfolioConstructor:
    """
    Portfolio construction using frozen P.1.2 optimal configuration

    Frozen Parameters (Godfather V9.0):
    - Rebalance frequency: Every 5 trading days
    - Hold buffer: 50%
    - Top 20 stocks
    - Sector neutrality: ON
    - Max stock weight: 10%
    """

    def __init__(
        self,
        n_stocks: int = 20,
        max_stock_weight: float = 0.10,
        sector_neutral: bool = True,
        hold_buffer_percentile: float = 0.50,
        rebalance_frequency: int = 5
    ):
        """
        Initialize portfolio constructor with frozen P.1.2 config

        Args:
            n_stocks: Number of stocks in portfolio (frozen at 20)
            max_stock_weight: Maximum weight per stock (frozen at 10%)
            sector_neutral: Sector neutrality flag (frozen at True)
            hold_buffer_percentile: Hold buffer (frozen at 50%)
            rebalance_frequency: Rebalance every N days (frozen at 5)
        """
        self.n_stocks = n_stocks
        self.max_stock_weight = max_stock_weight
        self.sector_neutral = sector_neutral
        self.hold_buffer_percentile = hold_buffer_percentile
        self.rebalance_frequency = rebalance_frequency

        self.current_holdings = set()  # Set of currently held symbols
        self.last_rebalance_date = None
        self.rebalance_counter = 0

        # Buffer statistics
        self.buffer_stats = {
            'retained': 0,
            'added': 0,
            'dropped': 0
        }

        print(f"Initializing PortfolioConstructor (Godfather V9.0 - PT.1.1)...")
        print(f"  Portfolio size: {self.n_stocks} stocks")
        print(f"  Max stock weight: {self.max_stock_weight*100:.1f}%")
        print(f"  Sector neutral: {self.sector_neutral}")
        print(f"  Hold buffer: {self.hold_buffer_percentile*100:.0f}%")
        print(f"  Rebalance frequency: Every {self.rebalance_frequency} days")
        print(f"  Buffer zone: Top {int(self.n_stocks * (1 + self.hold_buffer_percentile))} stocks")

    def should_rebalance(self, current_date: str) -> bool:
        """
        Check if portfolio should rebalance on given date

        Args:
            current_date: Current date (YYYY-MM-DD)

        Returns:
            True if should rebalance, False otherwise
        """
        current_date = pd.to_datetime(current_date)

        if self.last_rebalance_date is None:
            return True

        days_since_rebalance = (current_date - self.last_rebalance_date).days

        return days_since_rebalance >= self.rebalance_frequency

    def construct_target_portfolio(
        self,
        signal_data: pd.DataFrame,
        current_date: str,
        force_rebalance: bool = False
    ) -> pd.DataFrame:
        """
        Construct target portfolio from signals

        Args:
            signal_data: Signal DataFrame with sector_neutral_score
            current_date: Current date
            force_rebalance: Force rebalance regardless of schedule

        Returns:
            DataFrame with [stock_code, target_weight, sector, score]
        """
        current_date = pd.to_datetime(current_date)

        print(f"\n{'='*80}")
        print(f"【Constructing Target Portfolio - Godfather V9.0 PT.1.1】")
        print(f"Date: {current_date.date()}")
        print(f"{'='*80}\n")

        # Check if should rebalance
        if not force_rebalance and not self.should_rebalance(current_date):
            print(f"⏭️  Skipping rebalance (last rebalance: {self.last_rebalance_date.date()})")
            print(f"   Days since rebalance: {(current_date - self.last_rebalance_date).days}")
            print(f"   Next rebalance in: {self.rebalance_frequency - (current_date - self.last_rebalance_date).days} days")
            return pd.DataFrame()

        print(f"🔄 Rebalancing portfolio...")
        print(f"   Current holdings: {len(self.current_holdings)} stocks")

        # Use sector-neutral score for ranking
        signal_data = signal_data.copy()
        signal_data = signal_data.sort_values('sector_neutral_score', ascending=False)

        # Apply hold buffer (works on sector-neutral ranked signals)
        if len(self.current_holdings) > 0:
            target_stocks = self._apply_hold_buffer(signal_data)
        else:
            # First rebalance - take top N directly (no buffer needed)
            print(f"   First rebalance - no hold buffer applied")
            target_stocks = signal_data.head(self.n_stocks)

        # Calculate equal weights
        target_stocks = target_stocks.copy()
        target_stocks['target_weight'] = 1.0 / len(target_stocks)

        # Apply max weight constraint
        target_stocks['target_weight'] = target_stocks['target_weight'].clip(upper=self.max_stock_weight)

        # Renormalize
        target_stocks['target_weight'] = target_stocks['target_weight'] / target_stocks['target_weight'].sum()

        # Update state
        self.last_rebalance_date = current_date
        self.rebalance_counter += 1

        print(f"\n✅ Target Portfolio:")
        print(f"   Number of stocks: {len(target_stocks)}")
        print(f"   Total weight: {target_stocks['target_weight'].sum():.4f}")
        print(f"   Max weight: {target_stocks['target_weight'].max():.4f}")
        print(f"   Min weight: {target_stocks['target_weight'].min():.4f}")

        if 'sector' in target_stocks.columns:
            print(f"\n   Sector Exposure:")
            sector_weights = target_stocks.groupby('sector')['target_weight'].sum().sort_values(ascending=False)
            for sector, weight in sector_weights.head(5).items():
                print(f"     {sector}: {weight*100:.2f}%")

        # Print buffer statistics
        print(f"\n   Hold Buffer Statistics:")
        print(f"     Retained positions: {self.buffer_stats['retained']}")
        print(f"     New positions: {self.buffer_stats['added']}")
        print(f"     Dropped positions: {self.buffer_stats['dropped']}")
        if len(self.current_holdings) > 0:
            turnover_estimate = (self.buffer_stats['added'] + self.buffer_stats['dropped']) / (2 * self.n_stocks)
            print(f"     Estimated turnover: {turnover_estimate*100:.1f}%")

        return target_stocks[['stock_code', 'target_weight', 'sector', 'sector_neutral_score']]

    def _apply_hold_buffer(self, signal_data: pd.DataFrame) -> pd.DataFrame:
        """
        Apply hold buffer to reduce turnover - Godfather V9.0 PT.1.1 fixed logic

        Args:
            signal_data: Signal data sorted by score

        Returns:
            Signal data with hold buffer applied
        """
        print(f"\n   Applying Hold Buffer (50%)...")

        # Calculate buffer zone: top 20 + 50% = top 30
        n_buffer = int(self.n_stocks * (1 + self.hold_buffer_percentile))
        print(f"     Buffer zone: Top {n_buffer} stocks")

        # Get top N + buffer stocks (candidate pool)
        candidate_pool = signal_data.head(n_buffer)
        candidate_symbols = set(candidate_pool['stock_code'].values)

        # Current holdings
        current_symbols = self.current_holdings

        # Stocks to keep (in both current holdings AND candidate pool)
        keep_symbols = current_symbols & candidate_symbols
        print(f"     Current holdings in buffer zone: {len(keep_symbols)}")

        # Stocks to drop (current holdings NOT in candidate pool)
        drop_symbols = current_symbols - candidate_symbols
        print(f"     Current holdings outside buffer zone: {len(drop_symbols)}")

        # Stocks to add (in candidate pool but not current holdings)
        add_candidates = candidate_pool[~candidate_pool['stock_code'].isin(current_symbols)]
        print(f"     New candidates available: {len(add_candidates)}")

        # Build target portfolio
        # Step 1: Keep all existing holdings that are still in buffer zone
        keep_stocks = candidate_pool[candidate_pool['stock_code'].isin(keep_symbols)]

        # Step 2: Add new stocks to reach target size
        n_to_add = self.n_stocks - len(keep_symbols)

        if n_to_add > 0:
            # Add top-ranked new stocks
            new_stocks = add_candidates.head(n_to_add)
            result = pd.concat([keep_stocks, new_stocks], ignore_index=True)
        else:
            # We have more than enough stocks in keep_symbols
            # Select top N by score
            result = keep_stocks.sort_values('sector_neutral_score', ascending=False).head(self.n_stocks)

        # Update buffer statistics
        self.buffer_stats['retained'] = len(keep_symbols)
        self.buffer_stats['added'] = n_to_add if n_to_add > 0 else 0
        self.buffer_stats['dropped'] = len(drop_symbols)

        print(f"\n   ✅ Hold Buffer Decision:")
        print(f"     Retained: {self.buffer_stats['retained']} stocks")
        print(f"     Added: {self.buffer_stats['added']} stocks")
        print(f"     Dropped: {self.buffer_stats['dropped']} stocks")

        return result

    def calculate_turnover(
        self,
        target_portfolio: pd.DataFrame,
        current_portfolio: Optional[set] = None
    ) -> float:
        """
        Calculate expected turnover

        Args:
            target_portfolio: Target portfolio DataFrame
            current_portfolio: Current portfolio symbols (set)

        Returns:
            Turnover as fraction (0 to 2)
        """
        if current_portfolio is None:
            current_portfolio = self.current_holdings

        if len(current_portfolio) == 0:
            return 1.0  # 100% turnover on first trade

        target_symbols = set(target_portfolio['stock_code'].values)

        # Calculate symbol turnover
        added = len(target_symbols - current_portfolio)
        dropped = len(current_portfolio - target_symbols)

        # Turnover = (added + dropped) / (2 * portfolio_size)
        turnover = (added + dropped) / (2 * self.n_stocks)

        return turnover

    def update_holdings(self, realized_portfolio: pd.DataFrame):
        """
        Update current holdings after execution

        Args:
            realized_portfolio: Realized portfolio DataFrame with stock_code column
        """
        if len(realized_portfolio) > 0:
            self.current_holdings = set(realized_portfolio['stock_code'].values)
        else:
            self.current_holdings = set()

        print(f"\n✅ Holdings updated: {len(self.current_holdings)} stocks")

    def get_portfolio_summary(
        self,
        target_portfolio: pd.DataFrame
    ) -> Dict:
        """
        Get portfolio summary statistics

        Args:
            target_portfolio: Target portfolio DataFrame

        Returns:
            Dictionary with portfolio statistics
        """
        if len(target_portfolio) == 0:
            return {"status": "No rebalance"}

        turnover = self.calculate_turnover(target_portfolio)

        summary = {
            "num_stocks": len(target_portfolio),
            "total_weight": float(target_portfolio['target_weight'].sum()),
            "max_weight": float(target_portfolio['target_weight'].max()),
            "min_weight": float(target_portfolio['target_weight'].min()),
            "expected_turnover": float(turnover),
            "gross_exposure": 1.0,  # Long-only
            "net_exposure": 1.0,    # Long-only
            "rebalance_count": self.rebalance_counter,
            "last_rebalance_date": self.last_rebalance_date.date().isoformat() if self.last_rebalance_date else None,
            "buffer_stats": self.buffer_stats.copy()
        }

        if 'sector' in target_portfolio.columns:
            sector_exposure = target_portfolio.groupby('sector')['target_weight'].sum().to_dict()
            summary['sector_exposure'] = {k: float(v) for k, v in sector_exposure.items()}

        return summary
