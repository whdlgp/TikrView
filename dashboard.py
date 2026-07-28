"""
TikrView Dashboard
- Dash-based GUI dashboard that wraps the existing core/ modules
  (market_client, plot_ticker, stock_indicator, news) into a
  single-file interactive app.

Place this file at the project root, next to cli.py:

    TikrView/
    +-- core/
    |     +-- market_client.py
    |     +-- news.py
    |     +-- plot_ticker.py
    |     +-- stock_indicator.py
    +-- cli.py
    +-- dashboard.py   <- this file

Install (if needed):
    pip install dash dash-bootstrap-components plotly pandas yfinance feedparser requests

Run:
    python dashboard.py
Then open http://127.0.0.1:8050 in a browser.
"""

import traceback

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State, ALL, ctx, no_update

from core.market_client import get_ticker_data, get_ticker_info
from core.plot_ticker import plot_ticker_thumbnail, plot_ticker_chart, ChartType, CandleColor, to_dark_layout
from core.stock_indicator import parse_indicator, get_price_changes

try:
    from core.news import TickerNewsClient
    _NEWS_AVAILABLE = True
except Exception:
    _NEWS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

DEFAULT_TICKERS = "BND,SGOL,QQQM,VYMI,SPYM,SCHF,JEPI,SCHD,PFF,DWX,AGNC,441640.KS,UVXY,USDKRW=X"

THUMBNAIL_RANGE = "5y"
THUMBNAIL_INTERVAL = "1mo"

RANGE_OPTIONS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
INTERVAL_OPTIONS = ["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"]
CHANGE_LABELS = ["1D", "1W", "1M", "6M", "1Y"]

TIMEZONE_OPTIONS = [
    "Asia/Seoul", "Asia/Tokyo", "Asia/Shanghai", "Asia/Hong_Kong", "Asia/Singapore",
    "Europe/London", "Europe/Berlin", "Europe/Paris",
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "UTC",
]

INDICATOR_OPTIONS = [
    {"label": "SMA 5", "value": "SMA:5"},
    {"label": "SMA 10", "value": "SMA:10"},
    {"label": "SMA 20", "value": "SMA:20"},
    {"label": "SMA 50", "value": "SMA:50"},
    {"label": "SMA 60", "value": "SMA:60"},
    {"label": "SMA 120", "value": "SMA:120"},
    {"label": "SMA 200", "value": "SMA:200"},

    {"label": "VWAP", "value": "VWAP"},

    {"label": "KAMA 10", "value": "KAMA:10"},

    {"label": "Williams %R (14)", "value": "WilliamsR:14"},
    {"label": "MFI (14)", "value": "MFI:14"},
    {"label": "StochRSI (14,3,3)", "value": "StochRSI:14,3,3"},
    {"label": "Fisher (10)", "value": "Fisher:10"},
]
DEFAULT_INDICATORS = ["SMA:20", "SMA:60", "VWAP"]

THEME_OPTIONS = [{"label": "Dark", "value": "dark"}, {"label": "Light", "value": "light"}]

# Theme palettes. `sparkline` is the single uniform color used for every
# thumbnail chart (no more red/green coloring by change).
THEMES = {
    "dark": {
        "bg": "#101010",
        "panel": "#161616",
        "card": "#1e1e1e",
        "border": "#2f2f2f",
        "text": "#e0e0e0",
        "muted": "#9e9e9e",
        "muted2": "#666666",
        "accent": "#26a69a",
        "down": "#ef5350",
        "sparkline": "#7ec8e3",
        "active_bg": "#20302c",
        "dbc_theme": dbc.themes.DARKLY,
    },
    "light": {
        "bg": "#f4f5f7",
        "panel": "#ffffff",
        "card": "#ffffff",
        "border": "#dfe1e5",
        "text": "#1a1a1a",
        "muted": "#666666",
        "muted2": "#8a8a8a",
        "accent": "#0f9d84",
        "down": "#d32f2f",
        "sparkline": "#3d7bbf",
        "active_bg": "#e3f2f0",
        "dbc_theme": dbc.themes.FLATLY,
    },
}

DROPDOWN_STYLE = {"color": "#000", "fontSize": "13px", "minWidth": "150px"}


