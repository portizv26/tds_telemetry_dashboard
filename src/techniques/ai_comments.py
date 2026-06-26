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
            f"Eres un analista de telemetría de equipos mineros. Diagnostica esta señal.\n\n"
            f"**Señal**: {display_name} ({signal})\n"
            f"**Sistema**: {system}\n"
            f"**Unidad**: {unit}\n"
            f"**Dirección de riesgo**: {signal_meta.get('risk_direction', 'unknown')}\n"
            f"**Criticidad**: {signal_meta.get('criticality', 'unknown')}\n\n"
            f"**Evidencia de técnicas**:\n"
            f"{chr(10).join(evidence_lines)}\n\n"
            f"Responde en formato JSON con dos campos:\n"
            f"- \"description\": Una oración breve (máx 20 palabras) indicando qué se detectó en esta señal.\n"
            f"- \"explaining\": Un párrafo detallado (2-4 oraciones) explicando qué se encontró y por qué es relevante, basándote en la evidencia. Sé factual y específico.\n\n"
            f"Responde SOLO con el JSON, sin texto adicional."
        )

        try:
            response = client.chat.completions.create(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens_signal,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un analista técnico conciso de telemetría de equipos mineros. Responde siempre en español con observaciones factuales. Responde únicamente en formato JSON válido.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
            description = parsed.get("description", "")
            explaining = parsed.get("explaining", "")
        except json.JSONDecodeError:
            logger.warning(f"Signal comment JSON parse failed for {unit}/{signal}, using raw text")
            description = raw if raw else "[Diagnóstico no disponible]"
            explaining = ""
        except Exception as e:
            logger.error(f"Signal comment failed for {unit}/{signal}: {e}")
            description = f"[Diagnóstico no disponible: {e}]"
            explaining = ""

        records.append({
            "unit": unit,
            "signal": signal,
            "system": system,
            "status": worst_status,
            "risk_score": max_risk,
            "description": description,
            "explaining": explaining,
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
                f"{sig_row['description']} — {sig_row['explaining']}"
            )
            signals_referenced.append(sig_row["signal"])

        signal_context = "\n".join(signal_context_lines) if signal_context_lines else "Sin diagnósticos individuales de señal disponibles."

        prompt = (
            f"Eres un analista de salud de sistemas de equipos mineros.\n\n"
            f"**Sistema**: {system}\n"
            f"**Unidad**: {unit}\n"
            f"**Estado del sistema**: {sys_row['system_status']}\n"
            f"**Puntaje del sistema**: {sys_row['system_score']:.1f}/100\n"
            f"**Técnicas activadas**: {sys_row.get('n_techniques_triggered', 0)}\n\n"
            f"**Diagnósticos a nivel de señal**:\n{signal_context}\n\n"
            f"Basándote en los diagnósticos de señales anteriores, responde en formato JSON con tres campos:\n"
            f"- \"description\": Una oración breve (máx 20 palabras) resumiendo el estado del sistema.\n"
            f"- \"explaining\": Un párrafo detallado (2-4 oraciones) explicando qué se encontró y por qué es relevante. Referencia señales específicas por nombre.\n"
            f"- \"recommended_action\": Una acción de mantenimiento recomendada en una oración.\n\n"
            f"Responde SOLO con el JSON, sin texto adicional."
        )

        try:
            response = client.chat.completions.create(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens_system,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un analista conciso de salud de sistemas. Responde siempre en español con observaciones factuales. Responde únicamente en formato JSON válido.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
            description = parsed.get("description", "")
            explaining = parsed.get("explaining", "")
            recommended_action = parsed.get("recommended_action", None)
        except json.JSONDecodeError:
            logger.warning(f"System comment JSON parse failed for {unit}/{system}, using raw text")
            description = raw if raw else "[Diagnóstico no disponible]"
            explaining = ""
            recommended_action = None
        except Exception as e:
            logger.error(f"System comment failed for {unit}/{system}: {e}")
            description = f"[Diagnóstico no disponible: {e}]"
            explaining = ""
            recommended_action = None

        records.append({
            "unit": unit,
            "system": system,
            "system_status": sys_row["system_status"],
            "system_score": sys_row["system_score"],
            "description": description,
            "explaining": explaining,
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
                f"score={sys_row['system_score']:.0f}): {sys_row['description']} — {sys_row['explaining']}"
            )
            systems_referenced.append(sys_row["system"])

        system_context = "\n".join(system_context_lines) if system_context_lines else "Sin diagnósticos a nivel de sistema disponibles."
        urgency = _classify_urgency(unit_row["priority_score"])

        prompt = (
            f"Eres un analista de salud de flota de equipos mineros.\n\n"
            f"**Unidad**: {unit}\n"
            f"**Estado general**: {unit_row['overall_status']}\n"
            f"**Puntaje de prioridad**: {unit_row['priority_score']:.1f}\n"
            f"**Sistemas Anormales**: {unit_row.get('n_anormal_systems', 0)}\n"
            f"**Sistemas en Alerta**: {unit_row.get('n_alerta_systems', 0)}\n\n"
            f"**Diagnósticos a nivel de sistema**:\n{system_context}\n\n"
            f"Responde en formato JSON con tres campos:\n"
            f"- \"description\": Una oración breve (máx 20 palabras) resumiendo la condición general de la unidad.\n"
            f"- \"explaining\": Un párrafo detallado (2-4 oraciones) con la evaluación ejecutiva de la condición. Enfócate en urgencia y accionabilidad para una reunión de planificación de mantenimiento.\n"
            f"- \"recommended_action\": La acción de mayor prioridad recomendada en una oración.\n\n"
            f"Responde SOLO con el JSON, sin texto adicional."
        )

        try:
            response = client.chat.completions.create(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens_unit,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un analista de salud de flota. Responde siempre en español con evaluaciones factuales y accionables. Responde únicamente en formato JSON válido.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
            description = parsed.get("description", "")
            explaining = parsed.get("explaining", "")
            recommended_action = parsed.get("recommended_action", None)
        except json.JSONDecodeError:
            logger.warning(f"Unit comment JSON parse failed for {unit}, using raw text")
            description = raw if raw else "[Diagnóstico no disponible]"
            explaining = ""
            recommended_action = None
        except Exception as e:
            logger.error(f"Unit comment failed for {unit}: {e}")
            description = f"[Diagnóstico no disponible: {e}]"
            explaining = ""
            recommended_action = None

        records.append({
            "unit": unit,
            "overall_status": unit_row["overall_status"],
            "priority_score": unit_row["priority_score"],
            "description": description,
            "explaining": explaining,
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
