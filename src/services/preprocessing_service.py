"""
Preprocessing and Windowing Service for LSTM Autoencoder

Handles data cleaning, scaling, encoding, and window generation for telemetry data.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple

from sklearn.preprocessing import RobustScaler, OneHotEncoder
from numpy.lib.stride_tricks import sliding_window_view


def _rolling_mean_1d(arr: np.ndarray, win: int) -> np.ndarray:
    """Rolling mean for 1D numeric array."""
    arr = np.asarray(arr, dtype=np.float64)
    c = np.empty(len(arr) + 1, dtype=np.float64)
    c[0] = 0.0
    np.cumsum(arr, out=c[1:])
    return (c[win:] - c[:-win]) / win


def _ensure_window_axis_order(x: np.ndarray, win: int) -> np.ndarray:
    """
    Normalize sliding_window_view output to (n_windows, win, n_features).
    """
    if x.ndim != 3:
        raise ValueError(f"Expected 3D array, got shape {x.shape}")

    if x.shape[1] == win:
        return x
    if x.shape[2] == win:
        return np.swapaxes(x, 1, 2)

    raise ValueError(f"Could not identify window axis in shape {x.shape}")


def _fill_by_unit_fast(arr_2d: np.ndarray, fill_value: float) -> np.ndarray:
    """Fill missing values per unit/segment before windowing."""
    df = pd.DataFrame(arr_2d)
    return df.ffill().bfill().fillna(fill_value).to_numpy()


@dataclass
class WindowingConfig:
    """Configuration for windowing and preprocessing."""
    unit_col: str = "Unit"
    time_col: str = "Fecha"

    numeric_cols: Optional[List[str]] = None
    categorical_cols: Optional[List[str]] = None

    train_window_size: int = 60
    train_step_size: int = 1
    predict_window_size: int = 60

    min_numeric_coverage: float = 0.80
    min_row_coverage: float = 0.80
    max_created_fraction: Optional[float] = None
    max_imputed_fraction: Optional[float] = None

    train_fill_value: float = 0.0
    predict_fill_value: float = -10.0

    output_dtype: str = "float32"


class LSTMAutoencoderPreprocessor:
    """
    Preprocessor for LSTM autoencoder:
    - X = [numeric_scaled + categorical_encoded]
    - y = numeric_scaled only

    Supports:
    - fit() on train data
    - transform_rows()
    - make_train_windows() -> sliding windows
    - make_predict_windows() -> 1-hour windows per unit
    """

    def __init__(self, config: WindowingConfig):
        self.config = config
        self.numeric_scaler = None
        self.ohe = None
        self.input_feature_names_: Optional[List[str]] = None
        self.target_feature_names_: Optional[List[str]] = None
        self.numeric_fill_values_: Optional[Dict[str, float]] = None
        self.is_fitted_: bool = False

    def fit(self, df: pd.DataFrame) -> "LSTMAutoencoderPreprocessor":
        """Fit the preprocessor on training data."""
        df = self._validate_and_prepare_input(df)

        numeric_cols = self.config.numeric_cols or []
        categorical_cols = self.config.categorical_cols or []

        self.numeric_fill_values_ = {
            col: df[col].median(skipna=True) if col in df.columns else 0.0
            for col in numeric_cols
        }

        # Fit numeric scaler
        self.numeric_scaler = RobustScaler()
        if numeric_cols:
            num_fit = df[numeric_cols].copy()
            for col in numeric_cols:
                num_fit[col] = num_fit[col].fillna(self.numeric_fill_values_[col])
            self.numeric_scaler.fit(num_fit)

        # Fit OHE
        self.ohe = OneHotEncoder(
            handle_unknown="ignore",
            drop="first",
            sparse_output=False
        )
        if categorical_cols:
            cat_fit = df[categorical_cols].copy().astype("string").fillna("__missing__")
            self.ohe.fit(cat_fit)

        self.target_feature_names_ = list(numeric_cols)
        self.input_feature_names_ = self._build_input_feature_names()

        self.is_fitted_ = True
        return self

    def transform_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform input rows."""
        self._check_is_fitted()
        df = self._validate_and_prepare_input(df)

        base_cols = [self.config.unit_col, self.config.time_col]
        extra_cols = [
            c for c in ["created_by_reindex", "imputed_any", "n_imputed_signals"]
            if c in df.columns
        ]

        num_df = self._transform_numeric(df)
        cat_df = self._transform_categorical(df)

        out_parts = [df[base_cols + extra_cols].reset_index(drop=True)]
        if not num_df.empty:
            out_parts.append(num_df.reset_index(drop=True))
        if not cat_df.empty:
            out_parts.append(cat_df.reset_index(drop=True))

        out = pd.concat(out_parts, axis=1, copy=False)
        return out

    def fit_transform_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fit and transform."""
        self.fit(df)
        return self.transform_rows(df)

    def make_train_windows(
        self,
        raw_df: pd.DataFrame,
        transformed_df: pd.DataFrame,
        return_metadata: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, Optional[pd.DataFrame]]:
        """Create sliding training windows."""
        self._check_is_fitted()

        raw_df = self._validate_and_prepare_input(raw_df)
        transformed_df = transformed_df.copy()

        unit_col = self.config.unit_col
        time_col = self.config.time_col
        win = self.config.train_window_size
        step = self.config.train_step_size

        input_cols = self.input_feature_names_
        target_cols = self.target_feature_names_
        numeric_cols = self.config.numeric_cols or []

        raw_df = raw_df.sort_values([unit_col, time_col]).reset_index(drop=True)
        transformed_df = transformed_df.sort_values([unit_col, time_col]).reset_index(drop=True)

        if len(raw_df) != len(transformed_df):
            raise ValueError("raw_df and transformed_df have different number of rows.")

        if not raw_df[[unit_col, time_col]].equals(transformed_df[[unit_col, time_col]]):
            raise ValueError("raw_df and transformed_df row alignment mismatch.")

        unit_arr = raw_df[unit_col].to_numpy()
        time_arr = raw_df[time_col].to_numpy()

        raw_num = raw_df[numeric_cols].to_numpy(dtype=np.float32, copy=False) if numeric_cols else np.empty((len(raw_df), 0), dtype=np.float32)
        X_all = transformed_df[input_cols].to_numpy(dtype=np.float32, copy=True)
        y_all = transformed_df[target_cols].to_numpy(dtype=np.float32, copy=True)

        created_arr = raw_df["created_by_reindex"].to_numpy(dtype=np.float32, copy=False) if "created_by_reindex" in raw_df.columns else None
        imputed_arr = raw_df["imputed_any"].to_numpy(dtype=np.float32, copy=False) if "imputed_any" in raw_df.columns else None

        change = np.r_[True, unit_arr[1:] != unit_arr[:-1]]
        starts = np.flatnonzero(change)
        ends = np.r_[starts[1:], len(unit_arr)]

        X_seq = []
        y_seq = []
        meta_rows = []

        n_signals = len(numeric_cols)

        for s, e in zip(starts, ends):
            unit = unit_arr[s]
            n = e - s
            if n < win:
                continue

            raw_num_u = raw_num[s:e]
            X_u = X_all[s:e]
            y_u = y_all[s:e]
            time_u = time_arr[s:e]

            X_u_filled = _fill_by_unit_fast(X_u, fill_value=self.config.train_fill_value)
            y_u_filled = _fill_by_unit_fast(y_u, fill_value=self.config.train_fill_value)

            X_view = sliding_window_view(X_u_filled, window_shape=win, axis=0)
            y_view = sliding_window_view(y_u_filled, window_shape=win, axis=0)
            X_view = _ensure_window_axis_order(X_view, win)
            y_view = _ensure_window_axis_order(y_view, win)

            if n_signals > 0:
                observed = ~np.isnan(raw_num_u)
                observed_count_per_row = observed.sum(axis=1).astype(np.float32)
                row_has_any = observed.any(axis=1).astype(np.float32)

                numeric_coverage = _rolling_mean_1d(observed_count_per_row, win) / n_signals
                row_coverage = _rolling_mean_1d(row_has_any, win)
            else:
                numeric_coverage = np.ones(n - win + 1, dtype=np.float32)
                row_coverage = np.ones(n - win + 1, dtype=np.float32)

            valid = (
                (numeric_coverage >= self.config.min_numeric_coverage) &
                (row_coverage >= self.config.min_row_coverage)
            )

            created_fraction = None
            if created_arr is not None:
                created_fraction = _rolling_mean_1d(created_arr[s:e], win)
                if self.config.max_created_fraction is not None:
                    valid &= (created_fraction <= self.config.max_created_fraction)

            imputed_fraction = None
            if imputed_arr is not None:
                imputed_fraction = _rolling_mean_1d(imputed_arr[s:e], win)
                if self.config.max_imputed_fraction is not None:
                    valid &= (imputed_fraction <= self.config.max_imputed_fraction)

            idx = np.arange(0, n - win + 1, step)
            valid_idx = idx[valid[idx]]

            if len(valid_idx) == 0:
                continue

            X_sel = X_view[valid_idx]
            y_sel = y_view[valid_idx]

            finite_mask = np.isfinite(X_sel).all(axis=(1, 2)) & np.isfinite(y_sel).all(axis=(1, 2))
            if not finite_mask.all():
                X_sel = X_sel[finite_mask]
                y_sel = y_sel[finite_mask]
                valid_idx = valid_idx[finite_mask]

            if len(valid_idx) == 0:
                continue

            X_seq.append(X_sel.astype(self.config.output_dtype, copy=False))
            y_seq.append(y_sel.astype(self.config.output_dtype, copy=False))

            if return_metadata:
                for start_idx in valid_idx:
                    row = {
                        "Unit": unit,
                        "window_type": "train_sliding",
                        "start_idx": int(start_idx),
                        "end_idx_exclusive": int(start_idx + win),
                        "start_time": time_u[start_idx],
                        "end_time": time_u[start_idx + win - 1],
                        "numeric_coverage": float(numeric_coverage[start_idx]),
                        "row_coverage": float(row_coverage[start_idx]),
                    }
                    if created_fraction is not None:
                        row["created_fraction"] = float(created_fraction[start_idx])
                    if imputed_fraction is not None:
                        row["imputed_fraction"] = float(imputed_fraction[start_idx])
                    meta_rows.append(row)

        X = np.concatenate(X_seq, axis=0).astype(self.config.output_dtype) if X_seq else np.empty(
            (0, win, len(input_cols)), dtype=self.config.output_dtype
        )

        y = np.concatenate(y_seq, axis=0).astype(self.config.output_dtype) if y_seq else np.empty(
            (0, win, len(target_cols)), dtype=self.config.output_dtype
        )

        meta = pd.DataFrame(meta_rows) if return_metadata else None
        return X, y, meta

    def make_predict_windows(
        self,
        raw_df: pd.DataFrame,
        transformed_df: pd.DataFrame,
        return_metadata: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, Optional[pd.DataFrame]]:
        """Create prediction windows (1-hour blocks)."""
        self._check_is_fitted()

        raw_df = self._validate_and_prepare_input(raw_df)
        transformed_df = transformed_df.copy()

        unit_col = self.config.unit_col
        time_col = self.config.time_col
        win = self.config.predict_window_size

        input_cols = self.input_feature_names_
        target_cols = self.target_feature_names_

        raw_df = raw_df.sort_values([unit_col, time_col]).reset_index(drop=True)
        transformed_df = transformed_df.sort_values([unit_col, time_col]).reset_index(drop=True)

        if len(raw_df) != len(transformed_df):
            raise ValueError("raw_df and transformed_df have different number of rows.")

        if not raw_df[[unit_col, time_col]].equals(transformed_df[[unit_col, time_col]]):
            raise ValueError("raw_df and transformed_df row alignment mismatch.")

        unit_arr = raw_df[unit_col].to_numpy()
        time_arr = raw_df[time_col].to_numpy()

        X_all = transformed_df[input_cols].to_numpy(dtype=np.float32, copy=True)
        y_all = transformed_df[target_cols].to_numpy(dtype=np.float32, copy=True)

        created_arr = raw_df["created_by_reindex"].to_numpy(dtype=np.float32, copy=False) if "created_by_reindex" in raw_df.columns else None
        imputed_arr = raw_df["imputed_any"].to_numpy(dtype=np.float32, copy=False) if "imputed_any" in raw_df.columns else None

        change = np.r_[True, unit_arr[1:] != unit_arr[:-1]]
        starts = np.flatnonzero(change)
        ends = np.r_[starts[1:], len(unit_arr)]

        X_seq = []
        y_seq = []
        meta_rows = []

        for s, e in zip(starts, ends):
            unit = unit_arr[s]
            n = e - s
            if n < win:
                continue

            n_complete_windows = n // win
            usable = n_complete_windows * win
            if usable == 0:
                continue

            X_u = X_all[s:s + usable]
            y_u = y_all[s:s + usable]
            time_u = time_arr[s:s + usable]

            X_u_filled = _fill_by_unit_fast(X_u, fill_value=self.config.predict_fill_value)
            y_u_filled = _fill_by_unit_fast(y_u, fill_value=self.config.predict_fill_value)

            X_blocks = X_u_filled.reshape(n_complete_windows, win, -1)
            y_blocks = y_u_filled.reshape(n_complete_windows, win, -1)

            finite_mask = np.isfinite(X_blocks).all(axis=(1, 2)) & np.isfinite(y_blocks).all(axis=(1, 2))
            if not finite_mask.all():
                X_blocks = X_blocks[finite_mask]
                y_blocks = y_blocks[finite_mask]

            if len(X_blocks) == 0:
                continue

            X_seq.append(X_blocks.astype(self.config.output_dtype, copy=False))
            y_seq.append(y_blocks.astype(self.config.output_dtype, copy=False))

            if return_metadata:
                for hour_idx in range(n_complete_windows):
                    start_idx = hour_idx * win
                    end_idx = start_idx + win
                    row = {
                        "Unit": unit,
                        "window_type": "predict_hour_block",
                        "hour_idx": hour_idx,
                        "start_idx": start_idx,
                        "end_idx_exclusive": end_idx,
                        "start_time": time_u[start_idx],
                        "end_time": time_u[end_idx - 1],
                        "n_rows": win,
                    }
                    if created_arr is not None:
                        row["created_fraction"] = float(created_arr[s + start_idx:s + end_idx].mean())
                    else:
                        row["created_fraction"] = np.nan

                    if imputed_arr is not None:
                        row["imputed_fraction"] = float(imputed_arr[s + start_idx:s + end_idx].mean())
                    else:
                        row["imputed_fraction"] = np.nan

                    meta_rows.append(row)

        X = np.concatenate(X_seq, axis=0).astype(self.config.output_dtype) if X_seq else np.empty(
            (0, win, len(input_cols)), dtype=self.config.output_dtype
        )
        y = np.concatenate(y_seq, axis=0).astype(self.config.output_dtype) if y_seq else np.empty(
            (0, win, len(target_cols)), dtype=self.config.output_dtype
        )

        meta = pd.DataFrame(meta_rows) if return_metadata else None
        return X, y, meta

    def fit_transform_train(
        self,
        df_train: pd.DataFrame,
        return_metadata: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame, Optional[pd.DataFrame]]:
        """Fit on train -> transform rows -> create train windows."""
        tr_rows = self.fit_transform_rows(df_train)
        X, y, meta = self.make_train_windows(
            raw_df=df_train,
            transformed_df=tr_rows,
            return_metadata=return_metadata
        )
        return X, y, tr_rows, meta

    def transform_predict(
        self,
        df_test: pd.DataFrame,
        return_metadata: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame, Optional[pd.DataFrame]]:
        """Transform test -> create hourly predict windows."""
        tr_rows = self.transform_rows(df_test)
        X, y, meta = self.make_predict_windows(
            raw_df=df_test,
            transformed_df=tr_rows,
            return_metadata=return_metadata
        )

        print(f'Shape of predict windows: {X.shape}, {y.shape}')

        return X, y, tr_rows, meta

    def _validate_and_prepare_input(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and prepare input DataFrame."""
        df = df.copy()

        required_cols = [self.config.unit_col, self.config.time_col]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        if self.config.numeric_cols is None:
            raise ValueError("config.numeric_cols must be provided explicitly.")

        if self.config.categorical_cols is None:
            self.config.categorical_cols = []

        if not pd.api.types.is_datetime64_any_dtype(df[self.config.time_col]):
            df[self.config.time_col] = pd.to_datetime(df[self.config.time_col], errors="coerce")

        df = df.dropna(subset=[self.config.unit_col, self.config.time_col])
        df = df.sort_values([self.config.unit_col, self.config.time_col]).reset_index(drop=True)

        for col in self.config.numeric_cols:
            if col in df.columns and (
                df[col].dtype == "object" or pd.api.types.is_string_dtype(df[col])
            ):
                df[col] = pd.to_numeric(df[col], errors="coerce")

        for col in self.config.categorical_cols:
            if col in df.columns:
                df[col] = df[col].astype("string")

        return df

    def _transform_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform numeric columns."""
        numeric_cols = self.config.numeric_cols or []
        if not numeric_cols:
            return pd.DataFrame(index=df.index)

        num_df = df[numeric_cols].copy()
        nan_mask = num_df.isna()

        fill_values = self.numeric_fill_values_ or {c: 0.0 for c in numeric_cols}
        num_temp = num_df.copy()
        for c in numeric_cols:
            num_temp[c] = num_temp[c].fillna(fill_values.get(c, 0.0))

        scaled = pd.DataFrame(
            self.numeric_scaler.transform(num_temp),
            columns=numeric_cols,
            index=df.index
        )

        scaled[nan_mask] = np.nan
        return scaled

    def _transform_categorical(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform categorical columns."""
        categorical_cols = self.config.categorical_cols or []
        if not categorical_cols:
            return pd.DataFrame(index=df.index)

        cat_df = df[categorical_cols].copy().astype("string").fillna("__missing__")
        arr = self.ohe.transform(cat_df)
        cols = self.ohe.get_feature_names_out(categorical_cols).tolist()
        return pd.DataFrame(arr, columns=cols, index=df.index)

    def _build_input_feature_names(self) -> List[str]:
        """Build input feature names."""
        names = list(self.config.numeric_cols or [])
        if self.config.categorical_cols:
            names.extend(
                self.ohe.get_feature_names_out(self.config.categorical_cols).tolist()
            )
        return names

    def _check_is_fitted(self):
        """Check if preprocessor is fitted."""
        if not self.is_fitted_:
            raise RuntimeError("Preprocessor is not fitted yet. Call fit() first.")