def theme_colors(theme):
    return THEMES.get(theme, THEMES["dark"])


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_num(value, digits=2):
    if value is None:
        return "N/A"
    try:
        if abs(value) >= 1e12:
            return f"{value / 1e12:.{digits}f}T"
        if abs(value) >= 1e9:
            return f"{value / 1e9:.{digits}f}B"
        if abs(value) >= 1e6:
            return f"{value / 1e6:.{digits}f}M"
        return f"{value:,.{digits}f}"
    except Exception:
        return "N/A"


def _fmt_price(value, currency=""):
    if value is None:
        return "N/A"
    try:
        return f"{value:,.2f} {currency}".strip()
    except Exception:
        return "N/A"


def _fmt_pct(value):
    if value is None:
        return "N/A"
    try:
        return f"{value:+.2f}%"
    except Exception:
        return "N/A"


def parse_ticker_list(raw_text):
    if not raw_text:
        return []
    parts = [p.strip().upper() for p in raw_text.replace("\n", ",").split(",")]
    seen, result = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            result.append(p)
    return result


# ---------------------------------------------------------------------------
# Thumbnail sidebar
# ---------------------------------------------------------------------------

def build_thumbnail_figure(ticker, theme):
    """Small sparkline for a thumbnail button, built from the existing
    plot_ticker_thumbnail() helper (core/plot_ticker.py) rather than
    duplicating chart-construction logic here. Uniform 5y/1mo view,
    single color (no red/green by change)."""
    colors = theme_colors(theme)

    fig = plot_ticker_thumbnail(
        ticker,
        date_range=THUMBNAIL_RANGE,
        time_interval=THUMBNAIL_INTERVAL,
        dark_layout=(theme == "dark"),
    )
    if fig is None:
        fig = go.Figure()

    if fig.data:
        fig.data[0].line.color = colors["sparkline"]
        fig.data[0].hoverinfo = "skip"

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def build_thumbnail_meta(ticker):
    """Return (last_price, currency, pct_change_1d) for the thumbnail label."""
    try:
        info = get_ticker_info(ticker)
    except Exception:
        info = {}
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    currency = info.get("currency") or ""
    prev_close = info.get("previousClose")
    pct = None
    if price is not None and prev_close:
        try:
            pct = (price - prev_close) / prev_close * 100
        except Exception:
            pct = None
    return price, currency, pct


def thumbnail_style(active, theme):
    colors = theme_colors(theme)
    return {
        "backgroundColor": colors["active_bg"] if active else colors["card"],
        "border": f"1px solid {colors['accent']}" if active else f"1px solid {colors['border']}",
        "borderRadius": "8px",
        "padding": "8px 10px",
        "marginBottom": "8px",
        "cursor": "pointer",
        "width": "100%",
        "boxSizing": "border-box",
    }


def build_thumbnail(ticker, active, theme):
    colors = theme_colors(theme)
    fig = build_thumbnail_figure(ticker, theme)
    price, currency, pct = build_thumbnail_meta(ticker)

    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        ticker,
                        style={"fontWeight": "700", "fontSize": "13px", "overflow": "hidden",
                               "textOverflow": "ellipsis", "whiteSpace": "nowrap", "maxWidth": "108px",
                               "display": "inline-block", "verticalAlign": "bottom", "color": colors["text"]},
                    ),
                ],
                style={"marginBottom": "2px"},
            ),
            dcc.Graph(
                figure=fig,
                config={"staticPlot": True, "displayModeBar": False},
                style={"height": "36px", "width": "100%"},
            ),
            html.Div(
                _fmt_price(price, currency),
                style={"fontSize": "11px", "color": colors["muted"], "marginTop": "2px", "overflow": "hidden",
                       "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
            ),
        ],
        id={"type": "thumb", "index": ticker},
        n_clicks=0,
        style=thumbnail_style(active, theme),
    )


# ---------------------------------------------------------------------------
# Info card / chart builders
# ---------------------------------------------------------------------------

