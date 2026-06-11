"""
Pipeline Coordinator — Orchestrates the full telemetry analysis pipeline.

Execution flow:
  1. Load configuration and data
  2. Preprocess (model specification, validation)
  3. Compute/load baselines
  4. Run deviation analysis
  5. Run event analysis (depends on deviation)
  6. Run trend analysis
  7. Run distribution shift analysis
  8. Run autoencoder inference (depends on deviation for training)
  9. Aggregate results (Signal → System → Unit)
  10. AI Diagnosis (Signal → System → Unit comments)
  11. Generate LLM explanations (legacy, optional)
  12. Persist outputs to Golden layer
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from src.config.settings import (
    PipelineConfig,
    build_config,
    UNIT_COLNAME,
    TIME_COLNAME,
)
from src.config import load_signal_registry, load_equipment_registry
from src.utils.data_utils import (
    load_telemetry_files,
    compute_model_specification,
    validate_telemetry_data,
    get_all_systems,
    get_system_signals,
)
from src.techniques.deviation import compute_limits, apply_deviation_analysis, summarize_deviation, persist_limits
from src.techniques.events import run_event_analysis
from src.techniques.trend import run_trend_analysis
from src.techniques.distribution import run_distribution_analysis
from src.techniques.aggregation import run_aggregation
from src.techniques.ai_comments import run_ai_diagnosis

logger = logging.getLogger(__name__)


class TelemetryPipeline:
    """
    Main pipeline coordinator for telemetry health evaluation.

    Usage:
        pipeline = TelemetryPipeline(client="cda")
        pipeline.run()
    """

    def __init__(self, client: str = "cda", weeks: Optional[list[str]] = None):
        """
        Initialize pipeline.

        Parameters:
            client: Client identifier (default: "cda")
            weeks: Specific weekly files to process (e.g., ["Week22Year2026"]).
                   If None, processes all available files.
        """
        self.config = build_config(client)
        self.weeks = weeks
        self.signal_registry = None
        self.equipment_registry = None
        self.df_raw = None
        self.df_preprocessed = None
        self.limits = None
        self.df_labeled = None
        self.baseline_version = ""

        # Results storage
        self.deviation_summary = pd.DataFrame()
        self.event_results = pd.DataFrame()
        self.trend_results = pd.DataFrame()
        self.distribution_results = pd.DataFrame()
        self.system_health = pd.DataFrame()
        self.unit_health = pd.DataFrame()
        self.ai_comments = {"signal": pd.DataFrame(), "system": pd.DataFrame(), "unit": pd.DataFrame()}

    def run(self, skip_autoencoder: bool = False, skip_llm: bool = False, skip_ai_comments: bool = False) -> dict:
        """
        Execute the full pipeline.

        Parameters:
            skip_autoencoder: Skip LSTM training/inference (faster, for testing)
            skip_llm: Skip LLM explanation generation (saves API costs)
            skip_ai_comments: Skip AI Diagnosis generation (saves API costs)

        Returns:
            Summary dict with counts and statuses.
        """
        start_time = datetime.utcnow()
        logger.info("=" * 60)
        logger.info(f"Pipeline started: client={self.config.client}")
        logger.info("=" * 60)

        # Phase 1: Load
        self._load_data()

        # Phase 2: Preprocess
        self._preprocess()

        # Phase 3: Baselines
        self._load_or_compute_baselines()

        # Phase 4: Deviation Analysis
        self._run_deviation()

        # Phase 5: Event Analysis
        self._run_events()

        # Phase 6: Trend Analysis
        self._run_trends()

        # Phase 7: Distribution Shift Analysis
        self._run_distribution()

        # Phase 8: Autoencoder (optional)
        if not skip_autoencoder:
            self._run_autoencoder()

        # Phase 9: Aggregation
        self._run_aggregation()

        # Phase 10: AI Diagnosis (optional)
        if not skip_ai_comments:
            self._run_ai_diagnosis()

        # Phase 11: LLM Explanations (legacy, optional)
        if not skip_llm:
            self._run_llm_explanations()

        # Phase 12: Persist outputs
        self._persist_outputs()

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        summary = self._build_summary(elapsed)
        logger.info(f"Pipeline complete in {elapsed:.1f}s")
        return summary

    # ─── Phase 1: Load ─────────────────────────────────────────────────────

    def _load_data(self):
        """Load telemetry data and configuration."""
        logger.info("Phase 1: Loading data and configuration...")

        self.signal_registry = load_signal_registry(self.config)
        self.equipment_registry = load_equipment_registry(self.config)
        self.df_raw = load_telemetry_files(self.config.telemetry_path, self.weeks)

        logger.info(f"  Loaded {len(self.df_raw)} rows, {self.df_raw[UNIT_COLNAME].nunique()} units")

    # ─── Phase 2: Preprocess ───────────────────────────────────────────────

    def _preprocess(self):
        """Validate data and compute model specifications."""
        logger.info("Phase 2: Preprocessing...")

        validation = validate_telemetry_data(self.df_raw)
        if not validation["valid"]:
            for issue in validation["issues"]:
                logger.warning(f"  Data issue: {issue}")

        self.df_preprocessed = compute_model_specification(self.df_raw, self.equipment_registry)
        logger.info(f"  Preprocessed: {len(self.df_preprocessed)} rows")

    # ─── Phase 3: Baselines ────────────────────────────────────────────────

    def _load_or_compute_baselines(self):
        """Load existing baselines or compute from data."""
        logger.info("Phase 3: Loading/computing baselines...")

        baselines_path = self.config.baselines_path
        baseline_files = sorted(baselines_path.glob("baseline_*.parquet")) if baselines_path.exists() else []

        if baseline_files:
            self.baseline_version = baseline_files[-1].stem.replace("baseline_", "")
            logger.info(f"  Using existing baseline: {self.baseline_version}")
        else:
            logger.info("  No baseline files found, computing from data...")
            self.baseline_version = "computed"

        # Compute limits from data (always, for threshold comparison)
        self.limits = compute_limits(
            self.df_preprocessed, self.signal_registry, self.config.deviation
        )
        logger.info(f"  Computed limits for {len(self.limits)} model specifications")

        # Persist limits to Silver layer
        persist_limits(self.limits, self.config.limits_path, datetime.utcnow())

    # ─── Phase 4: Deviation ────────────────────────────────────────────────

    def _run_deviation(self):
        """Run deviation analysis."""
        logger.info("Phase 4: Running deviation analysis...")

        self.df_labeled = apply_deviation_analysis(
            self.df_preprocessed, self.limits, self.signal_registry
        )

        self.deviation_summary = summarize_deviation(
            self.df_labeled, self.signal_registry, self.baseline_version
        )

        n_anormal = (self.deviation_summary["status"] == "Anormal").sum() if len(self.deviation_summary) > 0 else 0
        logger.info(f"  Deviation: {len(self.deviation_summary)} results, {n_anormal} Anormal")

    # ─── Phase 5: Events ───────────────────────────────────────────────────

    def _run_events(self):
        """Run event analysis on deviation-labeled data."""
        logger.info("Phase 5: Running event analysis...")

        self.event_results = run_event_analysis(
            self.df_labeled, self.signal_registry, self.config.event
        )

        n_warnings = (self.event_results["event_type_weighted"] == "warning").sum() if len(self.event_results) > 0 else 0
        logger.info(f"  Events: {len(self.event_results)} total, {n_warnings} warnings")

    # ─── Phase 6: Trends ───────────────────────────────────────────────────

    def _run_trends(self):
        """Run trend analysis."""
        logger.info("Phase 6: Running trend analysis...")

        self.trend_results = run_trend_analysis(
            self.df_preprocessed, self.signal_registry,
            self.config.trend, self.baseline_version
        )

        n_sig = (self.trend_results["is_significant"]).sum() if len(self.trend_results) > 0 else 0
        logger.info(f"  Trends: {len(self.trend_results)} results, {n_sig} significant")

    # ─── Phase 7: Distribution ─────────────────────────────────────────────

    def _run_distribution(self):
        """Run distribution shift analysis."""
        logger.info("Phase 7: Running distribution shift analysis...")

        self.distribution_results = run_distribution_analysis(
            self.df_preprocessed, self.signal_registry,
            self.config.distribution, self.baseline_version
        )

        n_sig = (self.distribution_results["is_significant"]).sum() if len(self.distribution_results) > 0 else 0
        logger.info(f"  Distribution: {len(self.distribution_results)} results, {n_sig} significant")

    # ─── Phase 8: Autoencoder ──────────────────────────────────────────────

    def _run_autoencoder(self):
        """Train and score autoencoder models."""
        logger.info("Phase 8: Running autoencoder analysis...")
        try:
            from src.techniques.autoencoder import train_model, score_sequences

            systems = get_all_systems(self.signal_registry)
            units = self.df_preprocessed[UNIT_COLNAME].unique()

            trained = 0
            for unit in units:
                for system in systems:
                    features = get_system_signals(self.signal_registry, system)
                    if len(features) < 3:
                        continue

                    model_info = train_model(
                        self.df_preprocessed,
                        self.df_labeled,
                        unit, system, features,
                        self.config.autoencoder,
                    )
                    if model_info:
                        trained += 1

            logger.info(f"  Autoencoder: {trained} models trained")
        except ImportError:
            logger.warning("  TensorFlow not available, skipping autoencoder")
        except Exception as e:
            logger.error(f"  Autoencoder failed: {e}")

    # ─── Phase 9: Aggregation ──────────────────────────────────────────────

    def _run_aggregation(self):
        """Aggregate technique results into system/unit health."""
        logger.info("Phase 9: Running aggregation...")

        # Combine all technique results into unified format
        combined = self._combine_technique_results()

        if combined.empty:
            logger.warning("  No technique results to aggregate")
            return

        self.system_health, self.unit_health = run_aggregation(
            combined, self.signal_registry, self.config.aggregation
        )

        logger.info(
            f"  Aggregation: {len(self.system_health)} systems, "
            f"{len(self.unit_health)} units"
        )

    def _combine_technique_results(self) -> pd.DataFrame:
        """Combine all technique summaries into a single DataFrame for aggregation."""
        frames = []

        if not self.deviation_summary.empty:
            dev = self.deviation_summary.copy()
            dev["technique"] = "deviation"
            frames.append(dev[["unit", "signal", "system", "technique", "risk_score", "confidence_score", "status"]])

        if not self.trend_results.empty:
            tr = self.trend_results.copy()
            tr["technique"] = "trend"
            frames.append(tr[["unit", "signal", "system", "technique", "risk_score", "confidence_score", "status"]])

        if not self.distribution_results.empty:
            dist = self.distribution_results.copy()
            dist["technique"] = "distribution"
            frames.append(dist[["unit", "signal", "system", "technique", "risk_score", "confidence_score", "status"]])

        if not frames:
            return pd.DataFrame()

        return pd.concat(frames, ignore_index=True)

    # ─── Phase 10: AI Diagnosis ─────────────────────────────────────────

    def _run_ai_diagnosis(self):
        """Generate structured AI diagnostic comments (Signal → System → Unit)."""
        logger.info("Phase 10: Running AI Diagnosis...")

        if self.system_health.empty or not self.config.ai_comments.api_key:
            logger.info("  Skipping AI Diagnosis (no results or no API key)")
            return

        try:
            combined = self._combine_technique_results()

            self.ai_comments = run_ai_diagnosis(
                technique_results=combined,
                system_health=self.system_health,
                unit_health=self.unit_health,
                signal_registry=self.signal_registry,
                config=self.config.ai_comments,
            )

            total = sum(len(df) for df in self.ai_comments.values())
            logger.info(f"  AI Diagnosis complete: {total} comments generated")

        except Exception as e:
            logger.error(f"  AI Diagnosis failed: {e}")

    # ─── Phase 11: LLM Explanations (legacy) ─────────────────────────────

    def _run_llm_explanations(self):
        """Generate LLM explanations for non-Normal units (legacy)."""
        logger.info("Phase 11: Generating LLM explanations (legacy)...")

        if self.unit_health.empty or not self.config.llm.api_key:
            logger.info("  Skipping LLM (no results or no API key)")
            return

        try:
            from src.techniques.llm_explain import generate_fleet_explanations

            # Prepare data structures
            unit_healths = self.unit_health.to_dict("records")
            system_healths_by_unit = {}
            for _, row in self.system_health.iterrows():
                unit = row["unit"]
                if unit not in system_healths_by_unit:
                    system_healths_by_unit[unit] = []
                system_healths_by_unit[unit].append(row.to_dict())

            # Technique results by (unit, system) for evidence
            technique_by_us = {}
            combined = self._combine_technique_results()
            if not combined.empty:
                for (unit, system), group in combined.groupby(["unit", "system"]):
                    technique_by_us[(unit, system)] = group.to_dict("records")

            explanations = generate_fleet_explanations(
                unit_healths,
                system_healths_by_unit,
                technique_by_us,
                self.signal_registry,
                self.config.llm,
            )

            # Attach explanations to health DataFrames
            for unit, exp in explanations.items():
                # Unit summary
                mask = self.unit_health["unit"] == unit
                if mask.any():
                    self.unit_health.loc[mask, "executive_summary"] = exp.get("unit_summary", "")

                # System explanations
                for system, text in exp.get("system_explanations", {}).items():
                    sys_mask = (self.system_health["unit"] == unit) & (self.system_health["system"] == system)
                    if sys_mask.any():
                        self.system_health.loc[sys_mask, "explanation"] = text

            logger.info(f"  Generated explanations for {len(explanations)} units")

        except Exception as e:
            logger.error(f"  LLM explanations failed: {e}")

    # ─── Phase 12: Persist ─────────────────────────────────────────────────

    def _persist_outputs(self):
        """Save outputs to Golden layer."""
        logger.info("Phase 12: Persisting outputs...")

        output_base = self.config.output_path
        now = datetime.utcnow()
        year = now.year
        week = now.isocalendar()[1]

        # Deviation results
        if not self.deviation_summary.empty:
            path = output_base / "technique_results" / "deviation" / f"year={year}" / f"week={week}"
            path.mkdir(parents=True, exist_ok=True)
            self.deviation_summary.to_parquet(path / "deviation_results.parquet", index=False)

        # Event results
        if not self.event_results.empty:
            path = output_base / "technique_results" / "events" / f"year={year}" / f"week={week}"
            path.mkdir(parents=True, exist_ok=True)
            self.event_results.to_parquet(path / "events.parquet", index=False)

        # Trend results
        if not self.trend_results.empty:
            path = output_base / "technique_results" / "trend" / f"year={year}" / f"week={week}"
            path.mkdir(parents=True, exist_ok=True)
            self.trend_results.to_parquet(path / "trend_results.parquet", index=False)

        # Distribution results
        if not self.distribution_results.empty:
            path = output_base / "technique_results" / "distribution" / f"year={year}" / f"week={week}"
            path.mkdir(parents=True, exist_ok=True)
            self.distribution_results.to_parquet(path / "distribution_results.parquet", index=False)

        # System health
        if not self.system_health.empty:
            path = output_base / "system_health" / f"year={year}" / f"week={week}"
            path.mkdir(parents=True, exist_ok=True)
            self.system_health.to_parquet(path / "system_health.parquet", index=False)

        # Unit health
        if not self.unit_health.empty:
            path = output_base / "unit_health" / f"year={year}" / f"week={week}"
            path.mkdir(parents=True, exist_ok=True)
            self.unit_health.to_parquet(path / "unit_health.parquet", index=False)

        # AI Comments
        ai_path = output_base / "ai_comments" / f"year={year}" / f"week={week}"
        if not self.ai_comments["signal"].empty:
            ai_path.mkdir(parents=True, exist_ok=True)
            self.ai_comments["signal"].to_parquet(ai_path / "signal_comments.parquet", index=False)
        if not self.ai_comments["system"].empty:
            ai_path.mkdir(parents=True, exist_ok=True)
            self.ai_comments["system"].to_parquet(ai_path / "system_comments.parquet", index=False)
        if not self.ai_comments["unit"].empty:
            ai_path.mkdir(parents=True, exist_ok=True)
            self.ai_comments["unit"].to_parquet(ai_path / "unit_comments.parquet", index=False)

        logger.info(f"  Outputs saved to {output_base}")

    # ─── Summary ───────────────────────────────────────────────────────────

    def _build_summary(self, elapsed_seconds: float) -> dict:
        """Build execution summary."""
        return {
            "client": self.config.client,
            "elapsed_seconds": round(elapsed_seconds, 1),
            "input_rows": len(self.df_raw) if self.df_raw is not None else 0,
            "units_processed": self.df_preprocessed[UNIT_COLNAME].nunique() if self.df_preprocessed is not None else 0,
            "baseline_version": self.baseline_version,
            "deviation_results": len(self.deviation_summary),
            "events_detected": len(self.event_results),
            "trend_results": len(self.trend_results),
            "distribution_results": len(self.distribution_results),
            "system_assessments": len(self.system_health),
            "unit_assessments": len(self.unit_health),
            "ai_comments_signal": len(self.ai_comments["signal"]),
            "ai_comments_system": len(self.ai_comments["system"]),
            "ai_comments_unit": len(self.ai_comments["unit"]),
            "units_anormal": int((self.unit_health["overall_status"] == "Anormal").sum()) if not self.unit_health.empty else 0,
            "units_alerta": int((self.unit_health["overall_status"] == "Alerta").sum()) if not self.unit_health.empty else 0,
        }
