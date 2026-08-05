"""
TikrView - a simple stock dashboard GUI.

+--------------------------------------------------------------------+
| Tickers [___________] [Apply] [Save]   Theme [v]   Timezone [v]    |
+----------------+---------------------------------------------------+
| [Thumbnail]     | CHART | NEWS                                     |
| [Thumbnail]     |--------------------------------------------------|
| [Thumbnail]     | Range / Interval / Chart type / Indicators       |
| [Thumbnail]     |--------------------------------------------------|
| [Thumbnail]     | +-----------+  +----------------------------+    |
| ...             | | Summary   |  |                            |    |
| (scrollable)    | | - price   |  |          Chart             |    |
|                 | | - stats   |  |                            |    |
|                 | +-----------+  +----------------------------+    |
+----------------+---------------------------------------------------+

Usage:
    python dashboard.py
"""

import sys
from pathlib import Path
import shutil
import json

import traceback

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal, Slot, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QAction, QDesktopServices, QTextCursor

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter, QScrollArea
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QComboBox, QRadioButton, QButtonGroup, QSpinBox
from PySide6.QtWidgets import QGroupBox, QFrame, QTabWidget, QTextBrowser, QSizePolicy, QMenu

from PySide6.QtWebEngineWidgets import QWebEngineView

from qt_material import apply_stylesheet, list_themes

from core.market import get_ticker_data, get_ticker_info
from core.plot import ChartType, CandleColor, plot_ticker_chart, plot_ticker_thumbnail
from core.indicator import get_price_changes, parse_indicator
from core.news import TickerNewsClient


# === Background threading ===

