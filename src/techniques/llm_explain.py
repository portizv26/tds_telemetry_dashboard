"""
LLM Integration — Natural language explanations via OpenAI API.

Generates human-readable health summaries for maintenance teams
at both system and unit levels.
"""

import logging
import time
from datetime import datetime
from typing import Optional

from src.config.settings import LLMConfig

logger = logging.getLogger(__name__)


def _get_client(config: LLMConfig):
    """Initialize OpenAI client."""
    from openai import OpenAI
    if not config.api_key:
        raise ValueError("OPENAI_API_KEY not set in environment")
    return OpenAI(api_key=config.api_key)


def _get_signal_display(signal_name: str, signal_registry: dict) -> str:
    """Resolve signal display name from registry."""
    for s in signal_registry["signals"]:
        if s["name"] == signal_name:
            return s.get("display_name", signal_name)
    return signal_name


def generate_system_explanation(
    system_health: dict,
    technique_results: list[dict],
    signal_registry: dict,
    config: LLMConfig,
) -> str:
    """
    Generate natural language explanation for a system health assessment.

    Parameters:
        system_health: System aggregation result dict
        technique_results: Technique detail dicts for context
        signal_registry: Signal metadata for display names
        config: LLM configuration

    Returns:
        Natural language explanation string.
    """
    client = _get_client(config)

    # Build evidence context (top 5 results)
    sorted_results = sorted(technique_results, key=lambda x: x.get("risk_score", 0), reverse=True)[:5]
    evidence_lines = []
    for r in sorted_results:
        display_name = _get_signal_display(r.get("signal", ""), signal_registry)
        technique = r.get("technique", "analysis")
        risk = r.get("risk_score", 0)
        status = r.get("status", "unknown")
        evidence_lines.append(f"- {display_name}: {technique} → {status} (risk={risk}/100)")

    evidence_text = "\n".join(evidence_lines) if evidence_lines else "No significant findings."

    prompt = f"""You are a mining equipment health analyst. Based on the telemetry analysis results below,
provide a concise explanation for maintenance teams.

**System**: {system_health['system']}
**Unit**: {system_health['unit']}
**Status**: {system_health['system_status']}
**Score**: {system_health['system_score']}/100

**Evidence**:
{evidence_text}

Provide:
1. One-sentence summary of the system condition
2. Key findings (max 3 bullet points)
3. Recommended action (one sentence)

Use signal display names. Be factual and actionable. Do not speculate beyond the data."""

    try:
        response = client.chat.completions.create(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            messages=[
                {
                    "role": "system",
                    "content": "You are a technical analyst for mining equipment health monitoring. Be concise, factual, and actionable.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM explanation failed for {system_health['unit']}/{system_health['system']}: {e}")
        return f"[Explanation unavailable: {e}]"


def generate_unit_summary(
    unit_health: dict,
    system_results: list[dict],
    config: LLMConfig,
) -> str:
    """
    Generate executive summary for a unit health assessment.

    Parameters:
        unit_health: Unit aggregation result dict
        system_results: All system health results for this unit
        config: LLM configuration

    Returns:
        Executive summary string.
    """
    client = _get_client(config)

    systems_text = "\n".join([
        f"- {s['system']}: {s['system_status']} (score={s['system_score']}/100)"
        for s in sorted(system_results, key=lambda x: x["system_score"], reverse=True)
    ])

    prompt = f"""You are a fleet health analyst for mining equipment. Generate a brief executive summary.

**Unit**: {unit_health['unit']}
**Overall Status**: {unit_health['overall_status']}
**Priority Score**: {unit_health['priority_score']}

**Systems**:
{systems_text}

Provide a 2-3 sentence executive summary for a maintenance planning meeting.
Focus on: what needs attention, urgency level, and recommended next steps."""

    try:
        response = client.chat.completions.create(
            model=config.model,
            temperature=config.temperature,
            max_tokens=500,
            messages=[
                {
                    "role": "system",
                    "content": "You are a fleet health analyst. Be concise and actionable.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM summary failed for {unit_health['unit']}: {e}")
        return f"[Summary unavailable: {e}]"


def generate_fleet_explanations(
    unit_healths: list[dict],
    system_healths: dict,
    technique_results_by_unit_system: dict,
    signal_registry: dict,
    config: LLMConfig,
) -> dict:
    """
    Generate explanations for all non-Normal units.

    Parameters:
        unit_healths: List of unit health dicts
        system_healths: Dict keyed by unit → list of system health dicts
        technique_results_by_unit_system: Dict keyed by (unit, system) → list of result dicts
        signal_registry: Signal metadata
        config: LLM configuration

    Returns:
        Dict: {unit: {'unit_summary': str, 'system_explanations': {system: str}}}
    """
    explanations = {}

    for uh in unit_healths:
        unit = uh["unit"]

        if config.skip_normal_units and uh["overall_status"] == "Normal":
            continue

        explanations[unit] = {"system_explanations": {}}

        # System-level explanations for non-Normal systems
        for sh in system_healths.get(unit, []):
            if sh["system_status"] == "Normal":
                continue

            results = technique_results_by_unit_system.get((unit, sh["system"]), [])
            explanation = generate_system_explanation(sh, results, signal_registry, config)
            explanations[unit]["system_explanations"][sh["system"]] = explanation
            time.sleep(config.rate_limit_delay)

        # Unit summary
        explanations[unit]["unit_summary"] = generate_unit_summary(
            uh, system_healths.get(unit, []), config
        )
        time.sleep(config.rate_limit_delay)

    logger.info(f"Generated explanations for {len(explanations)} units")
    return explanations
