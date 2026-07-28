import pandas as pd
import numpy as np
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
    def calc(self, df: pd.DataFrame) -> pd.Series | tuple[pd.Series, ...]:
        """
        Compute the indicator values.

        Args:
            df (pd.DataFrame): OHLCV price data

        Returns:
            pd.Series | tuple[pd.Series, ...]:
                One or more indicator series, same index as df.
        """
        ...


class SMA(Indicator):
    """Simple Moving Average."""
    panel = Panel.MAIN

    def __init__(self, period: int):
        self.period = period

    @property
    def display_name(self):
        return f"SMA ({self.period})"

    def calc(self, df: pd.DataFrame) -> pd.Series:
        return df["Close"].rolling(self.period).mean()


class VWAP(Indicator):
    """Volume Weighted Average Price."""
    panel = Panel.MAIN

    def calc(self, df: pd.DataFrame) -> pd.Series:
        typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
        cumulative_price_volume = (typical_price * df["Volume"]).cumsum()
        cumulative_volume = df["Volume"].cumsum()

        return cumulative_price_volume / cumulative_volume


class KAMA(Indicator):
    """Kaufman's Adaptive Moving Average."""
    panel = Panel.MAIN

    def __init__(self, period: int = 10, fast_period: int = 2, slow_period: int = 30):
        self.period = period
        self.fast_period = fast_period
        self.slow_period = slow_period

    @property
    def display_name(self):
        return f"KAMA ({self.period})"

    def calc(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"]

        change = close.diff(self.period).abs()
        volatility = close.diff().abs().rolling(self.period).sum()
        efficiency = (change / volatility.replace(0, np.nan)).fillna(0)

        fast = 2.0 / (self.fast_period + 1)
        slow = 2.0 / (self.slow_period + 1)
        factor = (efficiency * (fast - slow) + slow) ** 2

        kama = pd.Series(np.nan, index=df.index)

        start_idx = self.period
        if len(df) <= self.period:
            start_idx = len(df) - 1

        if start_idx < 0:
            return kama

        kama.iloc[start_idx] = close.iloc[start_idx]

        for i in range(start_idx + 1, len(df)):
            prev = kama.iloc[i - 1]
            price = close.iloc[i]
            weight = factor.iloc[i]
            kama.iloc[i] = prev + weight * (price - prev)

        return kama


class WilliamsR(Indicator):
    """Williams %R."""
    panel = Panel.SUB
    reference_lines = [-20, -80]

    def __init__(self, period: int = 14):
        self.period = period

    @property
    def display_name(self):
        return f"Williams %R ({self.period})"

    def calc(self, df: pd.DataFrame) -> pd.Series:
        high = df["High"].rolling(self.period).max()
        low = df["Low"].rolling(self.period).min()

        return (high - df["Close"]) / (high - low) * -100


class MFI(Indicator):
    """Money Flow Index."""
    panel = Panel.SUB
    reference_lines = [20, 80]

    def __init__(self, period: int = 14):
        self.period = period

    def calc(self, df: pd.DataFrame) -> pd.Series:
        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        flow = typical * df["Volume"]
        direction = typical.diff() > 0

        pos_flow = flow.where(direction, 0).rolling(self.period).sum()
        neg_flow = flow.where(~direction, 0).rolling(self.period).sum()

        return 100 - (100 / (1 + (pos_flow / neg_flow)))


class StochRSI(Indicator):
    """Stochastic RSI."""
    panel = Panel.SUB
    reference_lines = [20, 80]

    def __init__(self, period: int = 14, smooth_k: int = 3, smooth_d: int = 3):
        self.period = period
        self.smooth_k = smooth_k
        self.smooth_d = smooth_d

    @property
    def display_name(self):
        return (
            f"StochRSI "
            f"({self.rsi_period}, "
            f"{self.stoch_period}, "
            f"{self.smooth_period})"
        )

    def calc(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(self.period).mean()
        avg_loss = loss.rolling(self.period).mean()

        strength = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + strength))

        min_rsi = rsi.rolling(self.period).min()
        max_rsi = rsi.rolling(self.period).max()

        stoch_rsi = (rsi - min_rsi) / (max_rsi - min_rsi)
        k = stoch_rsi.rolling(self.smooth_k).mean() * 100
        d = k.rolling(self.smooth_d).mean()

        return k, d