class WorkerSignals(QObject):
    """
    Signals for Worker's results.
    QRunnable can't send signals on its own.
    """

    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    """Runs a function on a background thread, to keep the GUI responsive."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            self.signals.error.emit(traceback.format_exc())
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


# === UI option constants ===

DATA_RANGE_OPTIONS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]
TIME_INTERVAL_OPTIONS = ["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"]
TIME_ZONE_OPTIONS = [
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
]
INDICATOR_OPTIONS = [
    ("SMA 5", "SMA:5"),
    ("SMA 10", "SMA:10"),
    ("SMA 20", "SMA:20"),
    ("SMA 50", "SMA:50"),
    ("SMA 60", "SMA:60"),
    ("SMA 120", "SMA:120"),
    ("SMA 200", "SMA:200"),
    ("AVWAP", "AVWAP"),
    ("KAMA 10", "KAMA:10"),
    ("Bollinger Bands (20,2.0)", "BBANDS:20,2.0"),
    ("SuperTrend (10,3.0)", "SuperTrend:10,3.0"),
    ("Williams %R (14)", "WilliamsR:14"),
    ("MFI (14)", "MFI:14"),
    ("ATR (14)", "ATR:14"),
    ("StochRSI (14,2,3)", "StochRSI:14,2,3"),
    ("Fisher (10,3)", "Fisher:10,3"),
    ("MACD (12,26,9)", "MACD:12,26,9"),
    ("ADX (14)", "ADX:14"),
]


# === Default values ===

DEFAULT_TICKERS = [
    "SPY",        # S&P 500
    "QQQ",        # Nasdaq 100
    "SCHD",       # Schwab US Dividend Equity ETF

    "AAPL",       # Apple
    "MSFT",       # Microsoft
    "NVDA",       # Nvidia
    "TSLA",       # Tesla
    "GOOGL",      # Google

    "005930.KS",  # SAMSUNG
    "000660.KS",  # SK Hynix
    "GLD",        # Gold
]
DEFAULT_INDICATORS = ["SMA:20", "SMA:60", "VWAP"]


# === Config ===

@dataclass
class Config:
    """App settings, loaded from and saved to a JSON file."""

    theme: str = "dark_teal.xml"
    timezone: str = "Asia/Seoul"
    window_width: int = 1650
    window_height: int = 920
    tickers: list = field(default_factory=lambda: DEFAULT_TICKERS.copy())
    date_range: str = "1y"
    time_interval: str = "1d"
    chart_type: str = "Candlestick"
    candle_color: str = "Green_Red"
    indicators: list = field(default_factory=lambda: DEFAULT_INDICATORS.copy())

    @classmethod
    def load(cls, path="config.json"):
        with open(path) as config_file:
            data = json.load(config_file)

        return cls(
            theme=data.get("theme", "dark_teal.xml"),
            timezone=data.get("timezone", "Asia/Seoul"),
            window_width=data.get("window_width", 1650),
            window_height=data.get("window_height", 920),
            tickers=data.get("tickers", DEFAULT_TICKERS),
            date_range=data.get("range", "1y"),
            time_interval=data.get("interval", "1d"),
            chart_type=data.get("chart_type", "Candlestick"),
            candle_color=data.get("candle_color", "Green_Red"),
            indicators=data.get("indicators", DEFAULT_INDICATORS),
        )

    def save(self, path="config.json"):
        data = {
            "theme": self.theme,
            "timezone": self.timezone,
            "window_width": self.window_width,
            "window_height": self.window_height,
            "tickers": self.tickers,
            "range": self.date_range,
            "interval": self.time_interval,
            "chart_type": self.chart_type,
            "candle_color": self.candle_color,
            "indicators": self.indicators,
        }
        with open(path, "w") as config_file:
            json.dump(data, config_file, indent=4)


# === Formatting helpers ===

def fmt_num(value, digits=2):
    """
    Formats a number with K/M/B/T suffixes.
    e.g. 1500000 -> "1.50M"
    """

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


def fmt_pct(value):
    """
    Formats a number as a percent string.
    e.g. 1.234 -> "+1.23%"
    """

    if value is None:
        return "N/A"
    try:
        return f"{value:+.2f}%"
    except Exception:
        return "N/A"


# === Sub-widgets ===

class IndicatorPicker(QWidget):
    """A button with a checklist menu for picking indicators."""

    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.button = QPushButton("Indicators...")
        self.button.clicked.connect(self.show_menu)

        self.menu = QMenu(self)
        self.actions = {}

        for label, value in INDICATOR_OPTIONS:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(value)
            action.toggled.connect(self.toggled)
            self.menu.addAction(action)
            self.actions[value] = action

        layout.addWidget(self.button)

    def show_menu(self):
        self.menu.exec(
            self.button.mapToGlobal(self.button.rect().bottomLeft())
        )

    def toggled(self):
        self.update_label()
        self.selection_changed.emit()

    def update_label(self):
        selected = self.selected_values()
        if selected:
            self.button.setText(", ".join(selected))
        else:
            self.button.setText("Indicators...")

    def selected_values(self):
        return [a.data() for a in self.actions.values() if a.isChecked()]

    def set_selected(self, values):
        for v, a in self.actions.items():
            a.setChecked(v in values)
        self.update_label()


class ThumbnailCard(QFrame):
    """A small card showing one ticker's mini chart and price."""

    clicked = Signal(str)

    def __init__(self, ticker, parent=None):
        super().__init__(parent)
        self.ticker = ticker
        self.active = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        self.ticker_label = QLabel(ticker)
        font = self.ticker_label.font()
        font.setBold(True)
        font.setPointSize(12)
        self.ticker_label.setFont(font)

        self.chart_view = QWebEngineView()
        self.chart_view.setFixedHeight(115)
        self.chart_view.page().setBackgroundColor(Qt.transparent)
        self.chart_view.setAttribute(Qt.WA_TransparentForMouseEvents)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.price_label = QLabel("-")
        self.price_label.setStyleSheet("font-size: 11px;")

        row.addWidget(self.price_label)
        row.addStretch()

        layout.addWidget(self.ticker_label)
        layout.addWidget(self.chart_view)
        layout.addLayout(row)

        self.update_style()

    def mousePressEvent(self, event):
        self.clicked.emit(self.ticker)
        super().mousePressEvent(event)

    def set_active(self, active):
        self.active = active
        self.update_style()

    def update_style(self):
        if self.active:
            self.setStyleSheet(
                "ThumbnailCard { border: 2px solid #26a69a; border-radius: 6px; }"
            )
        else:
            self.setStyleSheet(
                "ThumbnailCard { border: 1px solid #444; border-radius: 6px; }"
            )


