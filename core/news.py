import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from datetime import datetime, timedelta

import feedparser

from .market import get_ticker_info
from .etf import ETFHoldingsClient


class NewsSearchClient:
    """
    Fetches recent news via Google News RSS for a set of search queries.

    Usage:
        client = NewsSearchClient()
        news = client.fetch_news(["NVDA", "Nvidia Corp"])
    """

    def __init__(self, max_news_workers=8):
        self.max_news_workers = max_news_workers

    def search(self, queries, days=5):
        """
        Search recent news from Google News RSS.

        Args:
            queries (list[str]): Search queries.
            days (int): Only include news published within the given number of days.

        Returns:
            list[dict]: News items sorted by published date in descending order.
        """
        cutoff = datetime.now() - timedelta(days=days)
        news_items = []

        with ThreadPoolExecutor(max_workers=self.max_news_workers) as executor:
            futures = {executor.submit(self._fetch_one_query, q, cutoff): q for q in queries}
            for future in as_completed(futures):
                try:
                    news_items.extend(future.result())
                except Exception as e:
                    print(f"Failed fetching news for '{futures[future]}': {e}")

        seen_links = set()
        unique_news = []
        for item in news_items:
            if item["link"] not in seen_links:
                seen_links.add(item["link"])
                unique_news.append(item)
        unique_news.sort(key=lambda x: x["published"], reverse=True)
        return unique_news

    @staticmethod
    def _fetch_one_query(query, cutoff):
        q_encoded = quote(query)
        rss_url = f"https://news.google.com/rss/search?q={q_encoded}"
        feed = feedparser.parse(rss_url)
        items = []
        for entry in feed.entries:
            published_struct = getattr(entry, "published_parsed", None)
            if not published_struct:
                continue
            published_dt = datetime(*published_struct[:6])
            if published_dt < cutoff:
                continue
            items.append(
                {
                    "query": query,
                    "title": entry.title,
                    "link": entry.link,
                    "published": published_dt,
                    "summary": entry.summary,
                }
            )
        return items


class TickerNewsClient:
    """
    Combines ETFHoldingsClient and NewsSearchClient so any ticker symbol
    (stock or ETF) can be turned into search queries and searched for news
    in one call.

    Usage:
        client = TickerNewsClient()

        # Simple
        news = client.get_news_for_ticker("SCHD")
    """

    def __init__(self, timeout=15, max_news_workers=8, session=None):
        self.holdings = ETFHoldingsClient(timeout=timeout, session=session)
        self.news = NewsSearchClient(max_news_workers=max_news_workers)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        try:
            self.holdings.close()
        except Exception:
            pass

    def close(self):
        self.holdings.close()

    def build_search_queries(self, ticker_symbol, min_weight=0.01, top_n=None):
        """
        Build search queries for a stock or ETF.

        Args:
            ticker_symbol (str): Stock or ETF ticker symbol.
            min_weight (float): Minimum holding weight to include when building ETF queries (0-1 scale).
            top_n (int | None): Maximum number of holdings to include when building ETF queries.

        Returns:
            list[str]: Search queries without duplicates.
        """
        try:
            info = get_ticker_info(ticker_symbol)
        except Exception:
            info = {}
        queries = set()

        queries.add(ticker_symbol)
        long_name = info.get("longName") or info.get("shortName")
        if long_name:
            queries.add(long_name)

        if info.get("quoteType", "").upper() == "ETF":
            queries.add(f"{ticker_symbol} ETF")
            if long_name and "ETF" not in long_name.upper():
                queries.add(f"{long_name} ETF")

            holdings = self.holdings.get_holding_descriptions(ticker_symbol, min_weight=min_weight, top_n=top_n)
            for holding in holdings:
                queries.add(f"{holding} stock")
        return list(queries)

    def get_news_for_ticker(self, ticker_symbol, min_weight=0.01, top_n=None, days=5):
        """
        Fetch recent news for a stock or ETF.

        Args:
            ticker_symbol (str): Stock or ETF ticker symbol.
            min_weight (float): Minimum holding weight to include when building ETF queries (0-1 scale).
            top_n (int | None): Maximum number of holdings to include when building ETF queries.
            days (int): Only include news published within the given number of days.

        Returns:
            list[dict]: News items sorted by published date in descending order.
        """
        queries = self.build_search_queries(ticker_symbol, min_weight=min_weight, top_n=top_n)
        return self.news.search(queries, days=days)


