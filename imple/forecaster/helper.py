from .kronosbase import KronosBase
from .chronos2 import Chronos2
from .timesfm import TimesFM


def get_forecasters():
    """Get available forecasters"""
    forecasters = {
        "KRONOS": KronosBase,
        "CHRONOS2": Chronos2,
        "TIMESFM": TimesFM,
    }
    return forecasters


def parse_forecaster(forecaster_str: str):
    """
    Parse forecaster string to Forecaster instance.

    Examples:
        "Kronos:30" -> KronosBase(30)
        "Kronos:30,400,30,1.0,0.9" -> KronosBase(30, 400, 30, 1.0, 0.9)
        "Chronos2:30" -> Chronos2(30)
        "TimesFM:30" -> TimesFM(30)

    Args:
        forecaster_str (str): Forecaster string in the format
            "NAME[:param1,param2,...]".

    Returns:
        Forecaster: Parsed forecaster instance.

    Raises:
        ValueError: If the forecaster name is unknown or the parameters
            are invalid.
    """
    if ":" in forecaster_str:
        name, param_str = forecaster_str.split(":", 1)
        raw_params = param_str.split(",")
    else:
        name, raw_params = forecaster_str, []

    forecaster_map = get_forecasters()
    key = name.strip().upper()

    if key not in forecaster_map:
        available = ", ".join(sorted(forecaster_map))
        raise ValueError(f"Unknown forecaster '{name}'. Available: {available}")

    cls = forecaster_map[key]

    params = []
    for p in raw_params:
        p = p.strip()
        try:
            params.append(int(p))
        except ValueError:
            try:
                params.append(float(p))
            except ValueError:
                params.append(p)

    try:
        return cls(*params)
    except TypeError as e:
        raise ValueError(f"Invalid parameters for '{name}': {e}")