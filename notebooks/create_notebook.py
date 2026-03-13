"""
Script to generate the health_index_improved.ipynb notebook.
Each cell is defined as a dict with 'cell_type' and 'source'.
Run this script to create/overwrite the notebook file.
"""
import json
import os

# ── Notebook cell definitions ────────────────────────────────────────────────

cells = []

def md(source: str):
    cells.append({"cell_type": "markdown", "source": source})

def code(source: str):
    cells.append({"cell_type": "code", "source": source})


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 – Imports & Configuration
# ═══════════════════════════════════════════════════════════════════════════════
md("# Health Index – Improved Pipeline\n"
   "End-to-end notebook: load → clean → impute → train (with Optuna) → predict → health index.\n\n"
   "**Key improvements over v1:**\n"
   "1. Categorical column imputation (forward-fill)\n"
   "2. OneHotEncoded categorical features fed into the autoencoder\n"
   "3. Prediction / inference function\n"
   "4. Health-index computation (reconstruction error + coverage)\n"
   "5. Optuna hyper-parameter optimisation (stored as JSON)")

md("## 1 · Imports & constants")

code("""\
import os
import json
import pathlib
import warnings
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm.auto import tqdm

import tensorflow as tf
from tensorflow.keras import layers, Model, mixed_precision
from sklearn.preprocessing import RobustScaler, OneHotEncoder

import optuna

warnings.filterwarnings("ignore", category=FutureWarning)
""")

