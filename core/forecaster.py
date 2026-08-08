from abc import ABC, abstractmethod
import pandas as pd


class Forecaster(ABC):
    """
    Base interface for forecaster.
    """

    @property
    def display_name(self) -> str:
        """Name of forecaster"""
        return type(self).__name__

    @abstractmethod
    def calc(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute the forecast.

        Args:
            df (pd.DataFrame): OHLCV price data

        Returns:
            pd.DataFrame:
                Forecast result indexed by future dates with
                columns: median, lower, upper.
        """
        ...
