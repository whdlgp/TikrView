import pandas as pd
from abc import ABC, abstractmethod
from enum import Enum


def get_price_changes(df: pd.DataFrame) -> list:
    """
    Percentage price change per [1d, 7d, 30d, 180d, 365d]

    Args:
        df (pd.DataFrame): OHLCV price data indexed by datetime

    Returns:
        list: percentage change for [1d, 7d, 30d, 180d, 365d] ago. Each entry is None if no data.
    """
    if df.empty:
        return [None] * 5

    latest_price = df["Close"].iloc[-1]

    changes = []
    for days in [1, 7, 30, 180, 365]:
        try:
            today = pd.Timestamp.now(tz=df.index.tz)
            ref_date = today - pd.Timedelta(days=days)
            past_price = df[df.index <= ref_date]["Close"].iloc[-1]
            change = (latest_price - past_price) / past_price * 100
        except Exception:
            change = None
        changes.append(change)

    return changes


class Panel(Enum):
    """Draw position of indicator."""
    MAIN = "main"   # overlaid on the main price chart (e.g. SMA)
    SUB = "sub"     # separate subplot below the main chart (e.g. RSI)


class Indicator(ABC):
    """
    Base interface for indicator.

    Attributes:
        panel (Panel): where to draw it (Panel.MAIN or Panel.SUB)
        reference_lines (list[float]): optional horizontal guide values
    """
    panel: Panel
    reference_lines: list[float] = []

    @property
    def display_name(self) -> str:
        """Name of indicator"""
        return type(self).__name__

    @abstractmethod
    def calc(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """
        Compute the indicator values.

        Args:
            df (pd.DataFrame): OHLCV price data

        Returns:
            dict[str, pd.Series]:
                Mapping from output name (e.g. "SMA", "BB\u2193", "MACD-H")
                to a Series, same index as df.
        """
        ...
