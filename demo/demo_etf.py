from core.etf import ETFHoldingsClient


def demo_etf():
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
    demo_etf()
