"""
AI Comment Service

Generates expert maintenance comments for telemetry anomalies using OpenAI API.
"""

import os
from typing import Dict, List, Optional
import json

from src.utils.logger import logger


# Check for OpenAI availability
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. AI comments will be disabled.")


class AICommentService:
    """
    Service for generating AI-powered maintenance comments.
    
    Uses OpenAI API to generate expert insights on component and machine health
    based on telemetry anomaly patterns detected through percentile scoring.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize AI Comment Service.
        
        Parameters
        ----------
        api_key : str, optional
            OpenAI API key. If not provided, reads from OPENAI_API_KEY env var.
        model : str, default "gpt-4o-mini"
            OpenAI model to use for comment generation.
        """
        if not OPENAI_AVAILABLE:
            self.enabled = False
            logger.warning("AI comment service disabled: OpenAI package not available")
            return
        
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        if not self.api_key:
            self.enabled = False
            logger.warning("AI comment service disabled: No API key provided")
            return
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.enabled = True
        
        logger.info(f"AI comment service initialized with model: {model}")
    
    def generate_component_comment(
        self,
        unit_id: str,
        component: str,
        component_status: str,
        component_score: float,
        triggering_signals: List[str],
        signals_evaluation: Dict,
        evaluation_week: int,
        evaluation_year: int
    ) -> str:
        """
        Generate AI comment for component-level anomaly.
        
        Parameters
        ----------
        unit_id : str
            Equipment unit identifier
        component : str
            Component name (e.g., "Engine", "Transmission")
        component_status : str
            Component health status: "Normal", "Alerta", "Anormal"
        component_score : float
            Weighted severity score (0.0-1.0)
        triggering_signals : list of str
            Signals with non-normal status
        signals_evaluation : dict
            Per-signal evaluation details
        evaluation_week : int
            Week number evaluated
        evaluation_year : int
            Year evaluated
        
        Returns
        -------
        str
            AI-generated maintenance comment in Spanish
        """
        if not self.enabled:
            return None
        
        if component_status == 'Normal':
            return None
        
        # Build context for AI
        signal_details = []
        for signal in triggering_signals:
            if signal in signals_evaluation:
                eval_data = signals_evaluation[signal]
                signal_details.append({
                    'signal': signal,
                    'status': eval_data.get('status'),
                    'window_score': eval_data.get('window_score'),
                    'anomaly_percentage': eval_data.get('anomaly_percentage'),
                    'baseline': eval_data.get('baseline', {})
                })
        
        # Create prompt
        prompt = f"""Eres un experto en mantenimiento de camiones de extracción minera (haul trucks).

CONTEXTO DEL ANÁLISIS:
- Realizamos análisis semanal de señales de telemetría usando percentiles históricos
- Detectamos desviaciones de patrones normales comparando la semana actual con histórico de 90 días
- Usamos percentiles P1, P5, P95, P99 para clasificar lecturas como normales, alertas, o anormales

EQUIPO EVALUADO:
- Unidad: {unit_id}
- Componente: {component}
- Semana de Evaluación: {evaluation_week}/{evaluation_year}

CONDICIÓN DETECTADA:
- Estado del Componente: {component_status}
- Score de Severidad: {component_score:.2f} (rango 0.0-1.0)
- Señales con Desviación: {', '.join(triggering_signals)}

DETALLE DE SEÑALES ANORMALES:
{json.dumps(signal_details, indent=2)}

TAREA:
Genera un comentario técnico conciso (máximo 3 oraciones) que:
1. Explique qué condición anormal se detectó en el componente
2. Indique las posibles causas de esta desviación
3. Describa los riesgos si no se atiende oportunamente

El comentario debe ser técnico pero comprensible para el personal de mantenimiento.
Responde SOLO con el comentario, sin introducción ni formato adicional."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un experto en mantenimiento predictivo de equipos mineros pesados con 20+ años de experiencia."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=250
            )
            
            comment = response.choices[0].message.content.strip()
            logger.info(f"Generated component comment for {unit_id} - {component}")
            return comment
            
        except Exception as e:
            logger.error(f"Failed to generate component comment: {e}")
            return None
    
    def generate_machine_comment(
        self,
        unit_id: str,
        overall_status: str,
        machine_score: float,
        component_details: List[Dict],
        evaluation_week: int,
        evaluation_year: int
    ) -> str:
        """
        Generate AI comment for machine-level health assessment.
        
        Parameters
        ----------
        unit_id : str
            Equipment unit identifier
        overall_status : str
            Machine health status: "Normal", "Alerta", "Anormal"
        machine_score : float
            Aggregate severity score
        component_details : list of dict
            Per-component evaluation details
        evaluation_week : int
            Week number evaluated
        evaluation_year : int
            Year evaluated
        
        Returns
        -------
        str
            AI-generated maintenance summary in Spanish
        """
        if not self.enabled:
            return None
        
        # If machine is normal, return standard message
        if overall_status == 'Normal':
            return "No se detectaron anomalías en la evaluación semanal. El equipo opera dentro de parámetros normales según análisis de telemetría."
        
        # Build context for problematic components
        problematic_components = []
        for comp in component_details:
            if comp.get('status') in ['Alerta', 'Anormal']:
                problematic_components.append({
                    'component': comp['component'],
                    'status': comp['status'],
                    'score': comp['score'],
                    'triggering_signals': comp.get('triggering_signals', [])
                })
        
        # Create prompt
        prompt = f"""Eres un experto en mantenimiento de camiones de extracción minera (haul trucks).

