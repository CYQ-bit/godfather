"""
Signal Processor - Step 1 of Production Pipeline
Handles signal standardization and sector neutralization
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional


class SignalProcessor:
    """
    Processes raw ML predictions into portfolio-ready signals
    - Standardizes signals (z-score)
    - Applies sector neutralization
    - Handles missing data
    """

    def __init__(self, sector_col: str = 'sector'):
        """
        Args:
            sector_col: Column name for sector information
        """
        self.sector_col = sector_col

    def process(
        self,
        predictions: pd.DataFrame,
        sector_neutral: bool = True,
        clip_std: float = 3.0
    ) -> pd.DataFrame:
        """
        Process raw predictions into standardized signals

        Args:
            predictions: DataFrame with columns [date, stock_code, prediction, sector]
            sector_neutral: Whether to apply sector neutralization
            clip_std: Clip signals beyond this many standard deviations

        Returns:
            DataFrame with processed signals
        """
        df = predictions.copy()

        # Group by date for cross-sectional processing
        processed_list = []
        for date, group in df.groupby('date'):
            group = group.copy()

            # Step 1: Cross-sectional z-score
            group['signal_raw'] = self._zscore(group['prediction'].values)

            # Step 2: Sector neutralization
            if sector_neutral and self.sector_col in group.columns:
                group['signal'] = self._sector_neutralize(
                    group,
                    signal_col='signal_raw'
                )
            else:
                group['signal'] = group['signal_raw']

            # Step 3: Clip outliers
            group['signal'] = np.clip(
                group['signal'],
                -clip_std,
                clip_std
            )

            # Step 4: Re-standardize after clipping
            group['signal'] = self._zscore(group['signal'].values)

            processed_list.append(group)

        result = pd.concat(processed_list, ignore_index=True)
        return result

    def _zscore(self, x: np.ndarray) -> np.ndarray:
        """Cross-sectional z-score with NaN handling"""
        x = np.array(x, dtype=float)
        valid_mask = ~np.isnan(x)

        if valid_mask.sum() < 2:
            return np.zeros_like(x)

        mean = np.nanmean(x)
        std = np.nanstd(x)

        if std < 1e-8:
            return np.zeros_like(x)

        z = (x - mean) / std
        z[~valid_mask] = 0.0
        return z

    def _sector_neutralize(
        self,
        df: pd.DataFrame,
        signal_col: str
    ) -> pd.Series:
        """
        Sector neutralization: subtract sector mean from each signal

        Args:
            df: DataFrame with signal and sector columns
            signal_col: Name of signal column to neutralize

        Returns:
            Sector-neutralized signals
        """
        if self.sector_col not in df.columns:
            return df[signal_col]

        # Calculate sector means
        sector_means = df.groupby(self.sector_col)[signal_col].transform('mean')

        # Subtract sector mean
        neutral_signal = df[signal_col] - sector_means

        # Re-standardize to maintain unit variance
        neutral_signal = self._zscore(neutral_signal.values)

        return neutral_signal

    def get_signal_stats(self, df: pd.DataFrame) -> Dict:
        """
        Calculate signal statistics for monitoring

        Args:
            df: Processed signals DataFrame

        Returns:
            Dictionary of statistics
        """
        stats = {
            'mean': df['signal'].mean(),
            'std': df['signal'].std(),
            'min': df['signal'].min(),
            'max': df['signal'].max(),
            'n_stocks': df.groupby('date')['stock_code'].count().mean(),
        }

        if self.sector_col in df.columns:
            # Sector neutrality check (should be close to 0)
            sector_means = df.groupby(['date', self.sector_col])['signal'].mean()
            stats['sector_mean_abs'] = sector_means.abs().mean()

        return stats