def _test_news_search_client():
    query_sets = {
        "NVDA": ["NVDA", "Nvidia Corp"],
        "SCHD": ["SCHD ETF", "Schwab US Dividend Equity ETF"],
        "SPY": ["SPY ETF", "SPDR S&P 500 ETF"],
    }

    client = NewsSearchClient()
    for label, queries in query_sets.items():
        print(f"\n{'=' * 60}")
        print(f"=== {label} ===")
        print("=" * 60)

        t0 = time.time()
        news = client.search(queries, days=5)
        elapsed_news = time.time() - t0

        if not news:
            print(f"[FAIL] {label}: no news found")
            continue

        print(f"[OK] news: {len(news)} items, {elapsed_news:.2f}s")

        links = [n["link"] for n in news]
        no_dup_links = len(links) == len(set(links))
        dates = [n["published"] for n in news]
        is_news_sorted_desc = all(dates[i] >= dates[i + 1] for i in range(len(dates) - 1))
        print(f"[{'OK' if no_dup_links else 'FAIL'}] no duplicate links: {no_dup_links}")
        print(f"[{'OK' if is_news_sorted_desc else 'FAIL'}] sorted by published date descending: {is_news_sorted_desc}")

        print("  latest 3 news items:")
        for item in news[:3]:
            print(f"    [{item['published']:%Y-%m-%d %H:%M}] ({item['query']}) {item['title']}")


def _test_ticker_news_client():
    tickers = ["NVDA", "SCHD", "SPY", "QQQ", "VOO", "SCHB"]

    with TickerNewsClient() as client:
        for ticker in tickers:
            print(f"\n{'=' * 60}")
            print(f"=== {ticker} ===")
            print("=" * 60)

            # Create search queries
            t0 = time.time()
            queries = client.build_search_queries(ticker, min_weight=0.01)
            elapsed_queries = time.time() - t0

            if not queries:
                print(f"[FAIL] {ticker}: no search queries generated")
                continue

            print(f"[OK] queries: {len(queries)} generated, {elapsed_queries:.2f}s")
            print(f"  sample: {queries[:5]}")

            # Let's search news!
            t1 = time.time()
            news = client.get_news_for_ticker(ticker, min_weight=0.01)
            elapsed_news = time.time() - t1

            if not news:
                print(f"[FAIL] {ticker}: no news found")
                continue

            print(f"[OK] news: {len(news)} items, {elapsed_news:.2f}s")

            links = [n["link"] for n in news]
            no_dup_links = len(links) == len(set(links))
            dates = [n["published"] for n in news]
            is_news_sorted_desc = all(dates[i] >= dates[i + 1] for i in range(len(dates) - 1))
            print(f"[{'OK' if no_dup_links else 'FAIL'}] no duplicate links: {no_dup_links}")
            print(f"[{'OK' if is_news_sorted_desc else 'FAIL'}] sorted by published date descending: {is_news_sorted_desc}")

            print("  latest 3 news items:")
            for item in news[:3]:
                print(f"    [{item['published']:%Y-%m-%d %H:%M}] ({item['query']}) {item['title']}")

            print(f"\n  total time: {elapsed_queries + elapsed_news:.2f}s (queries {elapsed_queries:.2f}s / news {elapsed_news:.2f}s)")


if __name__ == "__main__":
    #_test_news_search_client()
    _test_ticker_news_client()