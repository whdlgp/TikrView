from core.market import get_ticker_info, get_ticker_data


def demo_market():
    from pprint import pprint
    info = get_ticker_info("AGNC")
    info_summary_keys = ["longName", "sector", "industry", "currentPrice", "marketCap", "trailingPE", "dividendYield", "fiftyTwoWeekLow", "fiftyTwoWeekHigh"]
    pprint(f"Ticker info ({type(info)})")
    pprint({k: info.get(k) for k in info_summary_keys})

    df = get_ticker_data("AGNC", date_range="1mo", time_interval="1d")
    pprint(f"Ticker Data ({type(df)})")
    pprint(df.head())


if __name__ == "__main__":
    demo_market()