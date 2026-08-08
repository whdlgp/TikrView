import torch
import pandas as pd
from chronos import Chronos2Pipeline
from core.forecaster import Forecaster


class Chronos2(Forecaster):
    def __init__(self, pred_len: int):
        self.pred_len = pred_len

        self.pipeline = self.get_cached_model("chronos-2")
        if self.pipeline is None:
            device_map = "cuda" if torch.cuda.is_available() else "cpu"
            self.pipeline = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=device_map)
            self.cache_model("chronos-2", self.pipeline)

    @property
    def display_name(self) -> str:
        return f"Chronos-2 ({self.pred_len})"

    def calc(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        original_tz = df.index.tz
        df.index = df.index.tz_localize(None)

        df = df.reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        df = df.rename(columns={df.columns[0]: "timestamp"})

        context_df = pd.DataFrame({
            "id": "series",
            "timestamp": df["timestamp"],
            "target": df["close"],
        })

        pred_df = self.pipeline.predict_df(
            context_df,
            prediction_length=self.pred_len,
            quantile_levels=[0.1, 0.5, 0.9],
            id_column="id",
            timestamp_column="timestamp",
            target="target",
            freq="B",
        )

        pred_df = pred_df.rename(columns={
            "timestamp": "Date",
            "predictions": "median",
            "0.1": "lower",
            "0.9": "upper",
        })

        pred_df = pred_df.set_index("Date")

        if original_tz is not None:
            pred_df.index = pred_df.index.tz_localize(original_tz)

        return pred_df[["median", "lower", "upper"]]
