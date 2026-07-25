import yfinance as yf
import pandas as pd

def get_ticker_info(ticker_name: str) -> dict:
    """
    Get ticker information from Yahoo Finance.

    Args:
        ticker_name (str): stock ticker symbol (e.g. "AGNC", "AAPL")

    Returns:
        dict: ticker info with keys.

    Note:
        - identifiers
            - symbol, shortName, longName, displayName, quoteType, exchange, fullExchangeName, currency
        - price (current session)
            - previousClose, open, dayLow, dayHigh, currentPrice, regularMarketPrice
        - price range
            - fiftyTwoWeekLow, fiftyTwoWeekHigh, allTimeHigh, allTimeLow, fiftyDayAverage, twoHundredDayAverage
        - valuation
            - marketCap, enterpriseValue, trailingPE, forwardPE, priceToBook, pegRatio, priceToSalesTrailing12Months
        - dividend
            - dividendRate, dividendYield, exDividendDate, payoutRatio, fiveYearAvgDividendYield, lastDividendValue
        - financials
            - totalRevenue, totalCash, totalDebt, netIncomeToCommon, grossProfits, revenuePerShare
        - profitability ratios
            - profitMargins, operatingMargins, grossMargins, returnOnAssets, returnOnEquity
        - analyst ratings
            - targetHighPrice, targetLowPrice, targetMeanPrice, recommendationMean, recommendationKey, numberOfAnalystOpinions
        - per-share metrics
            - bookValue, trailingEps, forwardEps, epsCurrentYear, epsTrailingTwelveMonths
        - volume
            - volume, regularMarketVolume, averageVolume, averageVolume10days
        - company profile
            - industry, sector, longBusinessSummary, fullTimeEmployees, companyOfficers
        - shares/ownership
            - sharesOutstanding, floatShares, sharesShort, heldPercentInsiders, heldPercentInstitutions, shortRatio
        - bid/ask
            - bid, ask, bidSize, askSize
        - liquidity
            - quickRatio, currentRatio, debtToEquity
        - market state
            - marketState, exchangeTimezoneName, regularMarketTime, postMarketTime
        - price (extended hours)
            - postMarketPrice, postMarketChange, postMarketChangePercent
        - corporate actions
            - corporateActions, earningsTimestamp, dividendDate
        - governance/risk
            - auditRisk, boardRisk, compensationRisk, shareHolderRightsRisk, overallRisk
        - address
            - address1, address2, city, state, zip, country, phone, fax, website
    """
    ticker_obj = yf.Ticker(ticker_name)
    info = ticker_obj.info

    return info


def get_ticker_data(ticker_name: str, date_range: str, time_interval: str, timezone: str = "Asia/Seoul") -> pd.DataFrame:
    """
    Get price data of ticker from Yahoo Finance.

    Args:
        ticker_name (str): stock ticker symbol (e.g. "AGNC", "AAPL")
        date_range (str): how much history to fetch.
            Valid values: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        time_interval (str): gap between each data point.
            Valid values: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        timezone (str): timezone to convert the index to (default: "Asia/Seoul")

    Returns:
        pandas.DataFrame: OHLCV price data indexed by datetime, converted
            to the given timezone. Columns: Open, High, Low, Close, Volume
    """
    # Download from Yahoo Finance.
    df = yf.download(ticker_name, period=date_range, interval=time_interval, progress=False)

    # Only price data.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Change timezone.
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert(timezone)
    else:
        df.index = df.index.tz_convert(timezone)

    return df


if __name__ == "__main__":
    from pprint import pprint
    info = get_ticker_info("AGNC")
    info_summary_keys = ["longName", "sector", "industry", "currentPrice", "marketCap", "trailingPE", "dividendYield", "fiftyTwoWeekLow", "fiftyTwoWeekHigh"]
    pprint(f"Ticker info ({type(info)})")
    pprint({k: info.get(k) for k in info_summary_keys})

    df = get_ticker_data("AGNC", date_range="1mo", time_interval="1d")
    pprint(f"Ticker Data ({type(df)})")
    pprint(df.head())