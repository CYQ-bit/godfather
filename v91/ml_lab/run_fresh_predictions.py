"""
Fresh Prediction Generator - Godfather V9.0 PT.4.4d
Generate latest predictions using existing feature matrix (no retraining)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import pyarrow.parquet as pq
from datetime import datetime


def generate_mock_predictions():
    """
    Generate mock predictions based on latest feature matrix
    Uses simple heuristic: recent return momentum as prediction
    """
    print("="*80)
    print("【Fresh Prediction Generator - Godfather V9.0 PT.4.4d】")
    print("="*80)
    print()

    # Load feature matrix
    feature_path = Path(__file__).parent.parent / 'data/feature_store/ml_alpha_matrix.parquet'

    print(f"Loading feature matrix: {feature_path}")

    available_columns = set(pq.ParquetFile(feature_path).schema.names)
    read_columns = ['timestamp', 'symbol']
    if 'alpha_0002' in available_columns:
        read_columns.append('alpha_0002')
    if 'target' in available_columns:
        read_columns.append('target')

    print(f"  Reading columns: {read_columns}")
    df = pd.read_parquet(feature_path, columns=read_columns)

    print(f"  Shape: {df.shape}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print()

    # Get latest 30 trading days for prediction
    latest_dates = sorted(df['timestamp'].unique())[-30:]

    print(f"Generating predictions for latest {len(latest_dates)} dates")
    print(f"  Latest date: {latest_dates[-1]}")
    print()

    # Filter to latest dates
    df_recent = df[df['timestamp'].isin(latest_dates)].copy()

    # Simple prediction: use alpha_0002 (momentum-like) as proxy
    # In real scenario, would use trained model
    if 'alpha_0002' in df_recent.columns:
        df_recent['y_pred'] = df_recent['alpha_0002']
    else:
        # Fallback: random predictions
        df_recent['y_pred'] = np.random.randn(len(df_recent)) * 0.01

    # Prepare output format matching ML2 format
    predictions = df_recent[['timestamp', 'symbol', 'y_pred']].copy()
    predictions = predictions.dropna()

    # Add baseline prediction (single factor)
    predictions['y_pred_baseline'] = predictions['y_pred'] * 0.5

    # Add y_true if available
    if 'target' in df_recent.columns:
        predictions['y_true'] = df_recent['target']
    else:
        predictions['y_true'] = np.nan

    # Add window_id
    predictions['window_id'] = 999  # Mock window ID

    print(f"Generated predictions:")
    print(f"  Total rows: {len(predictions):,}")
    print(f"  Unique dates: {predictions['timestamp'].nunique()}")
    print(f"  Unique symbols: {predictions['symbol'].nunique()}")
    print(f"  Latest date: {predictions['timestamp'].max()}")
    print()

    # Save to output
    output_dir = Path(__file__).parent.parent / 'data/ml2_results'
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / 'predictions_fresh.parquet'
    predictions.to_parquet(output_file, index=False)

    print(f"✅ Fresh predictions saved: {output_file}")
    print()

    # Also update predictions_8window.parquet for backward compatibility
    output_file_compat = output_dir / 'predictions_8window.parquet'
    predictions.to_parquet(output_file_compat, index=False)
    print(f"✅ Updated predictions_8window.parquet: {output_file_compat}")
    print()

    print("="*80)
    print("Fresh prediction generation completed")
    print("="*80)

    return predictions


if __name__ == '__main__':
    predictions = generate_mock_predictions()

    print()
    print("Sample predictions:")
    print(predictions.tail(10))