# === Main panels ===

class TopBar(QWidget):
    """Top bar for entering tickers and picking theme/timezone."""

    tickers_applied = Signal(list)
    theme_changed = Signal(str)
    timezone_changed = Signal(str)
    save_requested = Signal()

    def __init__(self, config, parent=None):
        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.ticker_edit = QLineEdit(",".join(config.tickers))

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_clicked)

        self.save_button = QPushButton("Save Config")
        self.save_button.clicked.connect(self.save_requested)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list_themes())
        self.theme_combo.setCurrentText(config.theme)
        self.theme_combo.setMinimumWidth(140)
        self.theme_combo.currentTextChanged.connect(self.theme_changed)

        self.timezone_combo = QComboBox()
        self.timezone_combo.addItems(TIME_ZONE_OPTIONS)
        self.timezone_combo.setCurrentText(config.timezone)
        self.timezone_combo.setMinimumWidth(140)
        self.timezone_combo.currentTextChanged.connect(self.timezone_changed)

        layout = QVBoxLayout(self)

        row = QHBoxLayout()

        row.addWidget(QLabel("Tickers"))
        row.addWidget(self.ticker_edit)
        row.addWidget(self.apply_button)
        row.addWidget(self.save_button)

        row.addSpacing(20)

        row.addWidget(QLabel("Theme"))
        row.addWidget(self.theme_combo)

        row.addSpacing(12)

        row.addWidget(QLabel("Timezone"))
        row.addWidget(self.timezone_combo)

        row.addStretch()

        layout.addLayout(row)

    def apply_clicked(self):
        text = self.ticker_edit.text().strip()
        if not text:
            return

        tickers = [t.strip().upper() for t in text.split(",") if t.strip()]

        seen = set()
        unique = []
        for t in tickers:
            if t not in seen:
                seen.add(t)
                unique.append(t)

        self.tickers_applied.emit(unique)


class ThumbnailPanel(QScrollArea):
    """Scrollable list of ThumbnailCards."""

    ticker_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWidgetResizable(True)
        self.setMinimumWidth(280)

        self.cards = {}

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch()

        self.setWidget(self.content)

    def set_tickers(self, tickers):
        for card in self.cards.values():
            card.setParent(None)
        self.cards.clear()

        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        for ticker in tickers:
            card = ThumbnailCard(ticker)
            card.clicked.connect(self.ticker_selected)
            self.cards[ticker] = card
            self.content_layout.addWidget(card)

        self.content_layout.addStretch()

    def update_card(self, ticker, price_text=None, chart_html=None):
        card = self.cards.get(ticker)
        if card is None:
            return
        if price_text is not None:
            card.price_label.setText(price_text)
        if chart_html is not None:
            card.chart_view.setHtml(chart_html)

    def set_active(self, ticker):
        for t, card in self.cards.items():
            card.set_active(t == ticker)


class SummaryPanel(QGroupBox):
    """Shows the selected ticker's price and key stats."""

    def __init__(self, parent=None):
        super().__init__("Summary", parent)

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)

        self.name_label = QLabel("-")
        self.name_label.setWordWrap(True)
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

        layout.addWidget(self.name_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)

        self.info_layout = QFormLayout()
        layout.addLayout(self.info_layout)

        layout.addStretch()

    def render(self, name, price_text, change_text, change_color, pairs):
        self.name_label.setText(name)
        self.price_label.setText(price_text)

        self.change_label.setText(change_text)
        self.change_label.setStyleSheet(f"color: {change_color}; font-size: 14px;")

        while self.info_layout.rowCount():
            self.info_layout.removeRow(0)

        for key, val in pairs:
            self.info_layout.addRow(QLabel(key + ":"), QLabel(val))