class FisherTransform(Indicator):
    """Fisher Transform."""
    panel = Panel.SUB
    reference_lines = [-2, -1, 0, 1, 2]

    def __init__(self, period: int = 10):
        self.period = period

    @property
    def display_name(self):
        return f"Fisher ({self.period})"

    def calc(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        import numpy as np

        price = (df["High"] + df["Low"]) / 2
        high = price.rolling(self.period).max()
        low = price.rolling(self.period).min()

        value = 2 * (price - low) / (high - low) - 1
        value = value.clip(-0.999, 0.999)

        fisher = 0.5 * np.log((1 + value) / (1 - value))
        signal = fisher.ewm(span=5, adjust=False).mean()

        return fisher, signal


def get_indicators():
    """Get available indicators"""
    indicators = {
        "SMA": SMA,
        "VWAP": VWAP,
        "KAMA": KAMA,
        "WILLIAMSR": WilliamsR,
        "MFI": MFI,
        "STOCHRSI": StochRSI,
        "FISHER": FisherTransform,
    } 
    return indicators


def parse_indicator(indicator_str: str):
    """
    Parse indicator string to Indicator instance.

    Examples:
        "SMA:20" -> SMA(20)
        "VWAP" -> VWAP()
        "StochRSI:14,3,3" -> StochRSI(14, 3, 3)

    Args:
        indicator_str (str): Indicator string in the format
            "NAME[:param1,param2,...]".

    Returns:
        Indicator: Parsed indicator instance.

    Raises:
        ValueError: If the indicator name is unknown or the parameters are invalid.
    """
    if ":" in indicator_str:
        name, param_str = indicator_str.split(":", 1)
        raw_params = param_str.split(",")
    else:
        name, raw_params = indicator_str, []

    indicator_map = get_indicators()
    key = name.strip().upper()
    if key not in indicator_map:
        available = ", ".join(sorted(indicator_map))
        raise ValueError(f"Unknown indicator '{name}'. Available: {available}")

    cls = indicator_map[key]

    params = []
    for p in raw_params:
        p = p.strip()
        try:
            params.append(int(p))
        except ValueError:
            params.append(float(p))

    try:
        return cls(*params)
    except TypeError as e:
        raise ValueError(f"Invalid parameters for '{name}': {e}")


if __name__ == "__main__":
    from market_client import get_ticker_data

    # Test price change
    tickers = ["AGNC", "AAPL", "TSLA", "O", "SPY", "INVALIDTICKER123"]
    labels = ["1D", "1W", "1M", "6M", "1Y"]

    for ticker in tickers:
        df = get_ticker_data(ticker, "1y", "1d", "Asia/Seoul")
        price_change = get_price_changes(df)

        print(f"{ticker}:", end="\t")
        for label, change in zip(labels, price_change):
            print(f"{label}: {change:+.2f}%" if change is not None else f"{label}: N/A", end="\t")
        print()

    # Test indicators
    df = get_ticker_data("AGNC", "1y", "1d", "Asia/Seoul")
    result = pd.DataFrame(index=df.index)

    result["Close"] = df["Close"]
    result["SMA20"] = SMA(20).calc(df)
    result["VWAP"] = VWAP().calc(df)
    result["KAMA"] = KAMA().calc(df)
    result["WilliamsR"] = WilliamsR().calc(df)
    result["MFI"] = MFI().calc(df)
    result["StochRSI_K"], result["StochRSI_D"] = StochRSI().calc(df)
    result["Fisher"], result["FisherSignal"] = FisherTransform().calc(df)

    print(result.tail(20))