from pathlib import Path
import pandas as pd

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def _table_path(name: str) -> Path:
    """Return path to CSV for logical table name."""
    return DATA_DIR / f"{name}.csv"


def load_table(name: str, columns=None) -> pd.DataFrame:
    """
    Load CSV table. If it doesn't exist, return empty DataFrame
    with given columns (if provided).
    """
    path = _table_path(name)
    if path.exists():
        df = pd.read_csv(path)
    else:
        if columns is None:
            df = pd.DataFrame()
        else:
            df = pd.DataFrame(columns=columns)
    return df


def save_table(df: pd.DataFrame, name: str) -> None:
    """Save DataFrame to CSV (overwrite)."""
    path = _table_path(name)
    df.to_csv(path, index=False)