CONTEXTO DEL ANÁLISIS:
- Realizamos análisis semanal de señales de telemetría usando percentiles históricos
- Detectamos desviaciones de patrones normales comparando la semana actual con histórico de 90 días
- El análisis evalúa múltiples componentes: Motor, Transmisión, Frenos, Dirección, etc.

EQUIPO EVALUADO:
- Unidad: {unit_id}
- Semana de Evaluación: {evaluation_week}/{evaluation_year}

CONDICIÓN GENERAL:
- Estado General: {overall_status}
- Score de Máquina: {machine_score:.2f}
- Total de Componentes con Problemas: {len(problematic_components)}

COMPONENTES AFECTADOS:
{json.dumps(problematic_components, indent=2)}

TAREA:
Genera un resumen ejecutivo (máximo 4 oraciones) que:
1. Describa la condición general del equipo
2. Identifique los componentes críticos afectados y sus señales principales
3. Explique los riesgos operacionales si no se interviene
4. Sugiera el nivel de prioridad para la intervención de mantenimiento

El resumen debe ser claro para supervisores y planificadores de mantenimiento.
Responde SOLO con el resumen, sin introducción ni formato adicional."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un experto en mantenimiento predictivo de equipos mineros pesados con 20+ años de experiencia."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=350
            )
            
            comment = response.choices[0].message.content.strip()
            logger.info(f"Generated machine comment for {unit_id}")
            return comment
            
        except Exception as e:
            logger.error(f"Failed to generate machine comment: {e}")
            return None
    
    def generate_batch_component_comments(
        self,
        components_data: List[Dict]
    ) -> Dict[str, str]:
        """
        Generate comments for multiple components in batch.
        
        Parameters
        ----------
        components_data : list of dict
            List of component evaluation data
        
        Returns
        -------
        dict
            Mapping of (unit_id, component) tuples to AI comments
        """
        comments = {}
        
        for comp_data in components_data:
            # Only generate for non-normal components
            if comp_data.get('component_status') not in ['Alerta', 'Anormal']:
                continue
            
            comment = self.generate_component_comment(
                unit_id=comp_data['unit_id'],
                component=comp_data['component'],
                component_status=comp_data['component_status'],
                component_score=comp_data['component_score'],
                triggering_signals=comp_data.get('triggering_signals', []),
                signals_evaluation=comp_data.get('signals_evaluation', {}),
                evaluation_week=comp_data['evaluation_week'],
                evaluation_year=comp_data['evaluation_year']
            )
            
            if comment:
                key = (comp_data['unit_id'], comp_data['component'])
                comments[key] = comment
        
        return comments


# Global singleton instance
_ai_service = None


def get_ai_service() -> AICommentService:
    """
    Get or create global AI comment service instance.
    
    Returns
    -------
    AICommentService
        Singleton AI service instance
    """
    global _ai_service
    
    if _ai_service is None:
        _ai_service = AICommentService()
    
    return _ai_service