def build_summary_card(ticker, theme):
    colors = theme_colors(theme)

    try:
        info = get_ticker_info(ticker)
    except Exception:
        info = {}

    try:
        df = get_ticker_data(ticker, date_range="1y", time_interval="1d")
        changes = get_price_changes(df)
    except Exception:
        changes = [None] * 5

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    currency = info.get("currency") or ""
    name = info.get("longName") or info.get("shortName") or ticker
    exchange = info.get("fullExchangeName") or info.get("exchange") or "N/A"
    market_state = info.get("marketState") or "N/A"
    quote_type = info.get("quoteType") or ""

    def change_color(v):
        return colors["muted"] if v is None else (colors["accent"] if v >= 0 else colors["down"])

    change_badges = [
        html.Div(
            [
                html.Div(label, style={"fontSize": "11px", "color": colors["muted"]}),
                html.Div(_fmt_pct(val), style={"fontSize": "14px", "fontWeight": "600", "color": change_color(val)}),
            ],
            style={"textAlign": "center", "padding": "4px 10px"},
        )
        for label, val in zip(CHANGE_LABELS, changes)
    ]

    basic_section = [
        ("Exchange", exchange),
        ("Currency", currency),
        ("Country", info.get("country") or "N/A"),
    ]

    quote_type = info.get("quoteType", "")

    if quote_type == "ETF":
        info_section = [
            ("Fund Family", info.get("fundFamily") or "N/A"),
            ("Category", info.get("category") or "N/A"),
            ("Net Assets", _fmt_num(info.get("netAssets"))),
            ("Expense Ratio", _fmt_pct(info.get("netExpenseRatio")) if info.get("netExpenseRatio") is not None else "N/A"),
            ("Dividend Yield", _fmt_pct(info.get("dividendYield")) if info.get("dividendYield") is not None else "N/A"),
            ("3Y Avg Return", _fmt_pct(info.get("threeYearAverageReturn")) if info.get("threeYearAverageReturn") is not None else "N/A"),
            ("5Y Avg Return", _fmt_pct(info.get("fiveYearAverageReturn")) if info.get("fiveYearAverageReturn") is not None else "N/A"),
            ("YTD Return", _fmt_pct(info.get("ytdReturn")) if info.get("ytdReturn") is not None else "N/A"),
        ]
    else:
        info_section = [
            ("Sector", info.get("sector") or "N/A"),
            ("Industry", info.get("industry") or "N/A"),
            ("Market Cap", _fmt_num(info.get("marketCap"))),
            ("P/E (TTM)", _fmt_num(info.get("trailingPE"))),
            ("Forward P/E", _fmt_num(info.get("forwardPE"))),
            ("EPS", _fmt_num(info.get("trailingEps"))),
            ("Beta", _fmt_num(info.get("beta"))),
            ("Employees", _fmt_num(info.get("fullTimeEmployees"), digits=0)),
            ("Dividend Yield", _fmt_pct(info.get("dividendYield")) if info.get("dividendYield") is not None else "N/A"),
        ]

    def metric_grid(title, pairs):
        return html.Div(
            [
                html.Div(title, style={"fontSize": "10.5px", "color": colors["muted2"], "textTransform": "uppercase",
                                        "letterSpacing": "0.05em", "marginTop": "10px", "marginBottom": "4px"}),
                html.Div(
                    [
                        html.Div(
                            [html.Span(k, style={"color": colors["muted"], "fontSize": "11.5px"}),
                             html.Span(v, style={"fontSize": "12.5px", "float": "right", "color": colors["text"]})],
                            style={"padding": "2px 0", "display": "flex", "justifyContent": "space-between"},
                        )
                        for k, v in pairs
                    ]
                ),
            ]
        )

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(ticker, style={"fontSize": "20px", "fontWeight": "700", "color": colors["text"]}),
                html.Div(name, style={"fontSize": "12.5px", "color": colors["muted"], "marginBottom": "2px"}),
                html.Div(f"{exchange} · {quote_type} · {market_state}", style={"fontSize": "10.5px", "color": colors["muted2"]}),
                html.Div(
                    [
                        html.Span(_fmt_price(price, currency), style={"fontSize": "24px", "fontWeight": "700", "marginRight": "8px", "color": colors["text"]}),
                        html.Span(currency, style={"fontSize": "12px", "color": colors["muted"]}),
                    ],
                    style={"marginTop": "8px"},
                ),
                html.Hr(style={"borderColor": colors["border"], "margin": "8px 0"}),
                html.Div(change_badges, style={"display": "flex", "flexWrap": "wrap"}),
                metric_grid("Basic", basic_section),
                metric_grid("Information", info_section),
            ]
        ),
        style={"backgroundColor": colors["card"], "border": f"1px solid {colors['border']}", "height": "100%"},
    )


