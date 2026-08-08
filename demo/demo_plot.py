from imple.indicator.classic import SMA, MACD
from imple.forecaster.timesfm import TimesFM
from core.plot import plot_ticker_thumbnail, plot_ticker_chart


def demo_thumbnail():
    fig = plot_ticker_thumbnail("AAPL", "1y", "1d")
    fig.show()


def demo_chart():
    fig = plot_ticker_chart(
        "AAPL",
        "1y",
        "1d",
        indicators=[
            SMA(20),
            MACD(),
        ],
        forecasters=[
            TimesFM(30),
        ]
    )
    fig.show()


def demo_plot():
    demo_thumbnail()
    demo_chart()


if __name__ == "__main__":
    demo_plot()