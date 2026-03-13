"""
Model builder module.

Single responsibility: construct the LSTM encoder-decoder architecture.
No training logic lives here.
"""

from typing import List, Tuple

import tensorflow as tf
from tensorflow.keras import Model, layers

from src.utils.logger import get_logger

logger = get_logger(__name__)


def build_lstm_autoencoder(
    n_features: int,
    sequence_length: int,
    encoder_units: List[int] = None,
    dropout_rate: float = 0.2,
    learning_rate: float = 1e-3,
) -> Tuple[Model, Model, Model]:
    """
    Build an LSTM encoder-decoder with a flexible number of layers.

    Parameters
    ----------
    n_features : int
        Number of input features per timestep.
    sequence_length : int
        Number of timesteps in each window (``WINDOW_SIZE``).
    encoder_units : list[int]
        Neuron counts for each encoder LSTM layer (decoder mirrors in reverse).
    dropout_rate : float
        Dropout applied after every LSTM layer.
    learning_rate : float
        Adam optimiser learning rate.

    Returns
    -------
    (autoencoder, encoder, decoder)
    """
    if encoder_units is None:
        encoder_units = [16, 8]

    # ── Encoder ──
    enc_in = layers.Input(shape=(sequence_length, n_features), name="enc_input")
    x = enc_in
    for i, units in enumerate(encoder_units):
        return_seq = i < len(encoder_units) - 1
        x = layers.LSTM(units, return_sequences=return_seq)(x)
        x = layers.Dropout(dropout_rate)(x)
    latent_dim = encoder_units[-1]
    encoder = Model(enc_in, x, name="encoder")

    # ── Decoder (mirror) ──
    dec_in = layers.Input(shape=(latent_dim,), name="dec_input")
    y = layers.RepeatVector(sequence_length)(dec_in)
    for units in reversed(encoder_units):
        y = layers.LSTM(units, return_sequences=True)(y)
        y = layers.Dropout(dropout_rate)(y)
    dec_out = layers.TimeDistributed(layers.Dense(n_features))(y)
    decoder = Model(dec_in, dec_out, name="decoder")

    # ── Autoencoder ──
    ae_in = layers.Input(shape=(sequence_length, n_features), name="ae_input")
    encoded = encoder(ae_in)
    decoded = decoder(encoded)
    autoencoder = Model(ae_in, decoded, name="autoencoder")
    autoencoder.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss="mse",
    )

    logger.info(
        f"Autoencoder built: layers={encoder_units}  "
        f"features={n_features}  seq_len={sequence_length}"
    )
    return autoencoder, encoder, decoder