@dataclass
class ChartSettings:
    """Chart options."""

    date_range: str
    interval: str
    chart_type: ChartType
    candle_color: CandleColor
    indicators: list


class ChartPanel(QWidget):
    """
    Chart settings UI (range, interval, indicators, etc.)
    and chart display area.
    """

    settings_changed = Signal()

    def __init__(self, config, summary_panel, parent=None):
        super().__init__(parent)

        self.chart_view = QWebEngineView()

        controls = QVBoxLayout()
        controls.setSpacing(4)

        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Range:"))
        self.range_group = QButtonGroup(self)
        for label in DATA_RANGE_OPTIONS:
            rb = QRadioButton(label)
            self.range_group.addButton(rb)
            range_row.addWidget(rb)
        range_idx = DATA_RANGE_OPTIONS.index(config.date_range)
        self.range_group.buttons()[range_idx].setChecked(True)
        self.range_group.buttonClicked.connect(self.settings_changed)
        range_row.addStretch()
        controls.addLayout(range_row)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Interval:"))
        self.interval_group = QButtonGroup(self)
        for label in TIME_INTERVAL_OPTIONS:
            rb = QRadioButton(label)
            self.interval_group.addButton(rb)
            interval_row.addWidget(rb)
        interval_idx = TIME_INTERVAL_OPTIONS.index(config.time_interval)
        self.interval_group.buttons()[interval_idx].setChecked(True)
        self.interval_group.buttonClicked.connect(self.settings_changed)
        interval_row.addStretch()
        controls.addLayout(interval_row)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Chart:"))
        self.chart_group = QButtonGroup(self)
        for label in ["Candlestick", "Line"]:
            rb = QRadioButton(label)
            self.chart_group.addButton(rb)
            type_row.addWidget(rb)
        type_idx = ["Candlestick", "Line"].index(config.chart_type)
        self.chart_group.buttons()[type_idx].setChecked(True)
        self.chart_group.buttonClicked.connect(self.settings_changed)

        self.color_combo = QComboBox()
        self.color_combo.addItems([color.name.title() for color in CandleColor])
        self.color_combo.setCurrentText(config.candle_color)
        self.color_combo.setMinimumWidth(130)
        self.color_combo.currentIndexChanged.connect(self.settings_changed)
        type_row.addSpacing(16)
        type_row.addWidget(QLabel("Color:"))
        type_row.addWidget(self.color_combo)

        self.indicator_picker = IndicatorPicker()
        self.indicator_picker.set_selected(config.indicators)
        self.indicator_picker.selection_changed.connect(self.settings_changed)
        type_row.addSpacing(16)
        type_row.addWidget(QLabel("Indicators:"))
        type_row.addWidget(self.indicator_picker)
        type_row.addStretch()
        controls.addLayout(type_row)

        self.changes_widget = QWidget()
        self.changes_layout = QHBoxLayout(self.changes_widget)
        self.changes_layout.setContentsMargins(0, 0, 0, 0)
        self.changes_layout.setSpacing(16)
        controls.addWidget(self.changes_widget)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(summary_panel)
        splitter.addWidget(self.chart_view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([100, 400]) 

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(controls, stretch=0)
        layout.addWidget(splitter, stretch=1)

    def settings(self):
        chart_type_text = self.chart_group.checkedButton().text()
        chart_type = ChartType.CANDLE if chart_type_text == "Candlestick" else ChartType.LINE

        color_name = self.color_combo.currentText().upper().replace(" ", "_")
        try:
            candle_color = CandleColor[color_name]
        except KeyError:
            candle_color = CandleColor.GREEN_RED

        indicators = []
        for spec in self.indicator_picker.selected_values():
            try:
                indicators.append(parse_indicator(spec))
            except ValueError:
                pass

        return ChartSettings(
            date_range=self.range_group.checkedButton().text(),
            interval=self.interval_group.checkedButton().text(),
            chart_type=chart_type,
            candle_color=candle_color,
            indicators=indicators,
        )

    def render(self, fig, symbol):
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
                f"<p style='color:#888;'>No data available for '{symbol}'</p>"
            )

    def render_changes(self, changes_data):
        while self.changes_layout.count():
            item = self.changes_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        up_color, down_color = self.settings().candle_color.value

        for label, val in changes_data:
            if val is None:
                color = "#888"
            elif val >= 0:
                color = up_color
            else:
                color = down_color
            lbl = QLabel(f"{label}: {fmt_pct(val)}")
            lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px;")
            self.changes_layout.addWidget(lbl)

        self.changes_layout.addStretch()


