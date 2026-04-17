"""
Risk Model - Barra-lite Style Factor Exposure Monitoring
Calculates portfolio exposure to 5 style factors: beta, volatility, momentum, liquidity, size
"""
import pandas as pd
import numpy as np
from typing import Dict, List


class BarraLiteRiskModel:
    """
    Simplified Barra-style risk model with 5 core factors
    - Beta: Market sensitivity
    - Volatility: Price volatility
    - Momentum: Recent returns
    - Liquidity: Trading volume
    - Size: Market capitalization
    """

    def __init__(self):
        self.factor_names = ['beta', 'volatility', 'momentum', 'liquidity', 'size']

    def calculate_factor_exposures(
        self,
        stock_data: pd.DataFrame,
        date: pd.Timestamp
    ) -> pd.DataFrame:
        """
        Calculate factor exposures for all stocks at a given date

        Args:
            stock_data: DataFrame with OHLCV data and market cap
                Required columns: [date, stock_code, close, volume, market_cap]
            date: Date to calculate exposures for

        Returns:
            DataFrame with columns [stock_code, beta, volatility, momentum, liquidity, size]
        """
        # Filter data up to the given date
        historical = stock_data[stock_data['date'] <= date].copy()

        if len(historical) == 0:
            return pd.DataFrame()

        # Calculate returns
        historical = historical.sort_values(['stock_code', 'date'])
        historical['return'] = historical.groupby('stock_code')['close'].pct_change()

        # Get latest date data for cross-sectional factors
        latest = historical[historical['date'] == date].copy()

        if len(latest) == 0:
            return pd.DataFrame()

        exposures = []
        for stock_code in latest['stock_code'].unique():
            stock_hist = historical[historical['stock_code'] == stock_code].copy()

            if len(stock_hist) < 60:  # Need at least 60 days
                continue

            stock_latest = latest[latest['stock_code'] == stock_code].iloc[0]

            exposure = {
                'stock_code': stock_code,
                'beta': self._calc_beta(stock_hist, historical),
                'volatility': self._calc_volatility(stock_hist),
                'momentum': self._calc_momentum(stock_hist),
                'liquidity': self._calc_liquidity(stock_hist),
                'size': self._calc_size(stock_latest)
            }
            exposures.append(exposure)

        df = pd.DataFrame(exposures)

        if len(df) == 0:
            return df  # Return empty DataFrame if no exposures calculated

        # Cross-sectional standardization
        for factor in self.factor_names:
            df[factor] = self._zscore(df[factor].values)

        return df

    def calculate_portfolio_exposure(
        self,
        weights: pd.Series,
        factor_exposures: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Calculate portfolio-level factor exposures

        Args:
            weights: Series with stock_code as index and weights as values
            factor_exposures: DataFrame from calculate_factor_exposures

        Returns:
            Dictionary of portfolio factor exposures
        """
        # Merge weights with exposures
        merged = factor_exposures.set_index('stock_code').loc[weights.index]

        portfolio_exposure = {}
        for factor in self.factor_names:
            # Weight-averaged exposure
            portfolio_exposure[factor] = (weights * merged[factor]).sum()

        return portfolio_exposure

    def _calc_beta(self, stock_hist: pd.DataFrame, market_hist: pd.DataFrame) -> float:
        """Calculate market beta using 60-day returns"""
        stock_returns = stock_hist.tail(60)['return'].dropna()

        # Market return = equal-weighted average
        market_returns = market_hist.groupby('date')['return'].mean()
        market_returns = market_returns.loc[stock_returns.index]

        if len(stock_returns) < 20 or len(market_returns) < 20:
            return 1.0

        # Align indices
        common_idx = stock_returns.index.intersection(market_returns.index)
        if len(common_idx) < 20:
            return 1.0

        stock_ret = stock_returns.loc[common_idx]
        market_ret = market_returns.loc[common_idx]

        # Beta = Cov(stock, market) / Var(market)
        cov = np.cov(stock_ret, market_ret)[0, 1]
        var = np.var(market_ret)

        if var < 1e-8:
            return 1.0

        return cov / var

    def _calc_volatility(self, stock_hist: pd.DataFrame) -> float:
        """Calculate 20-day return volatility"""
        returns = stock_hist.tail(20)['return'].dropna()

        if len(returns) < 10:
            return 0.0

        return returns.std() * np.sqrt(252)  # Annualized

    def _calc_momentum(self, stock_hist: pd.DataFrame) -> float:
        """Calculate 20-day momentum (cumulative return)"""
        prices = stock_hist.tail(21)['close']

        if len(prices) < 21:
            return 0.0

        return (prices.iloc[-1] / prices.iloc[0]) - 1.0

    def _calc_liquidity(self, stock_hist: pd.DataFrame) -> float:
        """Calculate average daily turnover (volume * price)"""
        recent = stock_hist.tail(20).copy()

        if len(recent) < 10:
            return 0.0

        recent['turnover'] = recent['volume'] * recent['close']
        return recent['turnover'].mean()

    def _calc_size(self, stock_latest: pd.Series) -> float:
        """Market capitalization"""
        if 'market_cap' in stock_latest:
            return stock_latest['market_cap']
        return 0.0

    def _zscore(self, x: np.ndarray) -> np.ndarray:
        """Cross-sectional z-score"""
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

    def check_risk_limits(
        self,
        portfolio_exposure: Dict[str, float],
        limits: Dict[str, float] = None
    ) -> Dict[str, bool]:
        """
        Check if portfolio exposures exceed risk limits

        Args:
            portfolio_exposure: Portfolio factor exposures
            limits: Dictionary of factor limits (default: ±0.5 for all)

        Returns:
            Dictionary indicating which limits are violated
        """
        if limits is None:
            limits = {factor: 0.5 for factor in self.factor_names}

        violations = {}
        for factor in self.factor_names:
            exposure = portfolio_exposure.get(factor, 0.0)
            limit = limits.get(factor, 0.5)
            violations[factor] = abs(exposure) > limit

        return violations
