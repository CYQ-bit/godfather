"""
Signal Runner Module - Phase PT.1
Generate signals using frozen ML.2 predictions
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import warnings


class SignalRunner:
    """
    Signal generation using frozen ML.2 model and validated features

    Features:
    - Load frozen ML.2 predictions
    - Apply sector neutralization
    - Generate signal timestamps
    - Track model/feature versions
    - Save signals for audit trail
    """

    def __init__(
        self,
        predictions_path: str,
        model_version: str = "ML.2_8window",
        feature_version: str = "B.2_frozen"
    ):
        """
        Initialize signal runner

        Args:
            predictions_path: Path to ML.2 predictions
            model_version: Model version identifier
            feature_version: Feature set version identifier
        """
        self.predictions_path = Path(predictions_path)
        self.model_version = model_version
        self.feature_version = feature_version
        self.predictions = None

        print(f"Initializing SignalRunner...")
        print(f"  Model version: {self.model_version}")
        print(f"  Feature version: {self.feature_version}")
        print(f"  Predictions path: {self.predictions_path}")

    def load_predictions(self) -> pd.DataFrame:
        """
        Load frozen ML.2 predictions

        Returns:
            DataFrame with predictions
        """
        print(f"\nLoading frozen predictions...")

        self.predictions = pd.read_parquet(self.predictions_path)

        # Standardize column names
        if 'timestamp' in self.predictions.columns:
            self.predictions = self.predictions.rename(columns={'timestamp': 'date'})
        if 'symbol' in self.predictions.columns:
            self.predictions = self.predictions.rename(columns={'symbol': 'stock_code'})
        if 'y_pred' in self.predictions.columns:
            self.predictions = self.predictions.rename(columns={'y_pred': 'prediction'})

        self.predictions['date'] = pd.to_datetime(self.predictions['date'])

        print(f"  Loaded {len(self.predictions)} predictions")
        print(f"  Date range: {self.predictions['date'].min()} to {self.predictions['date'].max()}")
        print(f"  Symbols: {self.predictions['stock_code'].nunique()}")

        return self.predictions

    def generate_signal(
        self,
        signal_date: str,
        sector_map: Optional[Dict[str, str]] = None
    ) -> pd.DataFrame:
        """
        Generate signal for given date

        Args:
            signal_date: Signal generation date (YYYY-MM-DD)
            sector_map: Optional sector mapping {symbol: sector}

        Returns:
            DataFrame with [date, stock_code, raw_score, sector_neutral_score, sector]
        """
        if self.predictions is None:
            raise ValueError("Predictions not loaded. Call load_predictions() first.")

        signal_date = pd.to_datetime(signal_date)

        print(f"\n{'='*80}")
        print(f"【Generating Signal for {signal_date.date()}】")
        print(f"{'='*80}\n")

        # Get predictions for this date
        signal_data = self.predictions[self.predictions['date'] == signal_date].copy()

        if len(signal_data) == 0:
            warnings.warn(f"No predictions found for {signal_date.date()}")
            return pd.DataFrame()

        print(f"Found {len(signal_data)} predictions for {signal_date.date()}")

        # Add sector information
        if sector_map:
            signal_data['sector'] = signal_data['stock_code'].map(sector_map)
            signal_data['sector'] = signal_data['sector'].fillna('Unknown')
        else:
            signal_data['sector'] = 'Unknown'

        # Raw score
        signal_data['raw_score'] = signal_data['prediction']

        # Sector-neutral score (z-score within sector)
        if sector_map:
            signal_data['sector_neutral_score'] = signal_data.groupby('sector')['raw_score'].transform(
                lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
            )
        else:
            signal_data['sector_neutral_score'] = signal_data['raw_score']

        # Add metadata
        signal_data['signal_timestamp'] = datetime.now()
        signal_data['model_version'] = self.model_version
        signal_data['feature_version'] = self.feature_version

        print(f"\nSignal Statistics:")
        print(f"  Raw score mean: {signal_data['raw_score'].mean():.4f}")
        print(f"  Raw score std: {signal_data['raw_score'].std():.4f}")
        print(f"  Sector-neutral score mean: {signal_data['sector_neutral_score'].mean():.4f}")
        print(f"  Sector-neutral score std: {signal_data['sector_neutral_score'].std():.4f}")

        if sector_map:
            print(f"\nSector Distribution:")
            sector_counts = signal_data['sector'].value_counts()
            for sector, count in sector_counts.head(10).items():
                print(f"  {sector}: {count}")

        return signal_data

    def save_signal(
        self,
        signal_data: pd.DataFrame,
        output_dir: str,
        signal_date: str
    ):
        """
        Save signal to disk for audit trail

        Args:
            signal_data: Signal DataFrame
            output_dir: Output directory
            signal_date: Signal date (YYYY-MM-DD)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        signal_date = pd.to_datetime(signal_date).date()
        output_file = output_dir / f"{signal_date}.parquet"

        signal_data.to_parquet(output_file, index=False)

        print(f"\n✅ Signal saved: {output_file}")
        print(f"   Records: {len(signal_data)}")

    def get_signal_summary(self, signal_data: pd.DataFrame) -> Dict:
        """
        Get summary statistics for signal

        Args:
            signal_data: Signal DataFrame

        Returns:
            Dictionary with signal statistics
        """
        if len(signal_data) == 0:
            return {"status": "No signal data"}

        return {
            "signal_date": signal_data['date'].iloc[0].date().isoformat(),
            "num_signals": len(signal_data),
            "num_symbols": signal_data['stock_code'].nunique(),
            "raw_score_mean": float(signal_data['raw_score'].mean()),
            "raw_score_std": float(signal_data['raw_score'].std()),
            "sector_neutral_score_mean": float(signal_data['sector_neutral_score'].mean()),
            "sector_neutral_score_std": float(signal_data['sector_neutral_score'].std()),
            "model_version": self.model_version,
            "feature_version": self.feature_version,
            "signal_timestamp": datetime.now().isoformat()
        }
