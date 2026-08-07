"""
Stock CLI
- displaying price charts and technical indicators

Usage:
    python cli.py thumbnail AAPL MSFT NVDA AMZN GOOGL META --range 6mo --interval 1d --cols 2
    python cli.py thumbnail AAPL MSFT --timezone America/New_York
    python cli.py chart AAPL --range 1y --interval 1d --indicators SMA:20 SMA:60 AVWAP KAMA:10
    python cli.py chart AAPL --type line --indicators MFI:14 WilliamsR:14 Fisher:10,3 StochRSI:14,2,3
    python cli.py chart BTC-USD --range 3mo --interval 4h --indicators SMA:20 AVWAP MFI:14 Fisher:10,3
    python cli.py chart AAPL --candle-color red_blue
    python cli.py chart AAPL --timezone America/New_York --indicators SMA:20
"""

import argparse
import math

from plotly.subplots import make_subplots

from imple.indicator.helper import parse_indicator
from core.plot import ChartType, CandleColor, plot_ticker_thumbnail, plot_ticker_chart, to_dark_layout


def cmd_thumbnail(args):
    """
    Display thumbnail charts for multiple tickers.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
    """

    tickers = args.tickers
    n = len(tickers)
    cols = min(n, args.cols)
    rows = math.ceil(n / cols)

    fig = make_subplots(rows=rows, cols=cols, subplot_titles=tickers)

    for i, ticker in enumerate(tickers):
        row, col = divmod(i, cols)

        thumb = plot_ticker_thumbnail(ticker=ticker, date_range=args.range, time_interval=args.interval, timezone=args.timezone, dark_layout=False)

        if thumb is None:
            continue

        for trace in thumb.data:
            fig.add_trace(trace, row=row + 1, col=col + 1)

    to_dark_layout(fig, title="Thumbnails")
    fig.update_layout(autosize=True)
    fig.show(config={"responsive": True})


def cmd_chart(args):
    """
    Display price chart with optional technical indicators.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
    """
    specs = (args.indicators or [])

    indicators = []
    for spec in specs:
        try:
            indicators.append(parse_indicator(spec))
        except ValueError as e:
            print(f"[Warning] Invalid indicator: {e}")

    fig = plot_ticker_chart(ticker=args.ticker, date_range=args.range, time_interval=args.interval, timezone=args.timezone, chart_type=ChartType(args.type), candle_color=CandleColor[args.candle_color.upper()], indicators=indicators)

    if fig is not None:
        fig.show(config={"responsive": True})
    else:
        print(f"[Warning] No data available for '{args.ticker}'")


def build_parser():
    """
    Build the command-line argument parser.

    Returns:
        argparse.ArgumentParser: Configured argument parser.
    """
    
    parser = argparse.ArgumentParser(description="Stock chart CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_thumb = sub.add_parser("thumbnail", help="Display multiple ticker thumbnails")
    p_thumb.add_argument("tickers", nargs="+", help="Ticker symbols (e.g. AAPL TSLA AGNC)")
    p_thumb.add_argument("--range", default="3mo", help="Date range (default: 3mo)")
    p_thumb.add_argument("--interval", default="1d", help="Time interval (default: 1d)")
    p_thumb.add_argument("--cols", type=int, default=3, help="Columns per row (default: 3)")
    p_thumb.add_argument("--timezone", default="Asia/Seoul", help="Timezone (default: Asia/Seoul)")
    p_thumb.set_defaults(func=cmd_thumbnail)

    p_chart = sub.add_parser("chart", help="Display a price chart with indicators")
    p_chart.add_argument("ticker", help="Ticker symbol (e.g. AAPL)")
    p_chart.add_argument("--range", default="1y", help="Date range (default: 1y)")
    p_chart.add_argument("--interval", default="1d", help="Time interval (default: 1d)")
    p_chart.add_argument("--indicators", nargs="*", default=[], help="Indicators (e.g. SMA:20 AVWAP)")
    p_chart.add_argument("--type", choices=["candle", "line"], default="candle", help="Chart type (default: candle)")
    p_chart.add_argument("--candle-color", choices=[c.name.lower() for c in CandleColor], default=CandleColor.GREEN_RED.name.lower(), help=f"Candlestick color scheme (default: {CandleColor.GREEN_RED.name.lower()})")
    p_chart.add_argument("--timezone", default="Asia/Seoul", help="Timezone (default: Asia/Seoul)")
    p_chart.set_defaults(func=cmd_chart)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)