def build_chart_figure(ticker, date_range, interval, timezone, chart_type, candle_color, indicator_values, theme):
    indicators = []
    warnings = []
    for spec in (indicator_values or []):
        try:
            indicators.append(parse_indicator(spec))
        except ValueError as e:
            warnings.append(str(e))

    try:
        fig = plot_ticker_chart(
            ticker=ticker,
            date_range=date_range,
            time_interval=interval,
            timezone=timezone,
            chart_type=ChartType(chart_type),
            candle_color=CandleColor[candle_color.upper()],
            indicators=indicators,
            dark_layout=(theme == "dark"),
        )
    except Exception:
        traceback.print_exc()
        fig = None

    if fig is None:
        fig = go.Figure()
        if theme == "dark":
            to_dark_layout(fig, title=f"No data for '{ticker}'")
        else:
            fig.update_layout(title=f"No data for '{ticker}'")

    return fig, warnings


def build_news_content(ticker, theme):
    colors = theme_colors(theme)
    if not _NEWS_AVAILABLE:
        return html.Div("News module unavailable.", style={"color": colors["muted"], "fontSize": "13px"})
    try:
        with TickerNewsClient() as client:
            items = client.get_news_for_ticker(ticker, days=5)
    except Exception as e:
        return html.Div(f"Failed to load news: {e}", style={"color": colors["down"], "fontSize": "13px"})

    if not items:
        return html.Div("No recent news found.", style={"color": colors["muted"], "fontSize": "13px"})

    rows = []
    for item in items[:15]:
        rows.append(
            html.Div(
                [
                    html.A(item["title"], href=item["link"], target="_blank",
                           style={"color": colors["text"], "fontSize": "13.5px", "textDecoration": "none"}),
                    html.Div(f"{item['published']:%Y-%m-%d %H:%M}  ·  {item.get('query', '')}",
                             style={"fontSize": "11px", "color": colors["muted"], "marginTop": "1px"}),
                ],
                style={"padding": "6px 0", "borderBottom": f"1px solid {colors['border']}"},
            )
        )
    return html.Div(rows)


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], suppress_callback_exceptions=True)
app.title = "TikrView"

_label_style = {"fontSize": "11px", "color": "#9e9e9e", "marginBottom": "2px", "display": "block"}

top_bar = html.Div(
    [
        html.Div(
            [
                html.H5("TikrView", style={"fontWeight": "700", "margin": 0}),
                html.Div(
                    "stock dashboard",
                    style={"fontSize": "11px", "color": "#9e9e9e"},
                ),
            ],
            style={"marginBottom": "12px"},
        ),

        html.Div(
            [
                html.Div(
                    [
                        html.Label("Tickers (comma separated)", style=_label_style),
                        dcc.Textarea(
                            id="ticker-input",
                            value=DEFAULT_TICKERS,
                            style={
                                "width": "100%",
                                "minWidth": 0,
                                "height": "38px",
                                "backgroundColor": "#101010",
                                "color": "#e0e0e0",
                                "border": "1px solid #333",
                                "resize": "none",
                            },
                        ),
                    ],
                    style={
                        "flex": 1,
                        "minWidth": 0,
                        "marginRight": "10px",
                    },
                ),

                dbc.Button(
                    "Update",
                    id="apply-btn",
                    color="success",
                    size="sm",
                    n_clicks=0,
                    style={
                        "height": "38px",
                        "marginTop": "16px",
                        "marginRight": "10px",
                    },
                ),

                html.Div(
                    [
                        html.Label("Theme", style=_label_style),
                        dcc.Dropdown(
                            THEME_OPTIONS,
                            "dark",
                            id="theme-input",
                            clearable=False,
                            style={
                                **DROPDOWN_STYLE,
                                "width": "110px",
                            },
                        ),
                    ],
                ),
            ],
            style={
                "display": "flex",
                "alignItems": "flex-end",
                "marginBottom": "14px",
            },
        ),

        html.Div(
            [
                html.Div(
                    [
                        html.Label("Range", style=_label_style),
                        dcc.Dropdown(
                            RANGE_OPTIONS,
                            "1y",
                            id="range-input",
                            clearable=False,
                            style={**DROPDOWN_STYLE, "width": "90px"},
                        ),
                    ],
                    style={"marginRight": "10px"},
                ),

                html.Div(
                    [
                        html.Label("Interval", style=_label_style),
                        dcc.Dropdown(
                            INTERVAL_OPTIONS,
                            "1d",
                            id="interval-input",
                            clearable=False,
                            style={**DROPDOWN_STYLE, "width": "90px"},
                        ),
                    ],
                    style={"marginRight": "10px"},
                ),

                html.Div(
                    [
                        html.Label("Chart", style=_label_style),
                        dcc.Dropdown(
                            ["candle", "line"],
                            "candle",
                            id="chart-type-input",
                            clearable=False,
                            style={**DROPDOWN_STYLE, "width": "100px"},
                        ),
                    ],
                    style={"marginRight": "10px"},
                ),

                html.Div(
                    [
                        html.Label("Candle", style=_label_style),
                        dcc.Dropdown(
                            [c.name.lower() for c in CandleColor],
                            CandleColor.GREEN_RED.name.lower(),
                            id="candle-color-input",
                            clearable=False,
                            style={**DROPDOWN_STYLE, "width": "130px"},
                        ),
                    ],
                    style={"marginRight": "10px"},
                ),

                html.Div(
                    [
                        html.Label("Timezone", style=_label_style),
                        dcc.Dropdown(
                            TIMEZONE_OPTIONS,
                            "Asia/Seoul",
                            id="timezone-input",
                            clearable=False,
                            style={**DROPDOWN_STYLE, "width": "160px"},
                        ),
                    ],
                    style={"marginRight": "10px"},
                ),

                html.Div(
                    [
                        html.Label("Indicators", style=_label_style),
                        dcc.Dropdown(
                            INDICATOR_OPTIONS,
                            DEFAULT_INDICATORS,
                            id="indicator-input",
                            multi=True,
                            style={**DROPDOWN_STYLE, "width": "240px"},
                        ),
                    ],
                ),
            ],
            style={
                "display": "flex",
                "flexWrap": "wrap",
                "alignItems": "flex-end",
            },
        ),
    ],
    id="top-bar",
    style={
        "padding": "14px 20px",
        "borderBottom": "1px solid #2a2a2a",
    },
)

