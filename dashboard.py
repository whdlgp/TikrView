"""
TikrView Dashboard
- PySide6 GUI wrapping the core/ modules (market_client, plot_ticker, stock_indicator, news).
- Simple, synchronous, no threading.

Run:
    python dashboard.py
"""

import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter, QScrollArea
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QComboBox, QRadioButton, QButtonGroup
from PySide6.QtWidgets import QGroupBox, QFrame, QTabWidget, QTextBrowser, QSizePolicy, QMenu

from PySide6.QtWebEngineWidgets import QWebEngineView

from qt_material import apply_stylesheet, list_themes

from core.market_client import get_ticker_data, get_ticker_info
from core.plot_ticker import ChartType, CandleColor, plot_ticker_chart, plot_ticker_thumbnail
from core.stock_indicator import get_price_changes, parse_indicator
from core.news import TickerNewsClient


DEFAULT_TICKERS = [
    "BND",
    "SGOL",
    "QQQM",
    "VYMI",
    "SPYM",
    "SCHF",
    "JEPI",
    "SCHD",
    "PFF",
    "DWX",
    "AGNC",
    "441640.KS",
    "UVXY",
    "USDKRW=X",
]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_num(value, digits=2):
    """Format a number with K/M/B/T suffixes."""
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


def _fmt_pct(value):
    """Format a percentage value."""
    if value is None:
        return "N/A"
    try:
        return f"{value:+.2f}%"
    except Exception:
        return "N/A"


# ---------------------------------------------------------------------------
# Indicator picker widget
# ---------------------------------------------------------------------------

INDICATOR_OPTIONS = [
    ("SMA 5", "SMA:5"),
    ("SMA 10", "SMA:10"),
    ("SMA 20", "SMA:20"),
    ("SMA 50", "SMA:50"),
    ("SMA 60", "SMA:60"),
    ("SMA 120", "SMA:120"),
    ("SMA 200", "SMA:200"),
    ("VWAP", "VWAP"),
    ("KAMA 10", "KAMA:10"),
    ("Williams %R (14)", "WilliamsR:14"),
    ("MFI (14)", "MFI:14"),
    ("StochRSI (14,3,3)", "StochRSI:14,3,3"),
    ("Fisher (10)", "Fisher:10"),
]

DEFAULT_INDICATORS = ["SMA:20", "SMA:60", "VWAP"]


class IndicatorPicker(QWidget):
    """Button that opens a menu with checkable indicator options."""

    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._button = QPushButton("Indicators...")
        self._button.clicked.connect(self._show_menu)

        self._menu = QMenu(self)
        self._actions = {}

        for label, value in INDICATOR_OPTIONS:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(value)
            action.toggled.connect(self._on_toggled)
            self._menu.addAction(action)
            self._actions[value] = action

        layout.addWidget(self._button)

    def _show_menu(self):
        self._menu.exec(
            self._button.mapToGlobal(self._button.rect().bottomLeft())
        )

    def _on_toggled(self):
        self._update_label()
        self.selection_changed.emit()

    def _update_label(self):
        selected = self.selected_values()
        if selected:
            self._button.setText(", ".join(selected))
        else:
            self._button.setText("Indicators...")

    def selected_values(self):
        """Return list of checked indicator spec strings."""
        return [a.data() for a in self._actions.values() if a.isChecked()]

    def set_selected(self, values):
        """Set checked indicators by value list."""
        for v, a in self._actions.items():
            a.setChecked(v in values)
        self._update_label()


# ---------------------------------------------------------------------------
# Thumbnail card widget
# ---------------------------------------------------------------------------

