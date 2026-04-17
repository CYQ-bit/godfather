"""
Risk Guard Module - Phase PT.1
Production-grade risk controls and circuit breakers
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum


class RiskStatus(Enum):
    """Risk status levels"""
    OK = "OK"
    WARN = "WARN"
    HALT = "HALT"


class RiskGuard:
    """
    Risk management and circuit breaker system

    Features:
    - Portfolio-level risk limits
    - Performance-based circuit breakers
    - Execution quality monitoring
    - Data quality checks
    - Multi-level alerts (OK/WARN/HALT)
    """

    def __init__(
        self,
        max_gross_exposure: float = 1.0,
        max_net_exposure: float = 1.0,
        min_net_exposure: float = 0.9,
        max_single_stock_weight: float = 0.10,
        max_sector_exposure: float = 0.30,
        max_daily_loss: float = 0.05,
        max_consecutive_loss_days: int = 3,
        max_drawdown: float = 0.20,
        max_unfilled_rate: float = 0.10,
        max_execution_slippage_bps: float = 50.0,
        max_implementation_shortfall_bps: float = 500.0,
        max_turnover: float = 1.0
    ):
        """
        Initialize risk guard with limits

        Args:
            max_gross_exposure: Maximum gross exposure (default 1.0 = 100%)
            max_net_exposure: Maximum net exposure (default 1.0 = 100%)
            min_net_exposure: Minimum net exposure (default 0.9 = 90%)
            max_single_stock_weight: Maximum single stock weight (default 0.10 = 10%)
            max_sector_exposure: Maximum sector exposure (default 0.30 = 30%)
            max_daily_loss: Maximum daily loss (default 0.05 = 5%)
            max_consecutive_loss_days: Maximum consecutive loss days (default 3)
            max_drawdown: Maximum drawdown (default 0.20 = 20%)
            max_unfilled_rate: Maximum unfilled order rate (default 0.10 = 10%)
            max_execution_slippage_bps: Maximum execution slippage in bps (default 50)
            max_implementation_shortfall_bps: Maximum implementation shortfall in bps (default 500)
            max_turnover: Maximum turnover (default 1.0 = 100%)
        """
        # Portfolio limits
        self.max_gross_exposure = max_gross_exposure
        self.max_net_exposure = max_net_exposure
        self.min_net_exposure = min_net_exposure
        self.max_single_stock_weight = max_single_stock_weight
        self.max_sector_exposure = max_sector_exposure

        # Performance limits
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_loss_days = max_consecutive_loss_days
        self.max_drawdown = max_drawdown

        # Execution limits
        self.max_unfilled_rate = max_unfilled_rate
        self.max_execution_slippage_bps = max_execution_slippage_bps
        self.max_implementation_shortfall_bps = max_implementation_shortfall_bps
        self.max_turnover = max_turnover

        # State tracking
        self.consecutive_loss_days = 0
        self.peak_value = None
        self.alerts = []

        print(f"Initializing RiskGuard (Godfather V9.0 - PT.1.1a)...")
        print(f"  Portfolio Limits:")
        print(f"    Max gross exposure: {self.max_gross_exposure*100:.0f}%")
        print(f"    Net exposure range: {self.min_net_exposure*100:.0f}%-{self.max_net_exposure*100:.0f}%")
        print(f"    Max single stock: {self.max_single_stock_weight*100:.0f}%")
        print(f"    Max sector: {self.max_sector_exposure*100:.0f}%")
        print(f"  Performance Limits:")
        print(f"    Max daily loss: {self.max_daily_loss*100:.0f}%")
        print(f"    Max consecutive losses: {self.max_consecutive_loss_days} days")
        print(f"    Max drawdown: {self.max_drawdown*100:.0f}%")
        print(f"  Execution Limits:")
        print(f"    Max unfilled rate: {self.max_unfilled_rate*100:.0f}%")
        print(f"    Max execution slippage: {self.max_execution_slippage_bps} bps")
        print(f"    Max implementation shortfall: {self.max_implementation_shortfall_bps} bps")
        print(f"    Max turnover: {self.max_turnover*100:.0f}%")

    def check_portfolio_risk(
        self,
        target_portfolio: pd.DataFrame
    ) -> Tuple[RiskStatus, List[str]]:
        """
        Check portfolio-level risk limits

        Args:
            target_portfolio: Target portfolio with [stock_code, target_weight, sector]

        Returns:
            (risk_status, list of violations)
        """
        violations = []
        status = RiskStatus.OK

        if len(target_portfolio) == 0:
            return status, violations

        # Check gross exposure
        gross_exposure = target_portfolio['target_weight'].abs().sum()
        if gross_exposure > self.max_gross_exposure:
            violations.append(f"Gross exposure {gross_exposure:.2%} exceeds limit {self.max_gross_exposure:.2%}")
            status = RiskStatus.HALT

        # Check net exposure
        net_exposure = target_portfolio['target_weight'].sum()
        if net_exposure > self.max_net_exposure:
            violations.append(f"Net exposure {net_exposure:.2%} exceeds max {self.max_net_exposure:.2%}")
            status = RiskStatus.WARN
        if net_exposure < self.min_net_exposure:
            violations.append(f"Net exposure {net_exposure:.2%} below min {self.min_net_exposure:.2%}")
            status = RiskStatus.WARN

        # Check single stock weights
        max_weight = target_portfolio['target_weight'].abs().max()
        if max_weight > self.max_single_stock_weight:
            violations.append(f"Single stock weight {max_weight:.2%} exceeds limit {self.max_single_stock_weight:.2%}")
            status = RiskStatus.HALT

        # Check sector exposure
        if 'sector' in target_portfolio.columns:
            sector_exposure = target_portfolio.groupby('sector')['target_weight'].sum().abs()
            max_sector = sector_exposure.max()
            if max_sector > self.max_sector_exposure:
                violations.append(f"Sector exposure {max_sector:.2%} exceeds limit {self.max_sector_exposure:.2%}")
                status = RiskStatus.WARN

        return status, violations

    def check_performance_risk(
        self,
        daily_return: float,
        portfolio_value: float
    ) -> Tuple[RiskStatus, List[str]]:
        """
        Check performance-based risk limits

        Args:
            daily_return: Daily return (fraction)
            portfolio_value: Current portfolio value

        Returns:
            (risk_status, list of violations)
        """
        violations = []
        status = RiskStatus.OK

        # Update peak value
        if self.peak_value is None:
            self.peak_value = portfolio_value
        else:
            self.peak_value = max(self.peak_value, portfolio_value)

        # Check daily loss
        if daily_return < -self.max_daily_loss:
            violations.append(f"Daily loss {daily_return:.2%} exceeds limit {-self.max_daily_loss:.2%}")
            status = RiskStatus.HALT

        # Track consecutive loss days
        if daily_return < 0:
            self.consecutive_loss_days += 1
        else:
            self.consecutive_loss_days = 0

        if self.consecutive_loss_days >= self.max_consecutive_loss_days:
            violations.append(f"Consecutive loss days {self.consecutive_loss_days} exceeds limit {self.max_consecutive_loss_days}")
            status = RiskStatus.WARN

        # Check drawdown
        drawdown = (portfolio_value - self.peak_value) / self.peak_value
        if drawdown < -self.max_drawdown:
            violations.append(f"Drawdown {drawdown:.2%} exceeds limit {-self.max_drawdown:.2%}")
            status = RiskStatus.HALT

        return status, violations

    def check_execution_risk(
        self,
        orders: List[Dict],
        fills: List[Dict],
        turnover: float,
        execution_summary: Optional[Dict] = None
    ) -> Tuple[RiskStatus, List[str]]:
        """
        Check execution quality with proper slippage decomposition (PT.1.1a)

        Args:
            orders: List of orders
            fills: List of fills
            turnover: Realized turnover
            execution_summary: Execution summary from ExecutionMonitor (optional)

        Returns:
            (risk_status, list of violations)
        """
        violations = []
        status = RiskStatus.OK

        if len(orders) == 0:
            return status, violations

        # Check unfilled rate
        unfilled_rate = 1.0 - (len(fills) / len(orders))
        if unfilled_rate > self.max_unfilled_rate:
            violations.append(f"Unfilled rate {unfilled_rate:.2%} exceeds limit {self.max_unfilled_rate:.2%}")
            status = RiskStatus.WARN

        # Check slippage with proper decomposition (PT.1.1a)
        if execution_summary is not None:
            # Use ExecutionMonitor's decomposed metrics
            exec_slip = execution_summary.get('execution_slippage_abs_mean_bps', 0)
            impl_shortfall = execution_summary.get('implementation_shortfall_abs_mean_bps', 0)

            # Strict threshold for execution slippage (trade->fill)
            if exec_slip > self.max_execution_slippage_bps:
                violations.append(f"Execution slippage {exec_slip:.1f} bps exceeds limit {self.max_execution_slippage_bps} bps")
                status = RiskStatus.WARN

            # Wider threshold for implementation shortfall (signal->fill, includes market move)
            if impl_shortfall > self.max_implementation_shortfall_bps:
                violations.append(f"Implementation shortfall {impl_shortfall:.1f} bps exceeds limit {self.max_implementation_shortfall_bps} bps")
                status = RiskStatus.WARN
        else:
            # Fallback: calculate implementation shortfall only (signal->fill)
            if len(fills) > 0:
                impl_shortfalls = []
                for fill in fills:
                    order = next((o for o in orders if o['order_id'] == fill['order_id']), None)
                    if order and 'reference_price' in order:
                        impl_shortfall_bps = abs(fill['fill_price'] - order['reference_price']) / order['reference_price'] * 10000
                        impl_shortfalls.append(impl_shortfall_bps)

                if impl_shortfalls:
                    avg_impl_shortfall = np.mean(impl_shortfalls)
                    if avg_impl_shortfall > self.max_implementation_shortfall_bps:
                        violations.append(f"Implementation shortfall {avg_impl_shortfall:.1f} bps exceeds limit {self.max_implementation_shortfall_bps} bps")
                        status = RiskStatus.WARN

        # Check turnover
        if turnover > self.max_turnover:
            violations.append(f"Turnover {turnover:.2%} exceeds limit {self.max_turnover:.2%}")
            status = RiskStatus.WARN

        return status, violations

    def check_data_quality(
        self,
        market_data: pd.DataFrame,
        expected_symbols: int,
        expected_date: str
    ) -> Tuple[RiskStatus, List[str]]:
        """
        Check data quality and freshness

        Args:
            market_data: Market data DataFrame
            expected_symbols: Expected number of symbols
            expected_date: Expected latest date

        Returns:
            (risk_status, list of violations)
        """
        violations = []
        status = RiskStatus.OK

        # Check data availability
        if len(market_data) == 0:
            violations.append("No market data available")
            return RiskStatus.HALT, violations

        # Check symbol count
        actual_symbols = market_data['stock_code'].nunique() if 'stock_code' in market_data.columns else 0
        if actual_symbols < expected_symbols * 0.9:
            violations.append(f"Symbol count {actual_symbols} is {(1 - actual_symbols/expected_symbols)*100:.1f}% below expected {expected_symbols}")
            status = RiskStatus.WARN

        # Check data freshness
        if 'date' in market_data.columns:
            latest_date = market_data['date'].max()
            expected_date = pd.to_datetime(expected_date)
            days_behind = (expected_date - latest_date).days

            if days_behind > 1:
                violations.append(f"Data is {days_behind} days behind (latest: {latest_date.date()}, expected: {expected_date.date()})")
                status = RiskStatus.HALT

        return status, violations

    def run_all_checks(
        self,
        target_portfolio: Optional[pd.DataFrame] = None,
        daily_return: Optional[float] = None,
        portfolio_value: Optional[float] = None,
        orders: Optional[List[Dict]] = None,
        fills: Optional[List[Dict]] = None,
        turnover: Optional[float] = None,
        execution_summary: Optional[Dict] = None,
        market_data: Optional[pd.DataFrame] = None,
        expected_symbols: Optional[int] = None,
        expected_date: Optional[str] = None
    ) -> Tuple[RiskStatus, Dict]:
        """
        Run all risk checks

        Returns:
            (overall_status, detailed_results)
        """
        print(f"\n{'='*80}")
        print(f"【Running Risk Checks】")
        print(f"{'='*80}\n")

        results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'overall_status': RiskStatus.OK,
            'violations': []
        }

        overall_status = RiskStatus.OK

        # Portfolio risk
        if target_portfolio is not None:
            status, violations = self.check_portfolio_risk(target_portfolio)
            results['checks']['portfolio'] = {'status': status.value, 'violations': violations}
            if status.value == 'HALT':
                overall_status = RiskStatus.HALT
            elif status.value == 'WARN' and overall_status != RiskStatus.HALT:
                overall_status = RiskStatus.WARN
            results['violations'].extend(violations)

        # Performance risk
        if daily_return is not None and portfolio_value is not None:
            status, violations = self.check_performance_risk(daily_return, portfolio_value)
            results['checks']['performance'] = {'status': status.value, 'violations': violations}
            if status.value == 'HALT':
                overall_status = RiskStatus.HALT
            elif status.value == 'WARN' and overall_status != RiskStatus.HALT:
                overall_status = RiskStatus.WARN
            results['violations'].extend(violations)

        # Execution risk
        if orders is not None and fills is not None and turnover is not None:
            status, violations = self.check_execution_risk(orders, fills, turnover, execution_summary)
            results['checks']['execution'] = {'status': status.value, 'violations': violations}
            if status.value == 'HALT':
                overall_status = RiskStatus.HALT
            elif status.value == 'WARN' and overall_status != RiskStatus.HALT:
                overall_status = RiskStatus.WARN
            results['violations'].extend(violations)

        # Data quality
        if market_data is not None and expected_symbols is not None and expected_date is not None:
            status, violations = self.check_data_quality(market_data, expected_symbols, expected_date)
            results['checks']['data_quality'] = {'status': status.value, 'violations': violations}
            if status.value == 'HALT':
                overall_status = RiskStatus.HALT
            elif status.value == 'WARN' and overall_status != RiskStatus.HALT:
                overall_status = RiskStatus.WARN
            results['violations'].extend(violations)

        results['overall_status'] = overall_status.value

        # Print summary
        print(f"Risk Status: {overall_status.value}")
        if len(results['violations']) > 0:
            print(f"\nViolations:")
            for violation in results['violations']:
                print(f"  ⚠️  {violation}")
        else:
            print(f"✅ All risk checks passed")

        return overall_status, results
