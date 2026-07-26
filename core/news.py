"""
News search client for stocks and ETFs
- ETFHoldingsClient: Fast, browser-free ETF holdings scraper.
    reverse-engineered from a HAR capture of schwab.wallst.com's ETF holdings page
- NewsSearchClient: Search news via Google News RSS.
- TickerNewsClient: Combines the two above. Not only ETFs, it can search stocks also.

This code inspired from holdings_dl project
by PiperBatey, available at:
    https://github.com/PiperBatey/holdings_dl
Licensed under the MIT License.
"""

import base64
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from datetime import datetime, timedelta

import requests
import feedparser

from .market_client import get_ticker_info


class ETFHoldingsClient:
    """
    Get ETF holdings info from schwab.wallst.com's internal API.

    Usage:
        client = ETFHoldingsClient()
        holdings = client.get_holdings("SCHD")
        descriptions = client.get_holding_descriptions("SCHD")
    """

    HOLDINGS_PAGE_URL = (
        "https://www.schwab.wallst.com/schwab/Prospect/research/etfs/schwabETF/"
        "index.asp?type=holdings&symbol={symbol}"
    )
    MODULE_API_BASE = (
        "https://www.schwab.wallst.com/schwab/Prospect/research/resources/"
        "server/Module/SchwabETF.ModuleAPI.asp"
    )

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }

    def __init__(self, timeout=15, session=None):
        self.timeout = timeout
        self.session = session or requests.Session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def close(self):
        self.session.close()

    def get_holdings(self, etf_symbol, min_weight=0.01, top_n=None):
        """
        Get holdings for an ETF.

        Args:
            etf_symbol (str): ETF ticker symbol (e.g. "SCHD", "SPY").
            min_weight (float): Minimum portfolio weight to include (0-1 scale). Ignored if top_n is specified.
            top_n (int | None): Maximum number of holdings to return, sorted by portfolio weight in descending order.

        Returns:
            list[dict]: ETF holdings sorted by portfolio weight in descending order.
        """
        session_id, wsodissue = self._get_session_info(etf_symbol)
        if not session_id or not wsodissue:
            print(f"Could not locate session token / wsodissue for {etf_symbol}")
            return []

        first_page = self._fetch_holdings_page(etf_symbol, session_id, wsodissue, page=1)
        total = self._extract_total_matches(first_page) or 0
        num_pages = max(1, -(-total // 60))  # ceil division

        all_rows = self._extract_rows(first_page)

        if top_n is not None:
            # Rows come back sorted by weight descending, so we only need
            # to keep pulling pages until we have enough to satisfy top_n.
            page = 2
            while len(all_rows) < top_n and page <= num_pages:
                page_data = self._fetch_holdings_page(etf_symbol, session_id, wsodissue, page=page)
                rows = self._extract_rows(page_data)
                if not rows:
                    break
                all_rows.extend(rows)
                page += 1
            return all_rows[:top_n]

        for page in range(2, num_pages + 1):
            page_data = self._fetch_holdings_page(etf_symbol, session_id, wsodissue, page=page)
            rows = self._extract_rows(page_data)
            if not rows:
                break
            all_rows.extend(rows)
            # Once we drop below min_weight there's no point requesting
            # further pages, since rows are already sorted descending.
            if rows[-1]["weight"] < min_weight:
                break

        return [r for r in all_rows if r["weight"] >= min_weight]

    def get_holding_descriptions(self, etf_symbol, min_weight=0.01, top_n=None):
        """
        Get holdings for an ETF and extract descriptions.

        Args:
            etf_symbol (str): ETF ticker symbol.
            min_weight (float): Minimum holding weight to include (0-1 scale).
            top_n (int | None): If given, return only the largest holdings regardless of min_weight.

        Returns:
            list[str]: Unique holding descriptions sorted by portfolio weight in descending order.
        """
        holdings = self.get_holdings(etf_symbol, min_weight=min_weight, top_n=top_n)
        seen = set()
        descriptions = []
        for h in holdings:
            d = str(h["description"]).strip()
            if d not in seen:
                seen.add(d)
                descriptions.append(d)
        return descriptions

    def _get_session_info(self, symbol):
        """Load the holdings page once and pull out sessionID + wsodissue."""
        resp = self.session.get(
            self.HOLDINGS_PAGE_URL.format(symbol=symbol),
            headers=self.DEFAULT_HEADERS,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        html = resp.text

        session_id_match = re.search(r"WSOD_DATA\.sessionID\s*=\s*'([^']+)'", html)
        wsodissue_match = re.search(r"gSymbolWSODIssue\s*=\s*'([^']+)'", html)

        if not session_id_match or not wsodissue_match:
            return None, None
        return session_id_match.group(1), wsodissue_match.group(1)

    def _fetch_holdings_page(self, symbol, session_id, wsodissue, page, num_rows=60):
        """POST for a single page of the holdings table, return parsed JSON."""
        payload = {
            "module": "schwabETFHoldingsTable",
            "moduleArgs": {
                "ModuleID": "holdingsTableContainer",
                "symbol": symbol.upper(),
                "wsodissue": wsodissue,
                "sortDir": "desc",
                "sortBy": "PctNetAssets",
                "page": page,
                "numRows": str(num_rows),
            },
        }
        encoded = base64.b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode()
        form_data = {
            "inputs": "B64ENC" + encoded,
            "..contenttype..": "text/javascript",
            "..requester..": "ContentBuffer",
        }

        post_headers = dict(self.DEFAULT_HEADERS)
        post_headers["Referer"] = self.HOLDINGS_PAGE_URL.format(symbol=symbol)
        post_headers["Origin"] = "https://www.schwab.wallst.com"
        post_headers["X-Requested-With"] = "XMLHttpRequest"

        url = f"{self.MODULE_API_BASE}?{session_id}"
        resp = self.session.post(url, headers=post_headers, data=form_data, timeout=self.timeout)
        if not resp.ok:
            print(f"[ETFHoldingsClient] POST failed ({resp.status_code}) for {symbol} page {page}")
            print(f"[ETFHoldingsClient] response body (first 500 chars): {resp.text[:500]}")
        resp.raise_for_status()

        text = resp.text.strip()
        text = re.sub(r"^this\.apiReturn\s*=\s*", "", text)
        text = re.sub(r";\s*$", "", text)
        return json.loads(text)

    @staticmethod
    def _find_node_by_id(node, target_id):
        if isinstance(node, dict):
            if isinstance(node.get("a"), dict) and node["a"].get("id") == target_id:
                return node
            for v in node.values():
                found = ETFHoldingsClient._find_node_by_id(v, target_id)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = ETFHoldingsClient._find_node_by_id(item, target_id)
                if found is not None:
                    return found
        return None

    @classmethod
    def _extract_total_matches(cls, data):
        """Pull the 'of N matches' total out of the pagination block."""
        pagination = cls._find_node_by_id(data, "PaginationContainer")
        if pagination is None:
            return None
        for child in pagination.get("c", []):
            if isinstance(child, dict) and child.get("t") == "p":
                for item in child.get("c", []):
                    if isinstance(item, (int, float)):
                        return int(item)
                    if isinstance(item, str) and item.strip().isdigit():
                        return int(item.strip())
        return None

    @classmethod
    def _extract_rows(cls, data):
        """Turn the tbody virtual-DOM into a list of holding dicts."""
        tbody = cls._find_node_by_id(data, "tthHoldingsTbody")
        rows = []
        if tbody is None:
            return rows
        for tr in tbody.get("c", []):
            tds = tr.get("c", [])
            if len(tds) < 5:
                continue
            try:
                symbol = tds[0]["a"]["tsraw"]
                description = tds[1]["a"]["tsraw"]
                weight_pct = float(tds[2]["a"]["tsraw"])  # e.g. 4.53 == 4.53%
                shares_held = tds[3]["a"]["tsraw"]
                market_value = tds[4]["a"]["tsraw"]
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "description": description,
                    "weight": weight_pct / 100.0,
                    "shares_held": shares_held,
                    "market_value": market_value,
                }
            )
        return rows


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


def _test_etf_holdings_client():
    tickers = ["NVDA", "SCHD", "SPY", "QQQ", "VOO", "SCHB"]

    with ETFHoldingsClient() as client:
        for ticker in tickers:
            print(f"\n{'=' * 60}")
            print(f"=== {ticker} ===")
            print("=" * 60)

            # Check ETF holdings info
            t0 = time.time()
            holdings = client.get_holdings(ticker, min_weight=0.01)
            elapsed_holdings = time.time() - t0

            if not holdings:
                print(f"[FAIL] {ticker}: no holdings found")
                continue

            # Top 5 holdings
            print(f"[OK] holdings: {len(holdings)} rows, {elapsed_holdings:.2f}s")
            for h in holdings[:5]:
                print(f"  {h['symbol']:<6} {h['description']:<35} {h['weight']:.2%}")

            # Check sort order
            weights = [h["weight"] for h in holdings]
            is_sorted_desc = all(weights[i] >= weights[i + 1] for i in range(len(weights) - 1))
            print(f"[{'OK' if is_sorted_desc else 'FAIL'}] sorted by weight descending: {is_sorted_desc}")

            # Descriptions helper
            t1 = time.time()
            descriptions = client.get_holding_descriptions(ticker, min_weight=0.01)
            elapsed_descriptions = time.time() - t1
            print(f"[OK] descriptions: {len(descriptions)} unique, {elapsed_descriptions:.2f}s")
            print(f"  sample: {descriptions[:5]}")


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
    #_test_etf_holdings_client()
    #_test_news_search_client()
    _test_ticker_news_client()