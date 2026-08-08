from abc import ABC, abstractmethod
import pandas as pd


class Forecaster(ABC):
    """
    Base interface for forecaster.
    """
    _model_cache = {}

    @classmethod
    def get_cached_model(cls, key):
        model = cls._model_cache.get(key)
        #print(f"[ModelCache] {'HIT' if model is not None else 'MISS'}: {key}")
        return model

    @classmethod
    def cache_model(cls, key, value):
        #print(f"[ModelCache] STORED: {key}")
        cls._model_cache[key] = value
        return value

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
