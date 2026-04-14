"""
Model Service for LSTM Autoencoder

Handles model building, training, inference, and persistence.
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
import tensorflow as tf

from dataclasses import dataclass, asdict
from typing import Tuple, Optional, Dict, Any
from tensorflow.keras import Model, layers


@dataclass
class LSTMAEModelConfig:
    """Configuration for LSTM autoencoder model."""
    latent_dim: int = 8
    encoder_lstm_1: int = 32
    encoder_lstm_2: int = 16
    decoder_lstm_1: int = 16
    decoder_lstm_2: int = 32

    dropout_rate: float = 0.2
    learning_rate: float = 1e-3

    batch_size: int = 32
    epochs: int = 50
    validation_split: float = 0.2
    early_stopping_patience: int = 5

    loss: str = "mse"
    metrics: tuple = ()


class LSTMAutoencoderService:
    """
    End-to-end service for:
    - building the model
    - training
    - saving/loading artifacts
    - running prediction
    - computing reconstruction error
    """

    def __init__(
        self,
        preprocessor,
        model_config: LSTMAEModelConfig,
        model: Optional[tf.keras.Model] = None
    ):
        self.preprocessor = preprocessor
        self.model_config = model_config
        self.model = model
        self.history_ = None

    def build_model(self) -> tf.keras.Model:
        """
        Build seq2seq LSTM autoencoder:
        X: (window, input_features)
        y: (window, numeric_features)
        """
        if not self.preprocessor.is_fitted_:
            raise RuntimeError("Preprocessor must be fitted before building the model.")

        seq_len = self.preprocessor.config.train_window_size
        n_input_features = len(self.preprocessor.input_feature_names_)
        n_output_features = len(self.preprocessor.target_feature_names_)

        cfg = self.model_config

        encoder_inputs = layers.Input(
            shape=(seq_len, n_input_features),
            name="encoder_inputs"
        )

        x = layers.Masking(mask_value=self.preprocessor.config.predict_fill_value)(encoder_inputs)
        x = layers.LSTM(cfg.encoder_lstm_1, return_sequences=True, name="enc_lstm_1")(x)
        x = layers.Dropout(cfg.dropout_rate, name="enc_dropout_1")(x)
        x = layers.LSTM(cfg.encoder_lstm_2, return_sequences=False, name="enc_lstm_2")(x)
        x = layers.Dropout(cfg.dropout_rate, name="enc_dropout_2")(x)

        latent = layers.Dense(cfg.latent_dim, activation="linear", name="latent_vector")(x)

        x = layers.RepeatVector(seq_len, name="repeat_vector")(latent)
        x = layers.LSTM(cfg.decoder_lstm_1, return_sequences=True, name="dec_lstm_1")(x)
        x = layers.Dropout(cfg.dropout_rate, name="dec_dropout_1")(x)
        x = layers.LSTM(cfg.decoder_lstm_2, return_sequences=True, name="dec_lstm_2")(x)

        decoder_outputs = layers.TimeDistributed(
            layers.Dense(n_output_features),
            name="reconstructed_numeric"
        )(x)

        model = Model(encoder_inputs, decoder_outputs, name="lstm_autoencoder")

        optimizer = tf.keras.optimizers.Adam(learning_rate=cfg.learning_rate)
        model.compile(
            optimizer=optimizer,
            loss=cfg.loss,
            metrics=list(cfg.metrics)
        )

        self.model = model
        return model

    def fit(
        self,
        df_train: pd.DataFrame,
        verbose: int = 1
    ) -> Dict[str, Any]:
        """
        Fit preprocessor + create train windows + train model.
        """
        X_train, y_train, transformed_rows, train_meta = self.preprocessor.fit_transform_train(
            df_train,
            return_metadata=True
        )

        if X_train.shape[0] == 0:
            raise ValueError("No valid training windows were generated.")

        if self.model is None:
            self.build_model()

        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                patience=self.model_config.early_stopping_patience,
                restore_best_weights=True,
                monitor="val_loss"
            )
        ]

        history = self.model.fit(
            X_train,
            y_train,
            epochs=self.model_config.epochs,
            batch_size=self.model_config.batch_size,
            validation_split=self.model_config.validation_split,
            callbacks=callbacks,
            verbose=verbose,
            shuffle=True
        )

        self.history_ = history.history

        return {
            "X_train_shape": X_train.shape,
            "y_train_shape": y_train.shape,
            "n_train_windows": int(X_train.shape[0]),
            "history": self.history_,
            "train_meta": train_meta,
            "transformed_rows": transformed_rows,
        }

    def predict_windows(
        self,
        df_test: pd.DataFrame,
        return_reconstruction: bool = True,
    ) -> Dict[str, Any]:
        """
        Create predict windows (1 hour blocks), reconstruct numeric outputs,
        and compute reconstruction error.
        """
        if self.model is None:
            raise RuntimeError("Model is not loaded/built.")

        X_pred, y_true, transformed_rows, pred_meta = self.preprocessor.transform_predict(
            df_test,
            return_metadata=True
        )

        if X_pred.shape[0] == 0:
            return {
                "X_pred": X_pred,
                "y_true": y_true,
                "y_pred": np.empty_like(y_true),
                "pred_meta": pred_meta,
                "window_errors": pd.DataFrame(),
                "signal_errors": pd.DataFrame(),
                "transformed_rows": transformed_rows,
            }

        y_pred = self.model.predict(X_pred, verbose=0)

        window_errors_df, signal_errors_df = self._compute_reconstruction_errors(
            y_true=y_true,
            y_pred=y_pred,
            pred_meta=pred_meta
        )

        result = {
            "X_pred": X_pred,
            "y_true": y_true,
            "y_pred": y_pred,
            "pred_meta": pred_meta,
            "window_errors": window_errors_df,
            "signal_errors": signal_errors_df,
            "transformed_rows": transformed_rows,
        }

        if not return_reconstruction:
            result.pop("X_pred", None)
            result.pop("y_true", None)
            result.pop("y_pred", None)

        return result

    def _compute_reconstruction_errors(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        pred_meta: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Compute:
        - per-window overall errors
        - per-window per-signal errors
        """
        signal_names = self.preprocessor.target_feature_names_

        abs_err = np.abs(y_true - y_pred)
        sq_err = np.square(y_true - y_pred)

        window_mae = abs_err.mean(axis=(1, 2))
        window_mse = sq_err.mean(axis=(1, 2))
        window_rmse = np.sqrt(window_mse)

        window_errors_df = pred_meta.copy()
        window_errors_df["window_mae"] = window_mae
        window_errors_df["window_mse"] = window_mse
        window_errors_df["window_rmse"] = window_rmse

        signal_mae = abs_err.mean(axis=1)
        signal_mse = sq_err.mean(axis=1)
        signal_rmse = np.sqrt(signal_mse)

        signal_error_rows = []
        for i in range(len(pred_meta)):
            base = pred_meta.iloc[i].to_dict()
            for j, sig in enumerate(signal_names):
                signal_error_rows.append({
                    **base,
                    "signal": sig,
                    "signal_mae": float(signal_mae[i, j]),
                    "signal_mse": float(signal_mse[i, j]),
                    "signal_rmse": float(signal_rmse[i, j]),
                })

        signal_errors_df = pd.DataFrame(signal_error_rows)

        return window_errors_df, signal_errors_df

    def save(self, artifact_dir: str) -> None:
        """
        Save:
        - keras model
        - preprocessor object
        - model config
        - schema metadata
        """
        if self.model is None:
            raise RuntimeError("No model available to save.")

        os.makedirs(artifact_dir, exist_ok=True)

        model_path = os.path.join(artifact_dir, "model.keras")
        self.model.save(model_path)

        preprocessor_path = os.path.join(artifact_dir, "preprocessor.joblib")
        joblib.dump(self.preprocessor, preprocessor_path)

        config_path = os.path.join(artifact_dir, "model_config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.model_config), f, indent=2)

        metadata = {
            "input_feature_names": self.preprocessor.input_feature_names_,
            "target_feature_names": self.preprocessor.target_feature_names_,
            "train_window_size": self.preprocessor.config.train_window_size,
            "predict_window_size": self.preprocessor.config.predict_window_size,
        }
        metadata_path = os.path.join(artifact_dir, "metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    @classmethod
    def load(cls, artifact_dir: str) -> "LSTMAutoencoderService":
        """Load saved service artifacts."""
        model_path = os.path.join(artifact_dir, "model.keras")
        preprocessor_path = os.path.join(artifact_dir, "preprocessor.joblib")
        config_path = os.path.join(artifact_dir, "model_config.json")

        model = tf.keras.models.load_model(model_path)
        preprocessor = joblib.load(preprocessor_path)

        with open(config_path, "r", encoding="utf-8") as f:
            cfg_dict = json.load(f)

        service = cls(
            preprocessor=preprocessor,
            model_config=LSTMAEModelConfig(**cfg_dict),
            model=model
        )
        return service
