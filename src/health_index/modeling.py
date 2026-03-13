"""
Modeling Module

Defines LSTM autoencoder architecture for learning normal equipment behavior.
"""

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from typing import Tuple


def build_lstm_autoencoder(
    window_size: int,
    n_features: int,
    lstm_units_1: int = 16,
    lstm_units_2: int = 8,
    dropout_rate: float = 0.2,
    learning_rate: float = 0.001,
) -> keras.Model:
    """
    Build LSTM autoencoder model for anomaly detection.
    
    Architecture:
        Encoder:
            LSTM(lstm_units_1, return_sequences=True)
            Dropout
            LSTM(lstm_units_2, return_sequences=False)
            Dropout
        
        Decoder:
            RepeatVector(window_size)
            LSTM(lstm_units_2, return_sequences=True)
            Dropout
            LSTM(lstm_units_1, return_sequences=True)
            Dropout
            TimeDistributed(Dense(n_features))
    
    Args:
        window_size: Number of timesteps in input sequence
        n_features: Number of features
        lstm_units_1: Units in first LSTM layer
        lstm_units_2: Units in second LSTM layer
        dropout_rate: Dropout rate
        learning_rate: Learning rate for Adam optimizer
    
    Returns:
        Compiled Keras model
    """
    # Input
    inputs = keras.Input(shape=(window_size, n_features))
    
    # Encoder
    x = layers.LSTM(lstm_units_1, return_sequences=True)(inputs)
    x = layers.Dropout(dropout_rate)(x)
    encoded = layers.LSTM(lstm_units_2, return_sequences=False)(x)
    encoded = layers.Dropout(dropout_rate)(encoded)
    
    # Decoder
    x = layers.RepeatVector(window_size)(encoded)
    x = layers.LSTM(lstm_units_2, return_sequences=True)(x)
    x = layers.Dropout(dropout_rate)(x)
    x = layers.LSTM(lstm_units_1, return_sequences=True)(x)
    x = layers.Dropout(dropout_rate)(x)
    outputs = layers.TimeDistributed(layers.Dense(n_features))(x)
    
    # Model
    model = keras.Model(inputs=inputs, outputs=outputs, name="LSTM_Autoencoder")
    
    # Compile
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss='mse',
        metrics=['mae']
    )
    
    return model


def get_model_summary(model: keras.Model) -> str:
    """Get model summary as string."""
    summary_lines = []
    model.summary(print_fn=lambda x: summary_lines.append(x))
    return '\n'.join(summary_lines)


def count_parameters(model: keras.Model) -> Tuple[int, int]:
    """
    Count trainable and non-trainable parameters.
    
    Returns:
        Tuple of (trainable_params, non_trainable_params)
    """
    trainable = sum([tf.size(w).numpy() for w in model.trainable_weights])
    non_trainable = sum([tf.size(w).numpy() for w in model.non_trainable_weights])
    return trainable, non_trainable
