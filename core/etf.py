"""
Get ETF holdings info from schwab.wallst.com's internal API.
- ETFHoldingsClient: Fast, browser-free ETF holdings scraper.
    reverse-engineered from a HAR capture of schwab.wallst.com's ETF holdings page

This code inspired from holdings_dl project
by PiperBatey, available at:
    https://github.com/PiperBatey/holdings_dl
Licensed under the MIT License.
"""

import base64
import json
import re
import requests


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


def _test_etf_holdings_client():
    import time
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


if __name__ == "__main__":
    _test_etf_holdings_client()