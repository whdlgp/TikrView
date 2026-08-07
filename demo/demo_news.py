import time
from core.news import NewsSearchClient, TickerNewsClient


def demo_news_search_client():
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


def demo_ticker_news_client():
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


def demo_news():
    print("----------------------")
    print("Demo: NewsSearchClient")
    print("----------------------")
    demo_news_search_client()
    print("----------------------")
    print("Demo: TickerNewsClient")
    print("----------------------")
    demo_ticker_news_client()


if __name__ == "__main__":
    demo_news()