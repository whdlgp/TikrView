from core.market import get_ticker_data, get_ticker_info
from imple.forecaster.kronosbase import KronosBase
from imple.forecaster.chronos2 import Chronos2
from imple.forecaster.timesfm import TimesFM


TICKER = "AAPL"
PRED_LEN = 30


def demo_forecaster(ticker=TICKER, pred_len=PRED_LEN):
    info = get_ticker_info(ticker)
    raw_df = get_ticker_data(ticker, date_range="2y", time_interval="1d")
    df = raw_df.copy()

    forecasters = [
        KronosBase(pred_len),
        Chronos2(pred_len),
        TimesFM(pred_len),
    ]

    name = info.get("shortName", ticker)
    current_price = df["Close"].iloc[-1]

    print()
    print(f"{name} ({ticker})")
    print(f"Current Price : ${current_price:.2f}")
    print(f"Forecast     : {pred_len} days")
    print()

    for forecaster in forecasters:
        result = forecaster.calc(df)

        median = result["median"]
        lower = result["lower"]
        upper = result["upper"]

        forecast_price = median.iloc[-1]
        change = (forecast_price / current_price - 1.0) * 100

        print(f"{forecaster.display_name}")
        print(f"  Forecast : ${forecast_price:.2f} ({change:+.2f}%)")
        print(f"  Range    : ${lower.iloc[-1]:.2f} ~ ${upper.iloc[-1]:.2f}")
        print()


if __name__ == "__main__":
    demo_forecaster()