class NewsPanel(QGroupBox):
    """Shows recent news for the selected ticker."""

    news_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("News", parent)

        layout = QVBoxLayout(self)

        button_layout = QHBoxLayout()

        self.button = QPushButton("Load News")
        self.button.clicked.connect(self.news_requested)

        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 365)
        self.days_spin.setValue(5)
        self.days_spin.setSuffix(" days")

        button_layout.addWidget(self.button)
        button_layout.addWidget(self.days_spin)
        button_layout.addStretch()

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(QDesktopServices.openUrl)

        layout.addLayout(button_layout)
        layout.addWidget(self.browser)

        self.news_items = []
        self.loaded_count = 0
        self.chunk_size = 30

        self.browser.verticalScrollBar().valueChanged.connect(self.on_news_scroll)

    def set_loading(self, loading):
        self.button.setEnabled(not loading)
        self.button.setText("Loading..." if loading else "Load News")

    def show_items(self, items):
        if not items:
            self.browser.setHtml("<p style='color:#888;'><i>No recent news found.</i></p>")
            return

        self.news_items = items
        self.loaded_count = 0

        end = min(self.chunk_size, len(self.news_items))

        html_parts = []
        for item in self.news_items[:end]:
            html_parts.append(
                f'<p style="margin-bottom: 8px;">'
                f'<a href="{item["link"]}" style="text-decoration: none;">'
                f'({item["query"]}) {item["title"]}</a><br>'
                f'<small>{item["published"]:%Y-%m-%d %H:%M}</small>'
                f'</p>'
            )

        self.browser.setHtml("".join(html_parts))
        self.loaded_count = end

    def on_news_scroll(self, value):
        bar = self.browser.verticalScrollBar()

        if value < bar.maximum() - 100:
            return

        if self.loaded_count >= len(self.news_items):
            return

        end = min(self.loaded_count + self.chunk_size, len(self.news_items))

        html_parts = []
        for item in self.news_items[self.loaded_count:end]:
            html_parts.append(
                f'<p style="margin-bottom: 8px;">'
                f'<a href="{item["link"]}" style="text-decoration: none;">'
                f'({item["query"]}) {item["title"]}</a><br>'
                f'<small>{item["published"]:%Y-%m-%d %H:%M}</small>'
                f'</p>'
            )

        cursor = self.browser.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml("".join(html_parts))

        self.loaded_count = end

    def show_error(self):
        self.browser.setHtml("<p style='color:#ef5350;'><i>Failed to load news.</i></p>")

    def clear(self):
        self.news_items = []
        self.loaded_count = 0
        self.browser.setHtml("")


# === Main window ===

