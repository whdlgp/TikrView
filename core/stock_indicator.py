import pandas as pd
import pandas_ta as ta
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
        return ta.sma(df["Close"], length=self.period)


class VWAP(Indicator):
    """Volume Weighted Average Price."""
    panel = Panel.MAIN

    def calc(self, df: pd.DataFrame) -> pd.Series:
        # Very long anchor(100Y) for cumulative VWAP.
        return ta.vwap(df["High"], df["Low"], df["Close"], df["Volume"], anchor="100Y")


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
        return ta.kama(df["Close"], length=self.period, fast=self.fast_period, slow=self.slow_period)


class BollingerBands(Indicator):
    """Bollinger Bands."""
    panel = Panel.MAIN

    def __init__(self, period: int = 20, std: float = 2.0):
        self.period = period
        self.std = std

    @property
    def display_name(self):
        return f"BB ({self.period}, {self.std})"

    def calc(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
        bb = ta.bbands(df["Close"], length=self.period, std=self.std)

        lower = bb[f"BBL_{self.period}_{self.std}_{self.std}"]
        mid = bb[f"BBM_{self.period}_{self.std}_{self.std}"]
        upper = bb[f"BBU_{self.period}_{self.std}_{self.std}"]

        return lower, mid, upper


class SuperTrend(Indicator):
    """SuperTrend."""
    panel = Panel.MAIN

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        self.period = period
        self.multiplier = multiplier

    @property
    def display_name(self):
        return f"SuperTrend ({self.period}, {self.multiplier})"

    def calc(self, df: pd.DataFrame) -> pd.Series:
        st = ta.supertrend(df["High"], df["Low"], df["Close"], length=self.period, multiplier=self.multiplier)

        return st[f"SUPERT_{self.period}_{self.multiplier}"]


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
        return ta.willr(df["High"], df["Low"], df["Close"], length=self.period)


class MFI(Indicator):
    """Money Flow Index."""
    panel = Panel.SUB
    reference_lines = [20, 80]

    def __init__(self, period: int = 14):
        self.period = period

    def calc(self, df: pd.DataFrame) -> pd.Series:
        return ta.mfi(df["High"], df["Low"], df["Close"], df["Volume"], length=self.period)


class StochRSI(Indicator):
    """Stochastic RSI."""
    panel = Panel.SUB
    reference_lines = [20, 80]

    def __init__(self, period: int = 14, smooth_k: int = 2, smooth_d: int = 3):
        self.period = period
        self.smooth_k = smooth_k
        self.smooth_d = smooth_d

    @property
    def display_name(self):
        return f"StochRSI ({self.period}, {self.smooth_k}, {self.smooth_d})"

    def calc(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        srsi = ta.stochrsi(df["Close"], length=self.period, rsi_length=self.period,
                            k=self.smooth_k, d=self.smooth_d, mamode="sma")

        k = srsi[f"STOCHRSIk_{self.period}_{self.period}_{self.smooth_k}_{self.smooth_d}"]
        d = srsi[f"STOCHRSId_{self.period}_{self.period}_{self.smooth_k}_{self.smooth_d}"]

        return k, d


class FisherTransform(Indicator):
    """Fisher Transform."""
    panel = Panel.SUB
    reference_lines = [-2, -1, 0, 1, 2]

    def __init__(self, period: int = 10, signal: int = 3):
        self.period = period
        self.signal = signal

    @property
    def display_name(self):
        return f"Fisher ({self.period}, {self.signal})"

    def calc(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        fisher = ta.fisher(df["High"], df["Low"], length=self.period, signal=self.signal)

        return fisher[f"FISHERT_{self.period}_{self.signal}"], fisher[f"FISHERTs_{self.period}_{self.signal}"]


class MACD(Indicator):
    """Moving Average Convergence Divergence."""
    panel = Panel.SUB
    reference_lines = [0]

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    @property
    def display_name(self):
        return f"MACD ({self.fast}, {self.slow}, {self.signal})"

    def calc(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
        macd = ta.macd(df["Close"], fast=self.fast, slow=self.slow, signal=self.signal)

        line = macd[f"MACD_{self.fast}_{self.slow}_{self.signal}"]
        hist = macd[f"MACDh_{self.fast}_{self.slow}_{self.signal}"]
        signal = macd[f"MACDs_{self.fast}_{self.slow}_{self.signal}"]

        return line, hist, signal


class ADX(Indicator):
    """Average Directional Index."""
    panel = Panel.SUB
    reference_lines = [20, 25]

    def __init__(self, period: int = 14):
        self.period = period

    @property
    def display_name(self):
        return f"ADX ({self.period})"

    def calc(self, df: pd.DataFrame) -> pd.Series:
        adx = ta.adx(df["High"], df["Low"], df["Close"], length=self.period)

        return adx[f"ADX_{self.period}"]


class ATR(Indicator):
    """Average True Range."""
    panel = Panel.SUB

    def __init__(self, period: int = 14):
        self.period = period

    @property
    def display_name(self):
        return f"ATR ({self.period})"

    def calc(self, df: pd.DataFrame) -> pd.Series:
        return ta.atr(df["High"], df["Low"], df["Close"], length=self.period)


def get_indicators():
    """Get available indicators"""
    indicators = {
        "SMA": SMA,
        "VWAP": VWAP,
        "KAMA": KAMA,
        "BBANDS": BollingerBands,
        "SUPERTREND": SuperTrend,
        "WILLIAMSR": WilliamsR,
        "MFI": MFI,
        "STOCHRSI": StochRSI,
        "FISHER": FisherTransform,
        "MACD": MACD,
        "ADX": ADX,
        "ATR": ATR,
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
    result["BBLower"], result["BBMid"], result["BBUpper"] = BollingerBands().calc(df)
    result["SuperTrend"] = SuperTrend().calc(df)
    result["WilliamsR"] = WilliamsR().calc(df)
    result["MFI"] = MFI().calc(df)
    result["StochRSI_K"], result["StochRSI_D"] = StochRSI().calc(df)
    result["Fisher"], result["FisherSignal"] = FisherTransform().calc(df)
    result["MACD"], result["MACDHist"], result["MACDSignal"] = MACD().calc(df)
    result["ADX"] = ADX().calc(df)
    result["ATR"] = ATR().calc(df)

    print(result.tail(20))