thumbnail_panel = html.Div(
    dcc.Loading(html.Div(id="thumbnail-list", children=[]), type="circle", color=THEMES["dark"]["accent"]),
    id="thumbnail-panel",
    style={"width": "170px", "flexShrink": 0, "padding": "12px", "overflowY": "auto"},
)

main_content = html.Div(
    dcc.Loading(html.Div(id="main-panel"), type="circle", color=THEMES["dark"]["accent"]),
    id="main-content",
    style={"flexGrow": 1, "padding": "16px 24px", "overflowY": "auto"},
)

body_row = html.Div(
    [thumbnail_panel, main_content],
    id="body-row",
    style={"display": "flex", "height": "calc(100vh - 92px)"},
)

app.layout = html.Div(
    [
        dcc.Store(id="tickers-store", data=parse_ticker_list(DEFAULT_TICKERS)),
        dcc.Store(id="active-ticker-store", data=(parse_ticker_list(DEFAULT_TICKERS) or [None])[0]),
        dcc.Store(id="theme-store", data="dark"),
        top_bar,
        body_row,
    ],
    id="app-root",
    style={"backgroundColor": "#101010", "minHeight": "100vh", "color": "#e0e0e0"},
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(Output("theme-store", "data"), Input("theme-input", "value"))
def set_theme(theme):
    return theme or "dark"


@app.callback(
    Output("app-root", "style"),
    Output("top-bar", "style"),
    Output("thumbnail-panel", "style"),
    Input("theme-store", "data"),
)
def apply_theme_chrome(theme):
    colors = theme_colors(theme)

    root_style = {
        "backgroundColor": colors["bg"],
        "minHeight": "100vh",
        "color": colors["text"],
    }

    top_bar_style = {
        "display": "block",
        "padding": "14px 20px",
        "borderBottom": f"1px solid {colors['border']}",
        "backgroundColor": colors["panel"],
    }

    thumb_panel_style = {
        "width": "170px",
        "flexShrink": 0,
        "padding": "12px",
        "overflowY": "auto",
        "backgroundColor": colors["bg"],
        "borderRight": f"1px solid {colors['border']}",
    }

    return root_style, top_bar_style, thumb_panel_style


@app.callback(
    Output("tickers-store", "data"),
    Input("apply-btn", "n_clicks"),
    State("ticker-input", "value"),
    prevent_initial_call=True,
)
def update_ticker_list(n_clicks, raw_tickers):
    return parse_ticker_list(raw_tickers)


@app.callback(
    Output("thumbnail-list", "children"),
    Input("tickers-store", "data"),
    Input("theme-store", "data"),
    State("active-ticker-store", "data"),
)
def render_thumbnails(tickers, theme, active_ticker):
    # Rebuilt when the ticker list or theme changes (not on every click,
    # which would recreate each thumbnail Div and reset its n_clicks).
    tickers = tickers or []
    return [build_thumbnail(t, active=(t == active_ticker), theme=theme) for t in tickers]


@app.callback(
    Output({"type": "thumb", "index": ALL}, "style"),
    Input("active-ticker-store", "data"),
    State({"type": "thumb", "index": ALL}, "id"),
    State("theme-store", "data"),
)
def highlight_active_thumbnail(active_ticker, thumb_ids, theme):
    # Cheap style-only update so the selected thumbnail is highlighted
    # without recreating (and thereby resetting) the clickable components.
    return [thumbnail_style(comp_id["index"] == active_ticker, theme) for comp_id in thumb_ids]


@app.callback(
    Output("active-ticker-store", "data"),
    Input({"type": "thumb", "index": ALL}, "n_clicks"),
    Input("tickers-store", "data"),
    State("active-ticker-store", "data"),
    prevent_initial_call=False,
)
def set_active_ticker(n_clicks_list, tickers, current_active):
    tickers = tickers or []
    triggered = ctx.triggered_id

    if isinstance(triggered, dict) and triggered.get("type") == "thumb":
        clicked_ticker = triggered["index"]
        for comp_id, n in zip(ctx.inputs_list[0], n_clicks_list):
            if comp_id["id"]["index"] == clicked_ticker and not n:
                return no_update
        return clicked_ticker

    if current_active in tickers:
        return current_active
    return tickers[0] if tickers else None


@app.callback(
    Output("main-panel", "children"),
    Input("active-ticker-store", "data"),
    Input("range-input", "value"),
    Input("interval-input", "value"),
    Input("timezone-input", "value"),
    Input("chart-type-input", "value"),
    Input("candle-color-input", "value"),
    Input("indicator-input", "value"),
    Input("theme-store", "data"),
)
def render_main_panel(active_ticker, date_range, interval, timezone, chart_type, candle_color, indicator_values, theme):
    colors = theme_colors(theme)

    if not active_ticker:
        return html.Div(
            "Enter tickers at the top and click 'Update tickers'.",
            style={"color": colors["muted"], "padding": "60px", "textAlign": "center"},
        )

    fig, warnings = build_chart_figure(active_ticker, date_range, interval, timezone, chart_type, candle_color, indicator_values, theme)

    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(build_summary_card(active_ticker, theme), width=12, lg=3, style={"marginBottom": "12px"}),
                    dbc.Col(
                        [
                            dcc.Graph(figure=fig, style={"height": "72vh"}, config={"responsive": True}),
                            html.Div(" / ".join(warnings), style={"color": "#f0ad4e", "fontSize": "12px", "marginTop": "4px"}) if warnings else None,
                        ],
                        width=12, lg=9,
                    ),
                ]
            ),
            html.Hr(style={"borderColor": colors["border"], "margin": "18px 0 10px"}),
            html.Div(
                [
                    dbc.Button("📰 Load news", id={"type": "news-btn", "index": active_ticker}, size="sm",
                               color="secondary", outline=True, n_clicks=0),
                    dcc.Loading(html.Div(id={"type": "news-content", "index": active_ticker}, style={"marginTop": "10px"})),
                ]
            ),
        ],
        style={"padding": "4px"},
    )


@app.callback(
    Output({"type": "news-content", "index": ALL}, "children"),
    Input({"type": "news-btn", "index": ALL}, "n_clicks"),
    State("theme-store", "data"),
    prevent_initial_call=True,
)
def load_news(n_clicks_list, theme):
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict):
        return [no_update] * len(n_clicks_list)

    ticker = triggered["index"]
    output_ids = [o["id"]["index"] for o in ctx.outputs_list]
    result = [no_update] * len(output_ids)
    for i, idx in enumerate(output_ids):
        if idx == ticker:
            result[i] = build_news_content(ticker, theme)
    return result


if __name__ == "__main__":
    app.run(debug=True, port=8050)