import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from enum import Enum

from .market import get_ticker_data, get_ticker_info
from .indicator import Panel, Indicator
from .forecaster import Forecaster


def to_dark_layout(fig, title=None):
    """
    Apply a dark theme to a Plotly figure.

    Args:
        fig (plotly.graph_objects.Figure): Plotly figure to update.
        title (str | None): Figure title.
    """

    bg_color = "#1e1e1e"
    grid_color = "#333333"
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        title=title,
        margin=dict(l=50, r=30, t=60, b=30),
    )
    fig.update_xaxes(gridcolor=grid_color)
    fig.update_yaxes(gridcolor=grid_color)


def plot_ticker_thumbnail(ticker: str, date_range: str, time_interval: str, timezone: str="Asia/Seoul", dark_layout: bool=True) -> go.Figure | None:
    """
    Create a thumbnail price chart for a ticker.

    Args:
        ticker (str): stock ticker symbol (e.g. "AGNC", "AAPL").
        date_range (str): how much history to fetch.
            Valid values: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        time_interval (str): gap between each data point.
            Valid values: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        timezone (str): timezone to convert the index to (default: "Asia/Seoul")
        dark_layout (bool): Whether to apply the dark theme.

    Returns:
        plotly.graph_objects.Figure | None: Thumbnail chart, or None if no data is available.
    """
    
    df = get_ticker_data(ticker, date_range=date_range, time_interval=time_interval, timezone = timezone)

    if df.empty:
        return

    accent_color = "#60a5fa" if dark_layout else "#2563eb"
    close = df["Close"]
    margin = (close.max() - close.min()) * 0.1

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=close,
            mode="lines",
            line=dict(width=1.5, color=accent_color),
            fill="tozeroy",
            fillgradient=dict(
                type="vertical",
                colorscale=[[0, "rgba(0,0,0,0)"], [1, accent_color]],
            ),
            showlegend=False,
        )
    )

    fig.update_yaxes(range=[close.min() - margin, close.max() + margin])

    if dark_layout:
        to_dark_layout(fig)

    return fig


class ChartType(Enum):
    """Type of price chart."""
    CANDLE = "candle"    # Candlestick chart
    LINE = "line"        # Line chart


class CandleColor(Enum):
    """Type of candle chart color"""
    # Green up
    GREEN_RED = ("#26a69a", "#ef5350")
    GREEN_ORANGE = ("#26a69a", "#fb8c00")
    GREEN_GRAY = ("#26a69a", "#757575")

    # Red up
    RED_BLUE = ("#e53935", "#1e88e5")
    RED_GREEN = ("#e53935", "#26a69a")
    RED_GRAY = ("#e53935", "#757575")

    # Monochrome
    BLACK_WHITE = ("#000000", "#ffffff")
    BLACK_GRAY = ("#000000", "#757575")


def plot_ticker_chart(
    ticker: str, date_range: str, time_interval: str, timezone: str="Asia/Seoul",
    chart_type: ChartType=ChartType.CANDLE, candle_color: CandleColor = CandleColor.GREEN_RED,
    indicators: list[Indicator] | None=None, forecasters: list[Forecaster] | None=None,
    dark_layout: bool=True
) -> go.Figure | None:
    """
    Create a price chart for a ticker with optional technical indicators.

    Args:
        ticker (str): Stock ticker symbol (e.g. "AGNC", "AAPL").
        date_range (str): How much history to fetch.
            Valid values: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        time_interval (str): Gap between each data point.
            Valid values: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        timezone (str): Timezone to convert the index to (default: "Asia/Seoul").
        chart_type (ChartType): Price chart type.
        candle_color (CandleColor): Candlestick color scheme.
        indicators (list[Indicator] | None): Technical indicators to display.
        dark_layout (bool): Whether to apply the dark theme.

    Returns:
        plotly.graph_objects.Figure | None: Price chart, or None if no data is available.
    """

    df = get_ticker_data(ticker, date_range=date_range, time_interval=time_interval, timezone=timezone)

    if df.empty:
        return None

    indicators = indicators or []

    main_indicators = [ind for ind in indicators if ind.panel == Panel.MAIN]
    sub_indicators = [ind for ind in indicators if ind.panel == Panel.SUB]

    n_sub = len(sub_indicators)
    rows = 2 + n_sub  # main + volume + sub
    volume_height = 0.15
    main_height = 0.85 - (0.25 if n_sub else 0)
    sub_height = 0.25 / n_sub if n_sub else 0
    row_heights = [main_height, volume_height] + [sub_height] * n_sub

    info = get_ticker_info(ticker)
    full_name = info.get("longName") or info.get("shortName")

    if full_name:
        main_title = (
            f"<b>{ticker}</b><br>"
            f"<span style='font-size:16px'>({full_name})</span>"
        )
    else:
        main_title = f"<b>{ticker}</b>"

    sub_titles = [main_title, "Volume"] + [ind.display_name for ind in sub_indicators]

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=row_heights, vertical_spacing=0.04, subplot_titles=sub_titles)

    up_color, down_color = candle_color.value

    if chart_type is ChartType.CANDLE:
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                increasing_line_color=up_color,
                decreasing_line_color=down_color,
                name=ticker,
            ),
            row=1, col=1,
        )

    elif chart_type is ChartType.LINE:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Close"],
                mode="lines",
                line=dict(color=up_color, width=1.8),
                name=ticker,
            ),
            row=1, col=1,
        )

    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    palette = px.colors.qualitative.Plotly
    for i, forecaster in enumerate(forecasters or []):
        color = palette[i % len(palette)]
        result = forecaster.calc(df)

        fig.add_trace(
            go.Scatter(
                x=list(result.index) + list(result.index[::-1]),
                y=list(result["upper"]) + list(result["lower"][::-1]),
                fill="toself",
                fillcolor=color,
                opacity=0.15,
                line=dict(color="rgba(0,0,0,0)"),
                hoverinfo="skip",
                showlegend=False,
            ),
            row=1, col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=result.index,
                y=result["median"],
                mode="lines",
                name=f"{forecaster.display_name}",
                line=dict(color=color, width=1.3, dash="dash"),
            ),
            row=1, col=1,
        )

    for ind in main_indicators:
        values = ind.calc(df)

        for name, series in values.items():
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=series,
                    mode="lines",
                    name=name,
                    line=dict(width=1.3),
                ),
                row=1, col=1,
            )

    volume_colors = [
        up_color if c >= o else down_color
        for o, c in zip(df["Open"], df["Close"])
    ]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["Volume"],
            marker_color=volume_colors,
            name="Volume",
            showlegend=False,
        ),
        row=2, col=1,
    )

    for i, ind in enumerate(sub_indicators):
        panel_row = 3 + i

        values = ind.calc(df)

        for name, series in values.items():
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=series,
                    mode="lines",
                    name=name,
                    line=dict(width=1.3),
                ),
                row=panel_row, col=1,
            )

        for ref in ind.reference_lines:
            fig.add_hline(y=ref, line_dash="dot", line_color="gray", row=panel_row, col=1)

    if dark_layout:
        to_dark_layout(fig)
    
    fig.update_layout(autosize=True, xaxis_rangeslider_visible=False, margin=dict(t=70))

    return fig
