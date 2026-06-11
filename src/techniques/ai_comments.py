"""
AI Diagnosis — Structured hierarchical diagnostic comments.

Generates diagnostic comments at three levels:
  1. Signal: What is remarkable about this signal?
  2. System: What is remarkable about this system?
  3. Unit: What is remarkable about this unit?

Each level builds on the previous (bottom-up), producing
independently stored comments for dashboard consumption.
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from src.config.settings import AICommentsConfig

logger = logging.getLogger(__name__)


def _get_client(config: AICommentsConfig):
    from openai import OpenAI
    if not config.api_key:
        raise ValueError("OPENAI_API_KEY not set in environment")
    return OpenAI(api_key=config.api_key)


def _get_signal_display(signal_name: str, signal_registry: dict) -> str:
    for s in signal_registry.get("signals", []):
        if s["name"] == signal_name:
            return s.get("display_name", signal_name)
    return signal_name


def _classify_urgency(priority_score: float) -> str:
    if priority_score >= 100:
        return "immediate"
    elif priority_score >= 50:
        return "schedule_inspection"
    elif priority_score >= 20:
        return "monitor"
    return "routine"


def generate_signal_comments(
    technique_results: pd.DataFrame,
    signal_registry: dict,
    config: AICommentsConfig,
) -> pd.DataFrame:
    """
    Generate AI diagnostic comments at the signal level.

    Parameters:
        technique_results: Combined technique results with columns
            [unit, signal, system, technique, risk_score, confidence_score, status]
        signal_registry: Signal metadata for context
        config: AI Comments configuration

    Returns:
        DataFrame with signal-level comments (only non-Normal signals).
    """
    if technique_results.empty:
        return pd.DataFrame()

    client = _get_client(config)
    now = datetime.utcnow()

    non_normal = technique_results[technique_results["status"] != "Normal"]
    if non_normal.empty:
        return pd.DataFrame()

    grouped = non_normal.groupby(["unit", "signal", "system"])

    records = []
    for (unit, signal, system), group in grouped:
        display_name = _get_signal_display(signal, signal_registry)
        techniques = group["technique"].unique().tolist()

        evidence_lines = []
        for _, row in group.iterrows():
            evidence_lines.append(
                f"- {row['technique']}: status={row['status']}, "
                f"risk_score={row['risk_score']:.0f}/100, "
                f"confidence={row['confidence_score']:.0f}/100"
            )

        max_risk = group["risk_score"].max()
        worst_status = group["status"].iloc[0]
        if "Anormal" in group["status"].values:
            worst_status = "Anormal"
        elif "Alerta" in group["status"].values:
            worst_status = "Alerta"

        signal_meta = next(
            (s for s in signal_registry.get("signals", []) if s["name"] == signal), {}
        )

        prompt = (
            f"You are a mining equipment telemetry analyst. Diagnose this signal.\n\n"
            f"**Signal**: {display_name} ({signal})\n"
            f"**System**: {system}\n"
            f"**Unit**: {unit}\n"
            f"**Risk Direction**: {signal_meta.get('risk_direction', 'unknown')}\n"
            f"**Criticality**: {signal_meta.get('criticality', 'unknown')}\n\n"
            f"**Technique Evidence**:\n"
            f"{chr(10).join(evidence_lines)}\n\n"
            f"In 2-3 sentences, explain what is remarkable about this signal based "
            f"on the evidence. Be factual and specific. Do not speculate."
        )

        try:
            response = client.chat.completions.create(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens_signal,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a concise technical analyst for mining equipment telemetry. Respond with factual observations only.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            comment = response.choices[0].message.content
        except Exception as e:
            logger.error(f"Signal comment failed for {unit}/{signal}: {e}")
            comment = f"[Diagnosis unavailable: {e}]"

        records.append({
            "unit": unit,
            "signal": signal,
            "system": system,
            "status": worst_status,
            "risk_score": max_risk,
            "comment": comment,
            "techniques_referenced": json.dumps(techniques),
            "evaluation_timestamp": now,
            "model_used": config.model,
        })

        time.sleep(config.rate_limit_delay)

    return pd.DataFrame(records)


def generate_system_comments(
    signal_comments: pd.DataFrame,
    system_health: pd.DataFrame,
    config: AICommentsConfig,
) -> pd.DataFrame:
    """
    Generate AI diagnostic comments at the system level.

    Uses signal-level comments as context (bottom-up approach).

    Parameters:
        signal_comments: Output from generate_signal_comments
        system_health: System health aggregation results
        config: AI Comments configuration

    Returns:
        DataFrame with system-level comments (only non-Normal systems).
    """
    if system_health.empty:
        return pd.DataFrame()

    client = _get_client(config)
    now = datetime.utcnow()

    non_normal_systems = system_health[system_health["system_status"] != "Normal"]
    if non_normal_systems.empty:
        return pd.DataFrame()

    records = []
    for _, sys_row in non_normal_systems.iterrows():
        unit = sys_row["unit"]
        system = sys_row["system"]

        relevant_signals = signal_comments[
            (signal_comments["unit"] == unit) & (signal_comments["system"] == system)
        ] if not signal_comments.empty else pd.DataFrame()

        signal_context_lines = []
        signals_referenced = []
        for _, sig_row in relevant_signals.iterrows():
            signal_context_lines.append(
                f"- **{sig_row['signal']}** ({sig_row['status']}, risk={sig_row['risk_score']:.0f}): "
                f"{sig_row['comment']}"
            )
            signals_referenced.append(sig_row["signal"])

        signal_context = "\n".join(signal_context_lines) if signal_context_lines else "No individual signal diagnoses available."

        prompt = (
            f"You are a mining equipment system health analyst.\n\n"
            f"**System**: {system}\n"
            f"**Unit**: {unit}\n"
            f"**System Status**: {sys_row['system_status']}\n"
            f"**System Score**: {sys_row['system_score']:.1f}/100\n"
            f"**Techniques Triggered**: {sys_row.get('n_techniques_triggered', 0)}\n\n"
            f"**Signal-Level Diagnoses**:\n{signal_context}\n\n"
            f"Based on the signal diagnoses above:\n"
            f"1. Summarize what is remarkable about this system (2-3 sentences)\n"
            f"2. Provide one recommended action\n\n"
            f"Be factual. Reference specific signals by name."
        )

        try:
            response = client.chat.completions.create(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens_system,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a concise system health analyst. Respond with a diagnosis paragraph followed by 'Recommended action:' on a new line.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            full_response = response.choices[0].message.content
        except Exception as e:
            logger.error(f"System comment failed for {unit}/{system}: {e}")
            full_response = f"[Diagnosis unavailable: {e}]"

        if "Recommended action:" in full_response:
            parts = full_response.split("Recommended action:", 1)
            comment = parts[0].strip()
            recommended_action = parts[1].strip()
        else:
            comment = full_response
            recommended_action = None

        records.append({
            "unit": unit,
            "system": system,
            "system_status": sys_row["system_status"],
            "system_score": sys_row["system_score"],
            "comment": comment,
            "signals_referenced": json.dumps(signals_referenced),
            "recommended_action": recommended_action,
            "evaluation_timestamp": now,
            "model_used": config.model,
        })

        time.sleep(config.rate_limit_delay)

    return pd.DataFrame(records)


def generate_unit_comments(
    system_comments: pd.DataFrame,
    unit_health: pd.DataFrame,
    config: AICommentsConfig,
) -> pd.DataFrame:
    """
    Generate AI diagnostic comments at the unit level.

    Uses system-level comments as context (bottom-up approach).

    Parameters:
        system_comments: Output from generate_system_comments
        unit_health: Unit health aggregation results
        config: AI Comments configuration

    Returns:
        DataFrame with unit-level comments (only non-Normal units).
    """
    if unit_health.empty:
        return pd.DataFrame()

    client = _get_client(config)
    now = datetime.utcnow()

    non_normal_units = unit_health[unit_health["overall_status"] != "Normal"]
    if non_normal_units.empty:
        return pd.DataFrame()

    records = []
    for _, unit_row in non_normal_units.iterrows():
        unit = unit_row["unit"]

        relevant_systems = system_comments[
            system_comments["unit"] == unit
        ] if not system_comments.empty else pd.DataFrame()

        system_context_lines = []
        systems_referenced = []
        for _, sys_row in relevant_systems.iterrows():
            system_context_lines.append(
                f"- **{sys_row['system']}** ({sys_row['system_status']}, "
                f"score={sys_row['system_score']:.0f}): {sys_row['comment']}"
            )
            systems_referenced.append(sys_row["system"])

        system_context = "\n".join(system_context_lines) if system_context_lines else "No system-level diagnoses available."
        urgency = _classify_urgency(unit_row["priority_score"])

        prompt = (
            f"You are a fleet health analyst for mining equipment.\n\n"
            f"**Unit**: {unit}\n"
            f"**Overall Status**: {unit_row['overall_status']}\n"
            f"**Priority Score**: {unit_row['priority_score']:.1f}\n"
            f"**Anormal Systems**: {unit_row.get('n_anormal_systems', 0)}\n"
            f"**Alerta Systems**: {unit_row.get('n_alerta_systems', 0)}\n\n"
            f"**System-Level Diagnoses**:\n{system_context}\n\n"
            f"Provide:\n"
            f"1. A 2-3 sentence executive assessment of this unit's condition\n"
            f"2. One top-priority recommended action\n\n"
            f"Focus on urgency and actionability for a maintenance planning meeting."
        )

        try:
            response = client.chat.completions.create(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens_unit,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a fleet health analyst. Respond with an assessment paragraph followed by 'Recommended action:' on a new line.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            full_response = response.choices[0].message.content
        except Exception as e:
            logger.error(f"Unit comment failed for {unit}: {e}")
            full_response = f"[Diagnosis unavailable: {e}]"

        if "Recommended action:" in full_response:
            parts = full_response.split("Recommended action:", 1)
            comment = parts[0].strip()
            recommended_action = parts[1].strip()
        else:
            comment = full_response
            recommended_action = None

        records.append({
            "unit": unit,
            "overall_status": unit_row["overall_status"],
            "priority_score": unit_row["priority_score"],
            "comment": comment,
            "systems_referenced": json.dumps(systems_referenced),
            "urgency": urgency,
            "recommended_action": recommended_action,
            "evaluation_timestamp": now,
            "model_used": config.model,
        })

        time.sleep(config.rate_limit_delay)

    return pd.DataFrame(records)


def run_ai_diagnosis(
    technique_results: pd.DataFrame,
    system_health: pd.DataFrame,
    unit_health: pd.DataFrame,
    signal_registry: dict,
    config: AICommentsConfig,
) -> dict[str, pd.DataFrame]:
    """
    Run the full AI Diagnosis pipeline (Signal → System → Unit).

    Parameters:
        technique_results: Combined technique results
        system_health: System health aggregation
        unit_health: Unit health aggregation
        signal_registry: Signal metadata
        config: AI Comments configuration

    Returns:
        Dict with keys 'signal', 'system', 'unit' mapping to DataFrames.
    """
    logger.info("  Generating signal-level comments...")
    signal_comments = generate_signal_comments(technique_results, signal_registry, config)
    logger.info(f"  Signal comments: {len(signal_comments)} generated")

    logger.info("  Generating system-level comments...")
    system_comments = generate_system_comments(signal_comments, system_health, config)
    logger.info(f"  System comments: {len(system_comments)} generated")

    logger.info("  Generating unit-level comments...")
    unit_comments = generate_unit_comments(system_comments, unit_health, config)
    logger.info(f"  Unit comments: {len(unit_comments)} generated")

    return {
        "signal": signal_comments,
        "system": system_comments,
        "unit": unit_comments,
    }
