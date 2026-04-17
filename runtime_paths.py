"""
Shared runtime path resolution for Godfather V9.0.

Keeps data lake path selection in one place so scripts can run after moving
the quant_lab repo without hardcoding machine-specific Desktop paths.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


DATA_LAKE_ROOT_ENV = "GODFATHER_DATA_LAKE_ROOT"
UNIVERSE_PATH_ENV = "GODFATHER_UNIVERSE_PATH"
REPO_ROOT = Path(__file__).resolve().parent
REPO_DATA_LAKE_ROOT = REPO_ROOT / "data" / "data_lake"
REPO_UNIVERSE_PATH = REPO_ROOT / "data" / "universe" / "sp500_universe.csv"
LEGACY_DISABLED_DATA_LAKE_ROOTS = (
    Path.home() / "v7_empire" / "v8_empire" / "data_lake",
    Path.home() / "Desktop" / "v7_empire" / "v8_empire" / "data_lake",
)


def _candidate_data_lake_roots() -> list[Path]:
    candidates: list[Path] = []
    env_root = os.getenv(DATA_LAKE_ROOT_ENV)
    if env_root:
        candidates.append(Path(env_root).expanduser())
    candidates.append(REPO_DATA_LAKE_ROOT)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def _is_readable_file(path: Path) -> bool:
    try:
        return path.is_file() and os.access(path, os.R_OK)
    except OSError:
        return False


def _is_readable_dir(path: Path) -> bool:
    try:
        return path.is_dir() and os.access(path, os.R_OK | os.X_OK)
    except OSError:
        return False


@lru_cache(maxsize=1)
def get_data_lake_root() -> Path:
    for candidate in _candidate_data_lake_roots():
        if _is_readable_dir(candidate / "prices"):
            return candidate

    checked = ", ".join(str(path) for path in _candidate_data_lake_roots())
    legacy = ", ".join(str(path) for path in LEGACY_DISABLED_DATA_LAKE_ROOTS)
    raise FileNotFoundError(
        "No launchd-safe Godfather data lake root found. "
        f"Checked active candidates: {checked}. "
        f"Legacy roots intentionally disabled: {legacy}"
    )


def get_price_lake_dir() -> Path:
    return get_data_lake_root() / "prices"


def get_price_lake_glob() -> str:
    return str(get_price_lake_dir() / "*.parquet")


def _candidate_universe_paths() -> list[Path]:
    candidates: list[Path] = []

    env_path = os.getenv(UNIVERSE_PATH_ENV)
    if env_path:
        candidates.append(Path(env_path).expanduser())

    # Keep a launchd-safe local copy inside the runtime repo.
    candidates.append(REPO_UNIVERSE_PATH)

    try:
        candidates.append(get_data_lake_root() / "universe" / "sp500_universe.csv")
    except FileNotFoundError:
        pass

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def get_universe_path() -> Path:
    for candidate in _candidate_universe_paths():
        if _is_readable_file(candidate):
            return candidate

    checked = ", ".join(str(path) for path in _candidate_universe_paths())
    raise FileNotFoundError(
        f"No readable Godfather universe file found. Checked: {checked}"
    )


def get_runtime_path_report() -> dict[str, str]:
    env_data_lake_root = os.getenv(DATA_LAKE_ROOT_ENV) or "unset"
    env_universe_path = os.getenv(UNIVERSE_PATH_ENV) or "unset"
    data_lake_root = get_data_lake_root()
    return {
        "ENV_GODFATHER_DATA_LAKE_ROOT": env_data_lake_root,
        "ENV_GODFATHER_UNIVERSE_PATH": env_universe_path,
        "RESOLVED_DATA_LAKE_ROOT": str(data_lake_root),
        "RESOLVED_PRICE_PATH": str(get_price_lake_dir()),
        "RESOLVED_UNIVERSE_PATH": str(get_universe_path()),
    }