code("""\
# ── Reproducibility seed ────────────────────────────────────────────
SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

# ── Paths (relative to notebooks/) ──────────────────────────────────
ROOT = pathlib.Path("..").resolve()
DATA_SILVER = ROOT / "data" / "telemetry" / "silver"
DATA_GOLDEN = ROOT / "data" / "telemetry" / "golden"
MODELS_DIR  = ROOT / "models"
MAPPING_PATH = ROOT / "data" / "telemetry" / "component_signals_mapping.json"

# ── Pipeline constants ──────────────────────────────────────────────
CLIENT      = "cda"
UNIT_COL    = "Unit"
TIME_COL    = "Fecha"
CAT_COLS    = ["EstadoMaquina", "EstadoCarga"]

FREQ             = "1min"
GAP_THRESHOLD    = pd.Timedelta("10min")
MIN_DURATION     = pd.Timedelta("4h")
MIN_COVERAGE     = 0.75
INTERP_LIMIT     = 10

WINDOW_SIZE      = 60          # 1 hour at 1-min frequency
IMPUTE_FILL_VAL  = -10.0       # fill value for missing data after scaling
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 – GPU Setup
# ═══════════════════════════════════════════════════════════════════════════════
md("## 2 · GPU configuration")

code("""\
def configure_gpu() -> None:
    \"\"\"Enable memory-growth and mixed-precision if a GPU is available.\"\"\"
    print(f"TensorFlow {tf.__version__}")
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        policy = mixed_precision.Policy("mixed_float16")
        mixed_precision.set_global_policy(policy)
        print(f"  GPU(s): {len(gpus)}  |  mixed-precision: {policy.name}")
    else:
        print("  No GPU detected – using CPU")

configure_gpu()
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 – Data Loading
# ═══════════════════════════════════════════════════════════════════════════════
md("## 3 · Data loading")

code("""\
def load_parquet_folder(folder: pathlib.Path) -> pd.DataFrame:
    \"\"\"Read every `.parquet` file inside *folder* and return a single DataFrame.\"\"\"
    files = sorted(folder.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files in {folder}")
    df = pd.concat([pd.read_parquet(f) for f in tqdm(files, desc="Loading")], ignore_index=True)
    df.sort_values([UNIT_COL, TIME_COL], inplace=True)
    df.drop_duplicates(subset=[UNIT_COL, TIME_COL], keep="first", inplace=True)
    df.reset_index(drop=True, inplace=True)
    print(f"Loaded {len(df)/1e6:.3f}M rows  |  {df[UNIT_COL].nunique()} units")
    return df

def load_component_mapping(path: pathlib.Path) -> dict:
    \"\"\"Load the component → signals JSON mapping.\"\"\"
    with open(path, "r") as f:
        return json.load(f)
""")

code("""\
input_folder = DATA_SILVER / CLIENT / "Telemetry_Wide_With_States"
df_raw = load_parquet_folder(input_folder)
component_mapping = load_component_mapping(MAPPING_PATH)
df_raw.head()
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 – Data Cleaning
# ═══════════════════════════════════════════════════════════════════════════════
md("## 4 · Data cleaning (outlier removal)")

code("""\
MARGINS: Dict[str, Tuple[float, float]] = {
    # General / GPS
    "GPSLat"       : (-30.4, -30.1),
    "GPSLon"       : (-71.3, -70.9),
    "GPSElevation" : (400, 2000),
    "GroundSpd"    : (0, 80),
    "EngSpd"       : (0, 2500),
    # Engine
    "EngCoolTemp"  : (30, 120),
    "RAftrclrTemp" : (10, 100),
    "EngOilPres"   : (150, 700),
    "CnkcasePres"  : (-1.5, 1.5),
    "RtLtExhTemp"  : (-10, 10),
    "RtExhTemp"    : (150, 750),
    "LtExhTemp"    : (150, 750),
    # Transmission
    "DiffLubePres" : (0, 800),
    "DiffTemp"     : (0, 150),
    "TrnLubeTemp"  : (-5, 120),
    "TCOutTemp"    : (30, 180),
    # Brakes
    "RtRBrkTemp"   : (20, 200),
    "RtFBrkTemp"   : (20, 200),
    "LtRBrkTemp"   : (20, 200),
    "LtFBrkTemp"   : (20, 200),
    # Steering
    "StrgOilTemp"  : (-10, 150),
}

def clean_outliers(df_in: pd.DataFrame, margins: Dict[str, Tuple[float, float]]) -> pd.DataFrame:
    \"\"\"Replace values outside *margins* with NaN.\"\"\"
    df = df_in.copy()
    for col, (lo, hi) in margins.items():
        if col in df.columns:
            df[col] = df[col].where((df[col] >= lo) & (df[col] <= hi), other=pd.NA)
    return df

def drop_sparse_rows(df: pd.DataFrame, num_cols: List[str], min_present_ratio: float = 0.5) -> pd.DataFrame:
    \"\"\"Drop rows where fewer than *min_present_ratio* of numerical signals are present.\"\"\"
    thresh = int(len(num_cols) * min_present_ratio)
    df = df.dropna(subset=num_cols, thresh=thresh)
    df.reset_index(drop=True, inplace=True)
    return df
""")

code("""\
num_cols = [c for c in MARGINS if c in df_raw.columns]
df_clean = clean_outliers(df_raw, MARGINS)
df_clean = drop_sparse_rows(df_clean, num_cols)
# Remove columns not present in mapping
df_clean.drop(columns=[c for c in ["Payload", "EngOilFltr", "AirFltr"] if c in df_clean.columns],
              inplace=True, errors="ignore")
print(f"After cleaning: {len(df_clean)/1e6:.3f}M rows")
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 – Cycle Detection & Imputation
# ═══════════════════════════════════════════════════════════════════════════════
md("## 5 · Cycle detection, numerical interpolation & categorical imputation")

code("""\
def assign_cycles(df: pd.DataFrame) -> pd.DataFrame:
    \"\"\"Assign a *cycle_id* per unit based on temporal gaps > GAP_THRESHOLD.\"\"\"
    df = df.copy()
    dt = df.groupby(UNIT_COL)[TIME_COL].diff()
    new_cycle = dt.isna() | (dt > GAP_THRESHOLD)
    df["cycle_id"] = new_cycle.groupby(df[UNIT_COL]).cumsum().astype("int64")
    return df

def is_valid_cycle(cycle_df: pd.DataFrame) -> bool:
    \"\"\"Return True if cycle duration >= MIN_DURATION and sample coverage >= MIN_COVERAGE.\"\"\"
    duration = cycle_df[TIME_COL].iloc[-1] - cycle_df[TIME_COL].iloc[0]
    freq_td = pd.to_timedelta(FREQ)
    expected_n = int(round(duration / freq_td)) + 1
    coverage = len(cycle_df) / expected_n if expected_n > 0 else 0.0
    return (duration >= MIN_DURATION) and (coverage >= MIN_COVERAGE)

def impute_cycle(cycle_df: pd.DataFrame, num_cols: List[str]) -> pd.DataFrame:
    \"\"\"Interpolate numerical columns (time-based) and forward-fill categoricals.\"\"\"
    out = cycle_df.copy()
    # ── Numerical interpolation ──
    out = out.set_index(TIME_COL)
    before_na = out[num_cols].isna()
    out[num_cols] = out[num_cols].interpolate(method="time", limit=INTERP_LIMIT, limit_area="inside")
    out["imputed_any"] = (before_na & ~out[num_cols].isna()).any(axis=1).astype("int8")
    out = out.reset_index()
    # ── Categorical forward-fill ──
    for col in CAT_COLS:
        if col in out.columns:
            out[col] = out[col].ffill()
    # Fill remaining NaN categoricals with defaults
    out.fillna({"EstadoMaquina": "ND", "EstadoCarga": "Sin Carga"}, inplace=True)
    return out

def process_cycles(df: pd.DataFrame, num_cols: List[str]) -> pd.DataFrame:
    \"\"\"Split into cycles, keep valid ones, impute, and concatenate.\"\"\"
    df = assign_cycles(df)
    cycles = []
    for (_, _), cdf in tqdm(df.groupby([UNIT_COL, "cycle_id"], sort=False), desc="Processing cycles"):
        if is_valid_cycle(cdf):
            cycles.append(impute_cycle(cdf, num_cols))
    if not cycles:
        raise ValueError("No valid cycles found – check GAP_THRESHOLD / MIN_DURATION settings")
    result = pd.concat(cycles, ignore_index=True)
    print(f"Valid cycles: {result[[UNIT_COL, 'cycle_id']].drop_duplicates().shape[0]}  |  "
          f"Rows: {len(result)/1e6:.3f}M")
    return result
""")

code("""\
df_processed = process_cycles(df_clean, num_cols)
df_processed.head()
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 – Labelling (percentile-based)
# ═══════════════════════════════════════════════════════════════════════════════
md("## 6 · Cycle labelling (Normal / Anomalous)")

code("""\
def label_cycles(df: pd.DataFrame, num_cols: List[str], anomaly_ratio: float = 2.0) -> pd.DataFrame:
    \"\"\"Label each (Unit, cycle_id) as Normal or Anomalous based on out-of-percentile ratio.\"\"\"
    signal_cols = [c for c in num_cols if ("GPS" not in c) and ("Spd" not in c)]
    percentiles = {c: df[c].quantile([0.05, 0.95]) for c in signal_cols}

    out_cols = []
    for col, pcts in percentiles.items():
        ocol = f"{col}_out_range"
        df[ocol] = ~df[col].between(pcts[0.05], pcts[0.95])
        out_cols.append(ocol)

    summary = df.groupby([UNIT_COL, "cycle_id"])[out_cols].sum()
    totals  = df.groupby([UNIT_COL, "cycle_id"]).size().rename("total_rows")
    summary["total_out_range"] = summary[out_cols].sum(axis=1)
    summary = summary.merge(totals, left_index=True, right_index=True)
    summary["total_ratio"] = summary["total_out_range"] / summary["total_rows"]
    summary["Label"] = np.where(summary["total_ratio"] < anomaly_ratio, "Normal", "Anomalous")

    df = df.merge(summary[["Label"]], left_on=[UNIT_COL, "cycle_id"], right_index=True)
    df.drop(columns=out_cols, inplace=True)
    return df
""")

code("""\
df_labelled = label_cycles(df_processed.copy(), num_cols)
print(df_labelled["Label"].value_counts())
df_labelled.head()
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 – Save processed data
# ═══════════════════════════════════════════════════════════════════════════════
md("## 7 · Store processed data")

code("""\
def save_processed_data(df: pd.DataFrame, client: str) -> pathlib.Path:
    \"\"\"Write processed data to silver layer as parquet.\"\"\"
    out_dir = DATA_SILVER / client
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "processed_data.parquet"
    df.to_parquet(path, index=False)
    print(f"Saved processed data → {path}  ({len(df)/1e6:.3f}M rows)")
    return path
""")

code("""\
save_processed_data(df_labelled, CLIENT)
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7b – Train / test split
# ═══════════════════════════════════════════════════════════════════════════════
md("## 7b · Train / test split (last 2 weeks for testing)")

code("""\
def split_train_test(
    df: pd.DataFrame,
    test_weeks: int = 2,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    \"\"\"Split by time: everything before the cutoff for training, the rest for testing.\"\"\"
    cutoff = df[TIME_COL].max() - pd.Timedelta(weeks=test_weeks)
    df_train = df[df[TIME_COL] < cutoff].copy()
    df_test  = df[df[TIME_COL] >= cutoff].copy()
    print(f"Train: {len(df_train):,} rows  ({df_train[TIME_COL].min()} → {df_train[TIME_COL].max()})")
    print(f"Test:  {len(df_test):,} rows  ({df_test[TIME_COL].min()} → {df_test[TIME_COL].max()})")
    return df_train, df_test
""")

code("""\
df_train, df_test = split_train_test(df_labelled, test_weeks=2)
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 – Sequence preparation (with OneHot categoricals)
# ═══════════════════════════════════════════════════════════════════════════════
md("## 8 · Sequence preparation (numerical + OneHot-encoded categoricals)")

code("""\
def fit_encoders(
    df: pd.DataFrame,
    num_cols: List[str],
    cat_cols: List[str],
) -> Tuple[Dict[str, RobustScaler], OneHotEncoder]:
    \"\"\"
    Fit one RobustScaler per unit (numerical cols) and one shared OneHotEncoder (categorical cols).
    Scalers are fitted on numpy arrays to avoid feature-name warnings at transform time.
    Returns (scalers_dict, ohe).
    \"\"\"
    scalers: Dict[str, RobustScaler] = {}
    for unit in df[UNIT_COL].unique():
        sc = RobustScaler()
        sc.fit(df.loc[df[UNIT_COL] == unit, num_cols].values)
        scalers[unit] = sc

    ohe = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    ohe.fit(df[cat_cols].values)
    return scalers, ohe

def build_sequences(
    df: pd.DataFrame,
    signal_cols: List[str],
    cat_cols: List[str],
    scalers: Dict[str, RobustScaler],
    ohe: OneHotEncoder,
    window_size: int,
    label_filter: Optional[str] = "Normal",
    hard_filling: bool = True,
) -> np.ndarray:
    \"\"\"
    Create sliding-window sequences [n_sequences, window_size, n_features].
    Numerical cols are scaled per-unit; categorical cols are one-hot encoded.
    If *label_filter* is given only rows with that label are used.
    If *hard_filling* is True, any remaining NaN values after scaling are filled with ffill() and bfill() within each cycle
    \"\"\"
    subset = df[df["Label"] == label_filter] if label_filter else df
    if hard_filling:
        subset = subset.sort_values([UNIT_COL, "cycle_id", TIME_COL])
        subset[signal_cols] = subset.groupby([UNIT_COL, "cycle_id"])[signal_cols].ffill().bfill()
    sequences = []
    for unit in subset[UNIT_COL].unique():
        unit_df = subset[subset[UNIT_COL] == unit]
        sc = scalers[unit]
        for cycle in unit_df["cycle_id"].unique():
            cdf = unit_df[unit_df["cycle_id"] == cycle]
            if len(cdf) < window_size * 2:
                continue
            num_scaled = sc.transform(cdf[signal_cols].values)
            cat_encoded = ohe.transform(cdf[cat_cols].values)
            combined = np.hstack([num_scaled, cat_encoded])
            for i in range(len(combined) - window_size):
                sequences.append(combined[i : i + window_size])
    return np.array(sequences, dtype="float32")
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 – Model builder
# ═══════════════════════════════════════════════════════════════════════════════
md("## 9 · LSTM autoencoder builder")

code("""\
def build_lstm_autoencoder(
    n_features: int,
    sequence_length: int,
    encoder_units: List[int] = [16, 8],
    dropout_rate: float = 0.2,
    learning_rate: float = 1e-3,
) -> Tuple[Model, Model, Model]:
    \"\"\"
    Build an LSTM encoder-decoder with a flexible number of layers.

    Args:
        encoder_units: list of neuron counts for each encoder LSTM layer
                       (decoder mirrors in reverse).  e.g. [32, 16, 8]
    Returns (autoencoder, encoder, decoder).
    \"\"\"
    # ── Encoder ──
    enc_in = layers.Input(shape=(sequence_length, n_features), name="enc_input")
    x = enc_in
    for i, units in enumerate(encoder_units):
        return_seq = (i < len(encoder_units) - 1)  # last layer returns single vector
        x = layers.LSTM(units, return_sequences=return_seq)(x)
        x = layers.Dropout(dropout_rate)(x)
    latent_dim = encoder_units[-1]
    encoder = Model(enc_in, x, name="encoder")

    # ── Decoder (mirror of encoder) ──
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
    return autoencoder, encoder, decoder
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 – Optuna optimisation
# ═══════════════════════════════════════════════════════════════════════════════
md("## 10 · Hyper-parameter optimisation (Optuna)")

code("""\
def _suggest_encoder_units(trial: optuna.Trial) -> List[int]:
    \"\"\"Suggest a variable-length list of descending LSTM layer sizes.\"\"\"
    n_layers = trial.suggest_int("n_layers", 1, 4)
    units = []
    prev = None
    for i in range(n_layers):
        hi = prev if prev else 128
        lo = max(4, hi // 4)
        u = trial.suggest_int(f"enc_units_L{i}", lo, hi, step=2)
        units.append(u)
        prev = u
    return units

def create_optuna_objective(
    X_train: np.ndarray,
    n_features: int,
    window_size: int,
):
    \"\"\"Return an Optuna objective closure for the autoencoder.\"\"\"

    def objective(trial: optuna.Trial) -> float:
        encoder_units = _suggest_encoder_units(trial)
        dropout_rate  = trial.suggest_float("dropout_rate", 0.05, 0.4, step=0.025)
        lr            = trial.suggest_float("learning_rate", 1e-5, 1e-2, log=True)
        batch_size    = trial.suggest_categorical("batch_size", [16, 32, 64])

        ae, _, _ = build_lstm_autoencoder(
            n_features=n_features,
            sequence_length=window_size,
            encoder_units=encoder_units,
            dropout_rate=dropout_rate,
            learning_rate=lr,
        )
        history = ae.fit(
            X_train, X_train,
            epochs=30,
            batch_size=batch_size,
            validation_split=0.2,
            callbacks=[tf.keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True)],
            verbose=0,
        )
        return min(history.history["val_loss"])

    return objective

def run_optuna_study(
    X_train: np.ndarray,
    n_features: int,
    window_size: int,
    component: str,
    client: str,
    n_trials: int = 20,
) -> dict:
    \"\"\"Run Optuna study in-memory and persist results as JSON. Returns best params.\"\"\"
    study_name = f"{component}_{window_size}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # In-memory study (avoids Windows file-lock privilege errors)
    study = optuna.create_study(
        study_name=study_name,
        direction="minimize",
    )
    study.optimize(
        create_optuna_objective(X_train, n_features, window_size),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    # ── Persist all trials + best params as plain JSON ──
    out_dir = MODELS_DIR / client / component
    out_dir.mkdir(parents=True, exist_ok=True)

    # Reconstruct encoder_units from best trial params
    bp = study.best_params
    n_layers = bp["n_layers"]
    encoder_units = [bp[f"enc_units_L{i}"] for i in range(n_layers)]

    best = {
        "encoder_units": encoder_units,
        "dropout_rate": bp["dropout_rate"],
        "learning_rate": bp["learning_rate"],
        "batch_size": bp["batch_size"],
        "best_val_loss": study.best_value,
        "study_name": study_name,
    }

    # Save best params
    summary_path = out_dir / f"best_params_{study_name}.json"
    with open(summary_path, "w") as f:
        json.dump(best, f, indent=2)

    # Save full trial history
    trials_data = []
    for t in study.trials:
        n_l = t.params.get("n_layers", 1)
        trials_data.append({
            "number": t.number,
            "value": t.value,
            "params": t.params,
            "encoder_units": [t.params.get(f"enc_units_L{i}") for i in range(n_l)],
            "state": t.state.name,
        })
    trials_path = out_dir / f"optuna_trials_{study_name}.json"
    with open(trials_path, "w") as f:
        json.dump(trials_data, f, indent=2)

    print(f"Best params → {summary_path}")
    print(f"All trials  → {trials_path}")
    return best
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 – Train component model
# ═══════════════════════════════════════════════════════════════════════════════
md("## 11 · Training loop (per component)")

code("""\
def save_model_artifacts(
    model: Model,
    scalers: Dict[str, RobustScaler],
    ohe: OneHotEncoder,
    best_params: dict,
    signal_cols: List[str],
    client: str,
    component: str,
) -> pathlib.Path:
    \"\"\"Persist model, scalers, encoder, and metadata.\"\"\"
    import pickle

    out_dir = MODELS_DIR / client / component
    out_dir.mkdir(parents=True, exist_ok=True)

    model.save(out_dir / "model.keras")
    with open(out_dir / "scalers.pkl", "wb") as f:
        pickle.dump(scalers, f)
    with open(out_dir / "ohe.pkl", "wb") as f:
        pickle.dump(ohe, f)
    metadata = {
        "signal_cols": signal_cols,
        "cat_cols": CAT_COLS,
        "window_size": WINDOW_SIZE,
        "best_params": best_params,
        "trained_at": datetime.now().isoformat(),
    }
    with open(out_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Artifacts saved → {out_dir}")
    return out_dir

def train_component_model(
    df: pd.DataFrame,
    component_mapping: dict,
    client: str,
    component: str,
    optimize: bool = True,
    n_trials: int = 20,
) -> Model:
    \"\"\"
    Full training pipeline for one component:
      1. Select signals
      2. Fit scalers & OHE
      3. Fill missing categoricals (forward-fill) and impute numerical (ffill and bfill)
      4. Build sequences
      5. (optional) Optuna optimisation
      6. Train final model with best params
      7. Save artifacts
    Returns the trained autoencoder.
    \"\"\"
    signal_cols = [c for c in component_mapping["components"][component]["signals"]
                   if c in df.columns]

    # ── Encoders ──
    scalers, ohe = fit_encoders(df, signal_cols, CAT_COLS)
    n_cat_features = len(ohe.get_feature_names_out())
    n_features = len(signal_cols) + n_cat_features

    # ── Sequences (Normal only) ──
    
    X_train = build_sequences(df, signal_cols, CAT_COLS, scalers, ohe,
                              window_size=WINDOW_SIZE, label_filter="Normal")
    print(f"[{component}]  sequences: {X_train.shape}  |  features: {n_features}")

    # ── Hyper-parameter search ──
    if optimize:
        best_params = run_optuna_study(
            X_train, n_features, WINDOW_SIZE, component, client, n_trials=n_trials,
        )
    else:
        best_params = {"encoder_units": [16, 8], "dropout_rate": 0.2, "learning_rate": 1e-3, "batch_size": 32}

    # ── Final training ──
    ae, encoder, decoder = build_lstm_autoencoder(
        n_features=n_features,
        sequence_length=WINDOW_SIZE,
        encoder_units=best_params["encoder_units"],
        dropout_rate=best_params["dropout_rate"],
        learning_rate=best_params["learning_rate"],
    )
    ae.fit(
        X_train, X_train,
        epochs=50,
        batch_size=best_params["batch_size"],
        validation_split=0.2,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)],
    )

    # ── Persist ──
    save_model_artifacts(ae, scalers, ohe, best_params, signal_cols, client, component)
    return ae
""")

code("""\
# Train all components (using df_train only)
trained_models = {}
for comp_name in component_mapping["components"]:
    print(f"\\n{'='*60}\\nTraining: {comp_name}\\n{'='*60}")
    trained_models[comp_name] = train_component_model(
        df_train, component_mapping, CLIENT, comp_name,
        optimize=True, n_trials=20,
    )
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12 – Prediction / Inference
# ═══════════════════════════════════════════════════════════════════════════════
md("## 12 · Prediction / inference (hour-by-hour)")

code("""\
import pickle

def load_model_artifacts(client: str, component: str) -> dict:
    \"\"\"Load model and all supporting artifacts from disk.\"\"\"
    base = MODELS_DIR / client / component
    model = tf.keras.models.load_model(base / "model.keras")
    with open(base / "scalers.pkl", "rb") as f:
        scalers = pickle.load(f)
    with open(base / "ohe.pkl", "rb") as f:
        ohe = pickle.load(f)
    with open(base / "metadata.json", "r") as f:
        metadata = json.load(f)
    return {"model": model, "scalers": scalers, "ohe": ohe, "metadata": metadata}

def prepare_inference_window(
    window_df: pd.DataFrame,
    signal_cols: List[str],
    cat_cols: List[str],
    scaler: RobustScaler,
    ohe: OneHotEncoder,
    window_size: int,
    num_fill: float = IMPUTE_FILL_VAL,
) -> Tuple[np.ndarray, float]:
    \"\"\"
    Prepare a single window (1 unit, up to *window_size* rows) for the model.

    Edge cases handled:
      - Empty window (0 rows):  all features filled with unlikely values.
      - Partial window (<window_size rows): existing rows are scaled/encoded
        normally; missing rows are padded (numerical → *num_fill*, OHE → 0).

    Returns:
        X        : np.ndarray of shape (1, window_size, n_features)
        coverage : fraction of rows present vs expected
    \"\"\"
    n_num = len(signal_cols)
    n_cat = len(ohe.get_feature_names_out())
    n_features = n_num + n_cat
    actual_len = len(window_df)
    coverage = actual_len / window_size

    # Build a single padding row: numerical → num_fill, OHE → 0
    pad_row = np.concatenate([
        np.full(n_num, num_fill, dtype="float32"),
        np.zeros(n_cat, dtype="float32"),
    ])

    if actual_len == 0:
        X = np.tile(pad_row, (window_size, 1))[np.newaxis, :, :]
        return X, 0.0

    # Scale existing numerical rows & encode existing categorical rows
    num_scaled  = scaler.transform(window_df[signal_cols].values)
    cat_encoded = ohe.transform(window_df[cat_cols].values)
    combined = np.hstack([num_scaled, cat_encoded]).astype("float32")

    # Pad if shorter than window_size
    if actual_len < window_size:
        pad = np.tile(pad_row, (window_size - actual_len, 1))
        combined = np.vstack([combined, pad])

    return combined[np.newaxis, :window_size, :], coverage

def predict_window(
    window_df: pd.DataFrame,
    model: Model,
    scaler: RobustScaler,
    ohe: OneHotEncoder,
    signal_cols: List[str],
    cat_cols: List[str],
    window_size: int = WINDOW_SIZE,
) -> dict:
    \"\"\"
    Run inference on a single window of data for 1 unit.

    Args:
        window_df: DataFrame with up to *window_size* rows for one unit.
    Returns:
        dict with reconstruction_error and coverage.
    \"\"\"
    X, coverage = prepare_inference_window(
        window_df, signal_cols, cat_cols, scaler, ohe, window_size,
    )
    X_pred = model.predict(X, verbose=0)
    mse = float(np.mean((X - X_pred) ** 2))
    return {"reconstruction_error": mse, "coverage": coverage}

def run_hourly_inference(
    df: pd.DataFrame,
    artifacts: dict,
    window_size: int = WINDOW_SIZE,
) -> pd.DataFrame:
    \"\"\"
    Inject data hour-by-hour and apply the model on each window.

    For every unit the test period is split into aligned 1-hour blocks
    (window_size rows at 1-min frequency).  Each block is fed to
    *predict_window* — even if it is empty or partially filled.

    Returns a DataFrame with one row per (unit, hour-window):
        Unit, window_start, window_end, reconstruction_error, coverage
    \"\"\"
    model       = artifacts["model"]
    scalers     = artifacts["scalers"]
    ohe         = artifacts["ohe"]
    meta        = artifacts["metadata"]
    signal_cols = meta["signal_cols"]
    cat_cols    = meta["cat_cols"]

    records = []
    for unit in tqdm(df[UNIT_COL].unique(), desc="Predicting"):
        scaler = scalers.get(unit)
        if scaler is None:
            continue
        udf = df[df[UNIT_COL] == unit].sort_values(TIME_COL)

        # Build aligned hourly boundaries over the full test range
        t_min = udf[TIME_COL].min().floor("h")
        t_max = udf[TIME_COL].max().ceil("h")
        hourly_starts = pd.date_range(t_min, t_max, freq="1h")

        for h_start in hourly_starts:
            h_end = h_start + pd.Timedelta(minutes=window_size)
            window_df = udf[(udf[TIME_COL] >= h_start) & (udf[TIME_COL] < h_end)]

            result = predict_window(
                window_df, model, scaler, ohe,
                signal_cols, cat_cols, window_size,
            )
            records.append({
                UNIT_COL: unit,
                "window_start": h_start,
                "window_end": h_end,
                **result,
            })

    result = pd.DataFrame(records)
    print(f"Inference windows: {len(result)}")
    return result
""")

code("""\
# Run hour-by-hour inference on the test set for each component
all_inferences = []
for comp_name in component_mapping["components"]:
    print(f"\\nInference: {comp_name}")
    arts = load_model_artifacts(CLIENT, comp_name)
    inf_df = run_hourly_inference(df_test, arts, window_size=WINDOW_SIZE)
    inf_df["component"] = comp_name
    all_inferences.append(inf_df)

inferences_df = pd.concat(all_inferences, ignore_index=True)
print(f"\\nTotal inference windows: {len(inferences_df)}")
inferences_df.head()
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 13 – Health Index Computation
# ═══════════════════════════════════════════════════════════════════════════════
md("## 13 · Health index computation")

code("""\
def compute_health_index(
    inferences_df: pd.DataFrame,
    error_col: str = "reconstruction_error",
    coverage_col: str = "coverage",
    error_quantile: float = 0.95,
) -> pd.DataFrame:
    \"\"\"
    Compute a health index per window.

    health_index = (1 - normalised_error) * coverage

    The error is normalised against the *error_quantile* of Normal-training errors
    so that 1.0 = perfectly normal and 0.0 = highly anomalous.
    \"\"\"
    df = inferences_df.copy()

    # Normalise error: clip at quantile ceiling, then scale to [0, 1]
    ceiling = df[error_col].quantile(error_quantile)
    df["error_norm"] = (df[error_col] / ceiling).clip(upper=1.0)
    df["health_index"] = (1.0 - df["error_norm"]) * df[coverage_col]
    df["health_index"] = df["health_index"].clip(0.0, 1.0)

    return df
""")

code("""\
health_df = compute_health_index(inferences_df)
health_df.describe()
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 14 – Save inference & health index
# ═══════════════════════════════════════════════════════════════════════════════
md("## 14 · Store inferences & health index")

code("""\
def save_golden_outputs(
    inferences_df: pd.DataFrame,
    health_df: pd.DataFrame,
    client: str,
) -> None:
    \"\"\"Write inference and health-index DataFrames to the golden layer.\"\"\"
    out_dir = DATA_GOLDEN / client
    out_dir.mkdir(parents=True, exist_ok=True)

    inf_path = out_dir / "inferences.parquet"
    inferences_df.to_parquet(inf_path, index=False)
    print(f"Inferences → {inf_path}  ({len(inferences_df)} rows)")

    hi_path = out_dir / "health_index.parquet"
    health_df.to_parquet(hi_path, index=False)
    print(f"Health index → {hi_path}  ({len(health_df)} rows)")
""")

code("""\
save_golden_outputs(inferences_df, health_df, CLIENT)
""")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 15 – Quick visualisation
# ═══════════════════════════════════════════════════════════════════════════════
md("## 15 · Quick visualisation")

code("""\
def plot_health_index_timeline(health_df: pd.DataFrame, unit: Optional[str] = None) -> None:
    \"\"\"Plot health index over time, optionally filtered by unit.\"\"\"
    df = health_df.copy()
    if unit:
        df = df[df[UNIT_COL] == unit]

    fig, axes = plt.subplots(2, 1, figsize=(16, 8), sharex=True)

    for comp in df["component"].unique():
        cdf = df[df["component"] == comp].sort_values("window_start")
        axes[0].plot(cdf["window_start"], cdf["health_index"], label=comp, alpha=0.7)
        axes[1].plot(cdf["window_start"], cdf["reconstruction_error"], label=comp, alpha=0.7)

    axes[0].set_ylabel("Health Index")
    axes[0].set_title(f"Health Index  {'(unit: ' + unit + ')' if unit else '(all units)'}")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].set_ylabel("Reconstruction Error")
    axes[1].set_xlabel("Time")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()
""")

code("""\
sample_unit = health_df[UNIT_COL].unique()[0]
plot_health_index_timeline(health_df, unit=sample_unit)
""")


# ═══════════════════════════════════════════════════════════════════════════════
# Build the .ipynb JSON
# ═══════════════════════════════════════════════════════════════════════════════
def build_notebook(cells_list: list) -> dict:
    """Convert cell dicts to a valid nbformat-4 notebook dict."""
    nb_cells = []
    for c in cells_list:
        source_lines = c["source"].split("\n")
        # nbformat stores source as a list of lines (each ending with \n except last)
        source_fmt = [line + "\n" for line in source_lines[:-1]]
        if source_lines:
            source_fmt.append(source_lines[-1])  # last line has no trailing \n

        cell = {
            "cell_type": c["cell_type"],
            "metadata": {},
            "source": source_fmt,
        }
        if c["cell_type"] == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        nb_cells.append(cell)

    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.12.4",
            },
        },
        "cells": nb_cells,
    }


if __name__ == "__main__":
    nb = build_notebook(cells)
    out_path = os.path.join(os.path.dirname(__file__), "health_index_improved.ipynb")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"Notebook written → {out_path}  ({len(cells)} cells)")
