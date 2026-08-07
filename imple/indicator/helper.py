from .classic import SMA, AnchoredVWAP, KAMA, BollingerBands, SuperTrend
from .classic import WilliamsR, MFI, StochRSI, FisherTransform, MACD, ADX, ATR


def get_indicators():
    """Get available indicators"""
    indicators = {
        "SMA": SMA,
        "AVWAP": AnchoredVWAP,
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
        "AVWAP" -> AnchoredVWAP()
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