class StockApp(QMainWindow):
    """
    Main window.
    holds all panels and updates them.
    """

    def __init__(self, config: Config):
        super().__init__()

        self.config = config

        self.current_symbol = None
        self.dark_theme = "dark" in config.theme.lower()
        self.timezone = config.timezone
        self.changes_data = []

        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(4)
        self._workers = []
        self._req_token = 0
        self._chart_token = 0

        self.setWindowTitle("TikrView")
        self.resize(config.window_width, config.window_height)

        self.build_ui()

        self.apply_tickers(config.tickers)

    def build_ui(self):
        self.top_bar = TopBar(self.config)
        self.top_bar.tickers_applied.connect(self.apply_tickers)
        self.top_bar.theme_changed.connect(self.change_theme)
        self.top_bar.timezone_changed.connect(self.change_timezone)

        self.top_bar.save_requested.connect(self.save_config)

        self.thumbnail_panel = ThumbnailPanel()
        self.thumbnail_panel.ticker_selected.connect(self.select_ticker)

        self.summary_panel = SummaryPanel()

        self.chart_panel = ChartPanel(self.config, self.summary_panel)
        self.chart_panel.settings_changed.connect(self.update_chart)

        self.news_panel = NewsPanel()
        self.news_panel.news_requested.connect(self.load_news)

        tab_widget = QTabWidget()
        tab_widget.addTab(self.chart_panel, "Chart")
        tab_widget.addTab(self.news_panel, "News")

        main_splitter = QSplitter()
        main_splitter.addWidget(self.thumbnail_panel)
        main_splitter.addWidget(tab_widget)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 4)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.top_bar, stretch=0)
        layout.addWidget(main_splitter, stretch=1)

        self.setCentralWidget(central)

    def run_async(self, fn, callback, *args, **kwargs):
        worker = Worker(fn, *args, **kwargs)
        worker.signals.result.connect(callback)
        worker.signals.finished.connect(lambda: self._workers.remove(worker))
        self._workers.append(worker)
        self.pool.start(worker)

    def apply_tickers(self, tickers):
        self.thumbnail_panel.set_tickers(tickers)

        for ticker in tickers:
            self.refresh_thumbnail(ticker)

        if tickers:
            self.select_ticker(tickers[0])

    def refresh_thumbnail(self, ticker):
        timezone = self.timezone
        dark_theme = self.dark_theme

        def build():
            try:
                info = get_ticker_info(ticker)
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                currency = info.get("currency", "")
                price_text = f"{price:,.2f} {currency}".strip() if price is not None else None
            except Exception:
                price_text = None

            try:
                fig = plot_ticker_thumbnail(
                    ticker,
                    date_range="5y",
                    time_interval="1mo",
                    timezone=timezone,
                    dark_layout=dark_theme,
                )
                if fig is not None:
                    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
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
                else:
                    html = None
            except Exception:
                html = None

            return price_text, html

        def apply(result):
            price_text, html = result
            self.thumbnail_panel.update_card(ticker, price_text, html)

        self.run_async(build, apply)

    def select_ticker(self, ticker):
        self.current_symbol = ticker
        self.thumbnail_panel.set_active(ticker)

        self.update_chart()
        self.update_summary()

        self._req_token += 1
        token = self._req_token
        timezone = self.timezone

        def build():
            try:
                df = get_ticker_data(
                    ticker,
                    date_range="1y",
                    time_interval="1d",
                    timezone=timezone,
                )
                return get_price_changes(df)
            except Exception:
                return None

        def apply(changes):
            if token != self._req_token:
                return

            labels = ["1D", "1W", "1M", "6M", "1Y"]
            self.changes_data = list(zip(labels, changes)) if changes is not None else []
            self.chart_panel.render_changes(self.changes_data)

        self.run_async(build, apply)

        self.news_panel.clear()

    def update_chart(self):
        if not self.current_symbol:
            return

        settings = self.chart_panel.settings()
        symbol = self.current_symbol
        timezone = self.timezone
        dark_theme = self.dark_theme

        self._chart_token += 1
        token = self._chart_token

        def build():
            try:
                return plot_ticker_chart(
                    ticker=symbol,
                    date_range=settings.date_range,
                    time_interval=settings.interval,
                    chart_type=settings.chart_type,
                    candle_color=settings.candle_color,
                    indicators=settings.indicators if settings.indicators else None,
                    timezone=timezone,
                    dark_layout=dark_theme,
                )
            except Exception:
                return None

        def apply(fig):
            if token != self._chart_token:
                return

            self.chart_panel.render(fig, symbol)
            self.chart_panel.render_changes(self.changes_data)

        self.run_async(build, apply)

    def update_summary(self):
        if not self.current_symbol:
            return

        symbol = self.current_symbol

        def build():
            try:
                return get_ticker_info(symbol)
            except Exception:
                return {}

        def apply(info):
            if symbol != self.current_symbol:
                return

            name = info.get("longName") or info.get("shortName") or symbol
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            currency = info.get("currency", "")
            prev_close = info.get("previousClose")

            price_text = f"{price:,.2f} {currency}".strip() if price is not None else "-"

            if price is not None and prev_close:
                day_change = (price - prev_close) / prev_close * 100
                change_color = "#26a69a" if day_change >= 0 else "#ef5350"
                change_text = f"Day Change: {fmt_pct(day_change)}"
            else:
                change_color = "#888"
                change_text = "Day Change: N/A"

            pairs = [
                ("Open", fmt_num(info.get("open"))),
                ("Prev Close", fmt_num(prev_close)),
                ("Day Low", fmt_num(info.get("dayLow"))),
                ("Day High", fmt_num(info.get("dayHigh"))),
                ("52W Low", fmt_num(info.get("fiftyTwoWeekLow"))),
                ("52W High", fmt_num(info.get("fiftyTwoWeekHigh"))),
                ("Volume", fmt_num(info.get("volume") or info.get("regularMarketVolume"))),
                ("Avg Volume", fmt_num(info.get("averageVolume"))),
                ("Market Cap", fmt_num(info.get("marketCap"))),
                ("P/E (TTM)", fmt_num(info.get("trailingPE"))),
                ("Fwd P/E", fmt_num(info.get("forwardPE"))),
                ("Div Yield", fmt_pct(info.get("dividendYield")) if info.get("dividendYield") is not None else "N/A"),
            ]

            self.summary_panel.render(name, price_text, change_text, change_color, pairs)

        self.run_async(build, apply)

    def load_news(self):
        if not self.current_symbol:
            return

        symbol = self.current_symbol
        self.news_panel.set_loading(True)

        def build():
            try:
                with TickerNewsClient() as client:
                    return client.get_news_for_ticker(symbol, days=self.news_panel.days_spin.value())
            except Exception:
                return None

        def apply(items):
            if symbol != self.current_symbol:
                return

            if items is None:
                self.news_panel.show_error()
            else:
                self.news_panel.show_items(items)

            self.news_panel.set_loading(False)

        self.run_async(build, apply)

    def change_theme(self, theme_name):
        apply_stylesheet(QApplication.instance(), theme=theme_name)

        was_dark = self.dark_theme
        self.dark_theme = "dark" in theme_name.lower()

        if was_dark != self.dark_theme:
            self.update_chart()
            for ticker in self.thumbnail_panel.cards:
                self.refresh_thumbnail(ticker)

    def change_timezone(self, tz_name):
        self.timezone = tz_name
        self.update_chart()

    def save_config(self):
        settings = self.chart_panel.settings()

        tickers = [t.strip().upper() for t in self.top_bar.ticker_edit.text().split(",") if t.strip()]

        config = Config(
            theme=self.top_bar.theme_combo.currentText(),
            timezone=self.timezone,
            window_width=self.width(),
            window_height=self.height(),
            tickers=tickers,
            date_range=settings.date_range,
            time_interval=settings.interval,
            chart_type=self.chart_panel.chart_group.checkedButton().text(),
            candle_color=self.chart_panel.color_combo.currentText(),
            indicators=self.chart_panel.indicator_picker.selected_values(),
        )
        config.save()


def main():
    if not Path("config.json").exists():
        shutil.copy("config_example.json", "config.json")
    config = Config.load("config.json")

    app = QApplication(sys.argv)
    apply_stylesheet(app, theme=config.theme)
    window = StockApp(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()