class ThumbnailCard(QFrame):
    """Clickable thumbnail card showing ticker, sparkline chart, price, and daily change."""

    clicked = Signal(str)

    def __init__(self, ticker, parent=None):
        super().__init__(parent)
        self.ticker = ticker
        self._active = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        # Ticker symbol
        self.ticker_label = QLabel(ticker)
        font = self.ticker_label.font()
        font.setBold(True)
        font.setPointSize(12)
        self.ticker_label.setFont(font)

        # Sparkline chart
        self.chart_view = QWebEngineView()
        self.chart_view.setFixedHeight(115)
        self.chart_view.page().setBackgroundColor(Qt.transparent)

        # Price + change row
        row = QHBoxLayout()
        row.setSpacing(8)

        self.price_label = QLabel("-")
        self.price_label.setStyleSheet("font-size: 11px;")

        row.addWidget(self.price_label)
        row.addStretch()

        layout.addWidget(self.ticker_label)
        layout.addWidget(self.chart_view)
        layout.addLayout(row)

        self._update_style()

    def mousePressEvent(self, event):
        self.clicked.emit(self.ticker)
        super().mousePressEvent(event)

    def set_active(self, active):
        self._active = active
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet(
                "ThumbnailCard { border: 2px solid #26a69a; border-radius: 6px; }"
            )
        else:
            self.setStyleSheet(
                "ThumbnailCard { border: 1px solid #444; border-radius: 6px; }"
            )


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class StockApp(QMainWindow):

    def __init__(self):
        super().__init__()

        self.current_symbol = None
        self.cards = {}
        self._dark_theme = True  # default theme is dark_teal.xml
        self._timezone = "Asia/Seoul"  # default timezone
        self._changes_data = []  # [(label, value), ...] for price changes bar

        self.setWindowTitle("TikrView")
        self.resize(1650, 920)

        self.build_ui()

        self.apply_tickers(DEFAULT_TICKERS)

    def build_ui(self):

        #
        # ============================================================
        # Top Bar
        # ============================================================
        #

        self.ticker_edit = QLineEdit(",".join(DEFAULT_TICKERS))

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.on_apply_clicked)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list_themes())
        self.theme_combo.setCurrentText("dark_teal.xml")
        self.theme_combo.setMinimumWidth(140)
        self.theme_combo.currentTextChanged.connect(self.change_theme)

        self.range_combo = QComboBox()
        self.range_combo.addItems(["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"])
        self.range_combo.setCurrentText("1y")
        self.range_combo.setMinimumWidth(70)
        self.range_combo.currentIndexChanged.connect(self.update_chart)

        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"])
        self.interval_combo.setCurrentText("1d")
        self.interval_combo.setMinimumWidth(70)
        self.interval_combo.currentIndexChanged.connect(self.update_chart)

        self.chart_combo = QComboBox()
        self.chart_combo.addItems(["Candlestick", "Line"])
        self.chart_combo.setMinimumWidth(110)
        self.chart_combo.currentIndexChanged.connect(self.update_chart)

        self.color_combo = QComboBox()
        self.color_combo.addItems([color.name.title() for color in CandleColor])
        self.color_combo.setMinimumWidth(130)
        self.color_combo.currentIndexChanged.connect(self.update_chart)

        self.indicator_picker = IndicatorPicker()
        self.indicator_picker.set_selected(DEFAULT_INDICATORS)
        self.indicator_picker.selection_changed.connect(self.update_chart)

        top_widget = QWidget()
        top_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        top_layout = QVBoxLayout(top_widget)

        row1 = QHBoxLayout()

        row1.addWidget(QLabel("Tickers"))
        row1.addWidget(self.ticker_edit)

        row1.addWidget(self.apply_button)

        row1.addSpacing(20)

        row1.addWidget(QLabel("Theme"))
        row1.addWidget(self.theme_combo)

        row1.addSpacing(12)

        self.timezone_combo = QComboBox()
        self.timezone_combo.addItems([
            "Asia/Seoul",
            "Asia/Tokyo",
            "Asia/Shanghai",
            "Asia/Hong_Kong",
            "Asia/Singapore",
            "Asia/Kolkata",
            "Europe/London",
            "Europe/Berlin",
            "Europe/Paris",
            "America/New_York",
            "America/Chicago",
            "America/Los_Angeles",
            "America/Toronto",
            "America/Sao_Paulo",
            "Australia/Sydney",
            "Pacific/Auckland",
            "UTC",
        ])
        self.timezone_combo.setCurrentText("Asia/Seoul")
        self.timezone_combo.setMinimumWidth(140)
        self.timezone_combo.currentTextChanged.connect(self.change_timezone)

        row1.addWidget(QLabel("Timezone"))
        row1.addWidget(self.timezone_combo)

        row1.addStretch()

        top_layout.addLayout(row1)

        #
        # ============================================================
        # Thumbnail Panel
        # ============================================================
        #

        self.thumbnail_scroll = QScrollArea()
        self.thumbnail_scroll.setWidgetResizable(True)
        self.thumbnail_scroll.setMinimumWidth(280)

        self.thumbnail_widget = QWidget()

        self.thumbnail_layout = QVBoxLayout(self.thumbnail_widget)
        self.thumbnail_layout.setContentsMargins(8, 8, 8, 8)
        self.thumbnail_layout.setSpacing(8)
        self.thumbnail_layout.addStretch()

        self.thumbnail_scroll.setWidget(self.thumbnail_widget)

        #
        # ============================================================
        # Summary Panel
        # ============================================================
        #

        self.summary_group = QGroupBox("Summary")

        summary_layout = QVBoxLayout(self.summary_group)

        self.name_label = QLabel("-")
        font = self.name_label.font()
        font.setPointSize(18)
        font.setBold(True)
        self.name_label.setFont(font)

        self.price_label = QLabel("-")
        font = self.price_label.font()
        font.setPointSize(16)
        font.setBold(True)
        self.price_label.setFont(font)

        self.change_label = QLabel("-")

        summary_layout.addWidget(self.name_label)
        summary_layout.addWidget(self.price_label)
        summary_layout.addWidget(self.change_label)

        self.info_layout = QFormLayout()
        summary_layout.addLayout(self.info_layout)

        summary_layout.addStretch()

        #
        # ============================================================
        # Chart Panel
        # ============================================================
        #

        self.chart_view = QWebEngineView()

        #
        # ============================================================
        # News Panel
        # ============================================================
        #

        self.news_group = QGroupBox("News")

        news_layout = QVBoxLayout(self.news_group)

        self.news_button = QPushButton("Load News")
        self.news_button.clicked.connect(self.load_news)

        self.news_browser = QTextBrowser()
        self.news_browser.setOpenLinks(False)
        self.news_browser.anchorClicked.connect(
            QDesktopServices.openUrl
        )

        news_layout.addWidget(self.news_button)
        news_layout.addWidget(self.news_browser)

        #
        # ============================================================
        # Right Side
        # ============================================================
        #

        right_widget = QWidget()

        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Chart controls bar
        controls = QVBoxLayout()
        controls.setSpacing(4)

        # Row: Range radio buttons
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Range:"))
        self.range_group = QButtonGroup(self)
        for label in ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]:
            rb = QRadioButton(label)
            self.range_group.addButton(rb)
            range_row.addWidget(rb)
        self.range_group.buttons()[5].setChecked(True)  # "1y"
        self.range_group.buttonClicked.connect(self.update_chart)
        range_row.addStretch()
        controls.addLayout(range_row)

        # Row: Interval radio buttons
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Interval:"))
        self.interval_group = QButtonGroup(self)
        for label in ["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"]:
            rb = QRadioButton(label)
            self.interval_group.addButton(rb)
            interval_row.addWidget(rb)
        self.interval_group.buttons()[5].setChecked(True)  # "1d"
        self.interval_group.buttonClicked.connect(self.update_chart)
        interval_row.addStretch()
        controls.addLayout(interval_row)

        # Row: Chart type radio + Color dropdown + Indicators
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Chart:"))
        self.chart_group = QButtonGroup(self)
        for label in ["Candlestick", "Line"]:
            rb = QRadioButton(label)
            self.chart_group.addButton(rb)
            type_row.addWidget(rb)
        self.chart_group.buttons()[0].setChecked(True)
        self.chart_group.buttonClicked.connect(self.update_chart)

        type_row.addSpacing(16)
        type_row.addWidget(QLabel("Color:"))
        type_row.addWidget(self.color_combo)
        type_row.addSpacing(16)
        type_row.addWidget(QLabel("Indicators:"))
        type_row.addWidget(self.indicator_picker)
        type_row.addStretch()
        controls.addLayout(type_row)

        # Row: Price changes
        self.changes_widget = QWidget()
        self.changes_layout = QHBoxLayout(self.changes_widget)
        self.changes_layout.setContentsMargins(0, 0, 0, 0)
        self.changes_layout.setSpacing(16)
        controls.addWidget(self.changes_widget)

        # Summary + Chart side by side
        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(self.summary_group)
        h_splitter.addWidget(self.chart_view)
        h_splitter.setStretchFactor(0, 1)  # summary narrow
        h_splitter.setStretchFactor(1, 4)  # chart wide

        # Chart tab: controls bar + summary/chart splitter
        chart_tab = QWidget()
        chart_tab_layout = QVBoxLayout(chart_tab)
        chart_tab_layout.setContentsMargins(6, 6, 6, 6)
        chart_tab_layout.addLayout(controls, stretch=0)
        chart_tab_layout.addWidget(h_splitter, stretch=1)

        # Tab widget: Chart | News
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(chart_tab, "Chart")
        self.tab_widget.addTab(self.news_group, "News")

        right_layout.addWidget(self.tab_widget)

        #
        # ============================================================
        # Main Splitter
        # ============================================================
        #

        main_splitter = QSplitter()

        main_splitter.addWidget(self.thumbnail_scroll)
        main_splitter.addWidget(right_widget)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 4)

        #
        # ============================================================
        # Central Widget
        # ============================================================
        #

        central = QWidget()

        layout = QVBoxLayout(central)

        layout.addWidget(top_widget, stretch=0)
        layout.addWidget(main_splitter, stretch=1)

        self.setCentralWidget(central)

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def apply_tickers(self, tickers):
        """Populate the thumbnail panel with ticker cards."""
        # Remove existing cards
        for card in self.cards.values():
            card.setParent(None)
        self.cards.clear()

        # Clear the layout completely
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        # Create new cards
        for ticker in tickers:
            card = ThumbnailCard(ticker)
            card.clicked.connect(self.on_thumbnail_clicked)
            self.cards[ticker] = card
            self.thumbnail_layout.addWidget(card)

            # Load price info for the card
            self._load_thumbnail_info(ticker, card)

        # Add stretch at the end so cards stay at the top when there are few
        self.thumbnail_layout.addStretch()

        # Select the first ticker
        if tickers:
            self.on_thumbnail_clicked(tickers[0])

    def _load_thumbnail_info(self, ticker, card):
        """Load sparkline chart and price for a thumbnail card."""
        # Price info
        try:
            info = get_ticker_info(ticker)
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            currency = info.get("currency", "")

            if price is not None:
                card.price_label.setText(f"{price:,.2f} {currency}".strip())
        except Exception:
            pass

        # Sparkline chart
        try:
            fig = plot_ticker_thumbnail(
                ticker,
                date_range="5y",
                time_interval="1mo",
                timezone=self._timezone,
                dark_layout=self._dark_theme,
            )
            if fig is not None:
                fig.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0),
                )
                fig.update_xaxes(visible=False)
                fig.update_yaxes(visible=False)
                html = fig.to_html(
                    include_plotlyjs="cdn",
                    config={"staticPlot": True, "displayModeBar": False},
                )
                html = html.replace(
                    "</head>",
                    "<style>body{background:transparent;margin:0;}</style></head>",
                )
                card.chart_view.setHtml(html)
        except Exception:
            pass

    def on_apply_clicked(self):
        """Parse the ticker input field and rebuild thumbnails."""
        text = self.ticker_edit.text().strip()
        if not text:
            return
        tickers = [
            t.strip().upper()
            for t in text.replace("\n", ",").split(",")
            if t.strip()
        ]
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in tickers:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        self.apply_tickers(unique)

    def on_thumbnail_clicked(self, ticker):
        """Handle thumbnail card click — select a ticker."""
        self.current_symbol = ticker

        # Highlight the active card
        for t, card in self.cards.items():
            card.set_active(t == ticker)

        self.update_chart()
        self.update_summary()
        self._fetch_changes_data()
        self._update_changes_bar()

        # Clear news when switching tickers
        self.news_browser.setHtml("")

    def update_chart(self, _=None):
        """Update the main chart view for the current ticker."""
        if not self.current_symbol:
            return

        date_range = self.range_group.checkedButton().text()
        interval = self.interval_group.checkedButton().text()

        chart_type_text = self.chart_group.checkedButton().text()
        if chart_type_text == "Candlestick":
            chart_type = ChartType.CANDLE
        else:
            chart_type = ChartType.LINE

        color_name = self.color_combo.currentText().upper().replace(" ", "_")
        try:
            candle_color = CandleColor[color_name]
        except KeyError:
            candle_color = CandleColor.GREEN_RED

        # Parse indicators from the picker
        indicator_specs = self.indicator_picker.selected_values()
        indicators = []
        for spec in indicator_specs:
            try:
                indicators.append(parse_indicator(spec))
            except ValueError:
                pass

        try:
            fig = plot_ticker_chart(
                ticker=self.current_symbol,
                date_range=date_range,
                time_interval=interval,
                chart_type=chart_type,
                candle_color=candle_color,
                indicators=indicators if indicators else None,
                timezone=self._timezone,
                dark_layout=self._dark_theme,
            )
        except Exception:
            fig = None

        if fig is not None:
            html = fig.to_html(
                include_plotlyjs="cdn",
                config={"responsive": True},
            )
            html = html.replace(
                "</head>",
                "<style>body{background:transparent;margin:0;}</style></head>",
            )
            self.chart_view.setHtml(html)
        else:
            self.chart_view.setHtml(
                f"<p style='color:#888;'>No data available for '{self.current_symbol}'</p>"
            )

        self._update_changes_bar()

    def update_summary(self):
        """Update the summary panel for the current ticker."""
        if not self.current_symbol:
            return

        # Fetch ticker info
        try:
            info = get_ticker_info(self.current_symbol)
        except Exception:
            info = {}

        name = (
            info.get("longName")
            or info.get("shortName")
            or self.current_symbol
        )
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        currency = info.get("currency", "")
        prev_close = info.get("previousClose")

        self.name_label.setText(name)
        if price is not None:
            self.price_label.setText(f"{price:,.2f} {currency}".strip())
        else:
            self.price_label.setText("-")

        # Day change
        if price is not None and prev_close:
            day_change = (price - prev_close) / prev_close * 100
            color = "#26a69a" if day_change >= 0 else "#ef5350"
            self.change_label.setText(
                f"Day Change: {_fmt_pct(day_change)}"
            )
            self.change_label.setStyleSheet(f"color: {color}; font-size: 14px;")
        else:
            self.change_label.setText("Day Change: N/A")
            self.change_label.setStyleSheet("color: #888; font-size: 14px;")

        # Clear old info rows
        while self.info_layout.rowCount():
            self.info_layout.removeRow(0)

        # Key metrics
        pairs = [
            ("Open", _fmt_num(info.get("open"))),
            ("Prev Close", _fmt_num(prev_close)),
            ("Day Low", _fmt_num(info.get("dayLow"))),
            ("Day High", _fmt_num(info.get("dayHigh"))),
            ("52W Low", _fmt_num(info.get("fiftyTwoWeekLow"))),
            ("52W High", _fmt_num(info.get("fiftyTwoWeekHigh"))),
            ("Volume", _fmt_num(info.get("volume") or info.get("regularMarketVolume"))),
            ("Avg Volume", _fmt_num(info.get("averageVolume"))),
            ("Market Cap", _fmt_num(info.get("marketCap"))),
            ("P/E (TTM)", _fmt_num(info.get("trailingPE"))),
            ("Fwd P/E", _fmt_num(info.get("forwardPE"))),
            ("Div Yield", _fmt_pct(info.get("dividendYield")) if info.get("dividendYield") is not None else "N/A"),
        ]
        for key, val in pairs:
            self.info_layout.addRow(QLabel(key + ":"), QLabel(val))

    def _fetch_changes_data(self):
        """Fetch price change data for the changes bar."""
        if not self.current_symbol:
            self._changes_data = []
            return
        try:
            df = get_ticker_data(
                self.current_symbol,
                date_range="1y",
                time_interval="1d",
                timezone=self._timezone,
            )
            changes = get_price_changes(df)
            labels = ["1D", "1W", "1M", "6M", "1Y"]
            self._changes_data = list(zip(labels, changes))
        except Exception:
            self._changes_data = []

    def _update_changes_bar(self):
        """Render the price changes bar using the current candle colors."""
        # Clear old labels
        while self.changes_layout.count():
            item = self.changes_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        # Get candle colors
        color_name = self.color_combo.currentText().upper().replace(" ", "_")
        try:
            candle_color = CandleColor[color_name]
        except KeyError:
            candle_color = CandleColor.GREEN_RED
        up_color, down_color = candle_color.value

        for label, val in self._changes_data:
            if val is None:
                color = "#888"
            elif val >= 0:
                color = up_color
            else:
                color = down_color
            lbl = QLabel(f"{label}: {_fmt_pct(val)}")
            lbl.setStyleSheet(
                f"color: {color}; font-weight: bold; font-size: 13px;"
            )
            self.changes_layout.addWidget(lbl)
        self.changes_layout.addStretch()

    def load_news(self):
        """Load news for the current ticker into the news browser."""
        if not self.current_symbol:
            return

        self.news_button.setEnabled(False)
        self.news_button.setText("Loading...")

        try:
            with TickerNewsClient() as client:
                items = client.get_news_for_ticker(
                    self.current_symbol, days=5
                )
        except Exception:
            self.news_browser.setHtml(
                "<p style='color:#ef5350;'><i>Failed to load news.</i></p>"
            )
            self.news_button.setEnabled(True)
            self.news_button.setText("Load News")
            return

        if not items:
            self.news_browser.setHtml(
                "<p style='color:#888;'><i>No recent news found.</i></p>"
            )
            self.news_button.setEnabled(True)
            self.news_button.setText("Load News")
            return

        html_parts = []
        for item in items[:15]:
            html_parts.append(
                f'<p style="margin-bottom: 8px;">'
                f'<a href="{item["link"]}" style="color: #e0e0e0; text-decoration: none;">'
                f'{item["title"]}</a><br>'
                f'<small style="color: #888;">'
                f'{item["published"]:%Y-%m-%d %H:%M}</small>'
                f'</p>'
            )
        self.news_browser.setHtml("".join(html_parts))

        self.news_button.setEnabled(True)
        self.news_button.setText("Load News")

    def change_theme(self, theme_name):
        """Apply a qt_material theme and refresh chart colors."""
        apply_stylesheet(QApplication.instance(), theme=theme_name)

        # Detect dark vs light
        was_dark = self._dark_theme
        self._dark_theme = "dark" in theme_name.lower()

        # Refresh chart and thumbnails if theme mode changed
        if was_dark != self._dark_theme:
            self.update_chart()
            for ticker, card in self.cards.items():
                self._load_thumbnail_info(ticker, card)

    def change_timezone(self, tz_name):
        """Update the timezone and refresh all chart data."""
        self._timezone = tz_name
        self.update_chart()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme="dark_teal.xml")
    window = StockApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()