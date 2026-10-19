"""
Deprecated entry point, kept so old schedulers still work.

It used to write a placeholder signal (alpha_0002, or random numbers) as
"predictions". It now runs the real daily inference.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_lab.run_daily_inference import main

if __name__ == "__main__":
    sys.exit(main())
