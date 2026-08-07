import pandas as pd

from core.market import get_ticker_data
from core.indicator import get_price_changes
from core.indicator import SMA, AnchoredVWAP, KAMA, BollingerBands, SuperTrend
from core.indicator import WilliamsR, MFI, StochRSI, FisherTransform, MACD, ADX, ATR


def demo_indicator():
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
    result["SMA20"] = SMA(20).calc(df)["SMA"]
    result["AVWAP"] = AnchoredVWAP().calc(df)["AVWAP"]
    result["KAMA"] = KAMA().calc(df)["KAMA"]
    bb = BollingerBands().calc(df)
    result["BBLower"], result["BBMid"], result["BBUpper"] = bb["BB\u2193"], bb["BB"], bb["BB\u2191"]
    result["SuperTrend"] = SuperTrend().calc(df)["S-Trend"]
    result["WilliamsR"] = WilliamsR().calc(df)["%R"]
    result["MFI"] = MFI().calc(df)["MFI"]
    srsi = StochRSI().calc(df)
    result["StochRSI_K"], result["StochRSI_D"] = srsi["%K"], srsi["%D"]
    fisher = FisherTransform().calc(df)
    result["Fisher"], result["FisherSignal"] = fisher["Fisher"], fisher["Fisher\u00b7Sig"]
    macd = MACD().calc(df)
    result["MACD"], result["MACDHist"], result["MACDSignal"] = macd["MACD"], macd["MACD\u00b7Hist"], macd["MACD\u00b7Sig"]
    result["ADX"] = ADX().calc(df)["ADX"]
    result["ATR"] = ATR().calc(df)["ATR"]

    print(result.tail(20))


if __name__ == "__main__":
    demo_indicator()
