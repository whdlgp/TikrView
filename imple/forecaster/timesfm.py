import pandas as pd
import timesfm
from core.forecaster import Forecaster


class TimesFM(Forecaster):
    def __init__(self, pred_len: int):
        self.pred_len = pred_len

        self.model = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
        self.model.compile(
            timesfm.ForecastConfig(
                max_context=1024,
                max_horizon=256,
                normalize_inputs=True,
                use_continuous_quantile_head=True,
                force_flip_invariance=True,
                infer_is_positive=True,
                fix_quantile_crossing=True,
            )
        )

    @property
    def display_name(self) -> str:
        return f"TimesFM 2.5 ({self.pred_len})"

    def calc(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["Close"].to_numpy()
        last_date = df.index[-1]
        future_dates = pd.bdate_range(last_date, periods=self.pred_len + 1)[1:]

        point_forecast, quantile_forecast = self.model.forecast(horizon=self.pred_len, inputs=[close])

        return pd.DataFrame(
            {
                "median": point_forecast[0],
                "lower": quantile_forecast[0, :, 1],
                "upper": quantile_forecast[0, :, 9],
            },
            index=pd.DatetimeIndex(future_dates),
        )
