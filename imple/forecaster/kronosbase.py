import torch
import numpy as np
import pandas as pd
from model import Kronos, KronosTokenizer, KronosPredictor
from core.forecaster import Forecaster


class KronosBase(Forecaster):
    def __init__(self, pred_len: int, lookback=400, n_samples=30, temperature=1.0, top_p=0.9):
        self.pred_len = pred_len
        
        self.lookback = lookback
        self.n_samples = n_samples
        self.temperature = temperature
        self.top_p = top_p

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
        model = Kronos.from_pretrained("NeoQuasar/Kronos-base")
        self.predictor = KronosPredictor(model, tokenizer, device=device, max_context=512)

    @property
    def display_name(self) -> str:
        extras = []
        if self.lookback != 400:
            extras.append(f"lb{self.lookback}")
        if self.n_samples != 30:
            extras.append(f"n{self.n_samples}")
        if self.temperature != 1.0:
            extras.append(f"T{self.temperature}")
        if self.top_p != 0.9:
            extras.append(f"p{self.top_p}")

        if extras:
            return f"Kronos-base ({self.pred_len}, {'/'.join(extras)})"
        return f"Kronos-base ({self.pred_len})"

    def calc(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        df = df.rename(columns={df.columns[0]: "timestamps"})
        df = df.tail(self.lookback).reset_index(drop=True)

        x_df = df[["open", "high", "low", "close", "volume"]]
        x_timestamp = df["timestamps"]
        y_timestamp = pd.Series(pd.bdate_range(x_timestamp.iloc[-1], periods=self.pred_len + 1)[1:])

        paths = []
        for i in range(self.n_samples):
            pred_df = self.predictor.predict(
                df=x_df,
                x_timestamp=x_timestamp,
                y_timestamp=y_timestamp,
                pred_len=self.pred_len,
                T=self.temperature,
                top_p=self.top_p,
                sample_count=1,
                verbose=False,
            )
            paths.append(pred_df["close"].to_numpy())

        paths = np.stack(paths)
        median = np.quantile(paths, 0.5, axis=0)
        lower = np.quantile(paths, 0.1, axis=0)
        upper = np.quantile(paths, 0.9, axis=0)

        return pd.DataFrame(
            {
                "median": median,
                "lower": lower,
                "upper": upper,
            },
            index=pd.DatetimeIndex(y_timestamp),
        )
