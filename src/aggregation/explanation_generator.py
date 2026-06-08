"""
Explanation Generator.

Generates human-readable natural language explanations for health assessments.

Methodology
-----------
1. Load explanation templates from configuration
2. Extract top contributing signals/systems
3. Generate status-specific explanations (Normal/Alerta/Anormal)
4. Include evidence details (values, deviations, trends)
5. Suggest recommended actions

Templates support variable substitution for dynamic content.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml

from src.models.entities import SystemHealth, UnitHealth, TechniqueResult
from src.config.signal_registry import SignalRegistry
from src.utils.logger import get_logger


class ExplanationGenerator:
    """
    Generates natural language explanations for health assessments.
    
    Parameters
    ----------
    signal_registry : SignalRegistry
        Signal metadata registry
    templates_path : Optional[Path]
        Path to explanation_templates.yaml (optional)
    """
    
    def __init__(
        self,
        signal_registry: SignalRegistry,
        templates_path: Optional[Path] = None,
    ):
        self.signal_registry = signal_registry
        self.logger = get_logger("explanation_generator")
        
        if templates_path and templates_path.exists():
            self.templates = self._load_templates(templates_path)
        else:
            self.templates = self._get_default_templates()
    
    def _load_templates(self, templates_path: Path) -> Dict[str, Any]:
        """Load templates from YAML file."""
        try:
            with open(templates_path, 'r') as f:
                templates = yaml.safe_load(f)
            return templates
        except Exception as e:
            self.logger.warning(f"Failed to load templates: {e}, using defaults")
            return self._get_default_templates()
    
    def _get_default_templates(self) -> Dict[str, Any]:
        """Get default explanation templates."""
        return {
            'system': {
                'Normal': {
                    'template': "Sistema {system} operando normalmente. Puntaje de salud: {score:.0f}/100 (Confianza: {confidence:.0f}%).",
                    'with_signals': "Señales principales: {signals_summary}. Sin anomalías detectadas."
                },
                'Alerta': {
                    'template': "Sistema {system} en estado de ALERTA. Puntaje de salud: {score:.0f}/100 (Confianza: {confidence:.0f}%).",
                    'with_signals': "Señales afectadas: {signals_summary}. Se recomienda monitoreo cercano.",
                    'top_contributor': "Señal más crítica: {signal} con puntaje de riesgo {signal_score:.0f}/100."
                },
                'Anormal': {
                    'template': "Sistema {system} en estado ANORMAL. Puntaje de salud: {score:.0f}/100 (Confianza: {confidence:.0f}%).",
                    'with_signals': "Señales críticas: {signals_summary}. Requiere inspección inmediata.",
                    'top_contributor': "Señal más crítica: {signal} con puntaje de riesgo {signal_score:.0f}/100.",
                    'urgency': "ATENCIÓN: Se recomienda acción correctiva urgente."
                },
                'InsufficientData': {
                    'template': "Sistema {system}: Datos insuficientes para evaluación confiable (Confianza: {confidence:.0f}%).",
                    'reason': "Se requiere mayor cobertura de datos para análisis preciso."
                }
            },
            'unit': {
                'Normal': {
                    'template': "Unidad {unit_id} operando normalmente. Puntaje general: {score:.0f}/100 (Confianza: {confidence:.0f}%).",
                    'systems': "Todos los sistemas dentro de parámetros normales. {normal_count} sistemas evaluados."
                },
                'Alerta': {
                    'template': "Unidad {unit_id} en estado de ALERTA. Puntaje general: {score:.0f}/100 (Confianza: {confidence:.0f}%).",
                    'systems': "Sistemas afectados: {affected_systems}. {alerta_count} en alerta, {anormal_count} anormales.",
                    'priority': "Prioridad de mantenimiento: {priority_score:.0f}. Urgencia: {urgency}."
                },
                'Anormal': {
                    'template': "Unidad {unit_id} en estado ANORMAL. Puntaje general: {score:.0f}/100 (Confianza: {confidence:.0f}%).",
                    'systems': "Sistemas críticos: {affected_systems}. {anormal_count} sistemas anormales requieren atención.",
                    'priority': "Prioridad de mantenimiento: {priority_score:.0f}. Urgencia: {urgency}.",
                    'action': "ACCIÓN REQUERIDA: Inspección y reparación necesaria."
                },
                'InsufficientData': {
                    'template': "Unidad {unit_id}: Evaluación limitada por datos insuficientes (Confianza: {confidence:.0f}%).",
                    'reason': "Se requiere mayor cobertura de datos en múltiples sistemas."
                }
            }
        }
    
    def generate_system_explanation(
        self,
        system_health: SystemHealth,
        technique_results: Optional[List[TechniqueResult]] = None,
    ) -> str:
        """
        Generate natural language explanation for system health.
        
        Parameters
        ----------
        system_health : SystemHealth
            System health assessment
        technique_results : Optional[List[TechniqueResult]]
            Technique results contributing to assessment
        
        Returns
        -------
        str
            Natural language explanation
        """
        status = system_health.system_status
        templates = self.templates['system'].get(status, {})
        
        # Build base explanation
        base = templates.get('template', '').format(
            system=system_health.system,
            score=system_health.system_score,
            confidence=system_health.system_confidence,
        )
        
        # Add signals summary
        if system_health.top_signals and len(system_health.top_signals) > 0:
            signals_summary = self._format_signals_summary(
                system_health.top_signals, technique_results
            )
            
            signals_part = templates.get('with_signals', '').format(
                signals_summary=signals_summary
            )
            
            base += " " + signals_part
            
            # Add top contributor details
            if status in ['Alerta', 'Anormal'] and 'top_contributor' in templates:
                top_signal = system_health.top_signals[0]
                top_signal_score = self._get_signal_max_risk(top_signal, technique_results)
                
                contributor_part = templates.get('top_contributor', '').format(
                    signal=self._get_signal_display_name(top_signal),
                    signal_score=top_signal_score,
                )
                
                base += " " + contributor_part
        
        # Add urgency message for Anormal
        if status == 'Anormal' and 'urgency' in templates:
            base += " " + templates['urgency']
        
        # Add insufficient data reason
        if status == 'InsufficientData' and 'reason' in templates:
            base += " " + templates['reason']
        
        return base.strip()
    
    def generate_unit_explanation(
        self,
        unit_health: UnitHealth,
        system_health_list: Optional[List[SystemHealth]] = None,
    ) -> str:
        """
        Generate natural language explanation for unit health.
        
        Parameters
        ----------
        unit_health : UnitHealth
            Unit health assessment
        system_health_list : Optional[List[SystemHealth]]
            System health assessments for unit
        
        Returns
        -------
        str
            Natural language explanation
        """
        status = unit_health.overall_status
        templates = self.templates['unit'].get(status, {})
        
        # Build base explanation
        base = templates.get('template', '').format(
            unit_id=unit_health.unit_id,
            score=unit_health.unit_score,
            confidence=unit_health.unit_confidence,
        )
        
        # Get urgency text
        urgency_text = self._get_urgency_text(unit_health)
        
        # Add systems details
        if status == 'Normal':
            systems_part = templates.get('systems', '').format(
                normal_count=unit_health.systems_normal,
            )
            base += " " + systems_part
        
        elif status in ['Alerta', 'Anormal']:
            # Get affected systems
            affected_systems = self._format_affected_systems(
                unit_health.top_risk_systems, system_health_list
            )
            
            systems_part = templates.get('systems', '').format(
                affected_systems=affected_systems,
                alerta_count=unit_health.systems_alerta,
                anormal_count=unit_health.systems_anormal,
            )
            
            base += " " + systems_part
            
            # Add priority information
            priority_part = templates.get('priority', '').format(
                priority_score=unit_health.priority_score,
                urgency=urgency_text,
            )
            
            base += " " + priority_part
            
            # Add action message for Anormal
            if status == 'Anormal' and 'action' in templates:
                base += " " + templates['action']
        
        elif status == 'InsufficientData':
            if 'reason' in templates:
                base += " " + templates['reason']
        
        return base.strip()
    
    def _format_signals_summary(
        self,
        signals: List[str],
        technique_results: Optional[List[TechniqueResult]],
    ) -> str:
        """
        Format list of signals with display names.
        
        Parameters
        ----------
        signals : List[str]
            Signal names
        technique_results : Optional[List[TechniqueResult]]
            Technique results for signal details
        
        Returns
        -------
        str
            Formatted signal summary
        """
        if not signals:
            return "ninguna"
        
        signal_displays = []
        for signal in signals[:3]:  # Top 3
            display_name = self._get_signal_display_name(signal)
            
            # Try to get current value if available
            if technique_results:
                for result in technique_results:
                    if result.signal_name == signal:
                        # Get mean value from evidence if available
                        if 'mean_value' in result.evidence:
                            value = result.evidence['mean_value']
                            signal_meta = self.signal_registry.get_signal(signal)
                            unit = signal_meta.unit if signal_meta else ""
                            signal_displays.append(f"{display_name} ({value:.1f} {unit})")
                            break
                else:
                    signal_displays.append(display_name)
            else:
                signal_displays.append(display_name)
        
        return ", ".join(signal_displays)
    
    def _format_affected_systems(
        self,
        systems: List[str],
        system_health_list: Optional[List[SystemHealth]],
    ) -> str:
        """
        Format list of affected systems with scores.
        
        Parameters
        ----------
        systems : List[str]
            System names
        system_health_list : Optional[List[SystemHealth]]
            System health assessments
        
        Returns
        -------
        str
            Formatted systems summary
        """
        if not systems:
            return "ninguno"
        
        system_displays = []
        for system in systems[:3]:  # Top 3
            if system_health_list:
                # Find system health
                for sh in system_health_list:
                    if sh.system == system:
                        system_displays.append(f"{system} ({sh.system_score:.0f}/100)")
                        break
                else:
                    system_displays.append(system)
            else:
                system_displays.append(system)
        
        return ", ".join(system_displays)
    
    def _get_signal_display_name(self, signal_name: str) -> str:
        """Get user-friendly signal name."""
        signal = self.signal_registry.get_signal(signal_name)
        if signal:
            return signal.display_name
        return signal_name
    
    def _get_signal_max_risk(
        self,
        signal_name: str,
        technique_results: Optional[List[TechniqueResult]],
    ) -> float:
        """Get maximum risk score for signal across techniques."""
        if not technique_results:
            return 0.0
        
        max_risk = 0.0
        for result in technique_results:
            if result.signal_name == signal_name:
                max_risk = max(max_risk, result.risk_score)
        
        return max_risk
    
    def _get_urgency_text(self, unit_health: UnitHealth) -> str:
        """Get urgency classification text."""
        urgency = unit_health.evidence_summary.get('maintenance_urgency', 'monitor')
        
        urgency_map = {
            'immediate': 'Inmediata',
            'this_week': 'Esta Semana',
            'this_month': 'Este Mes',
            'monitor': 'Monitoreo'
        }
        
        return urgency_map.get(urgency, 'Monitoreo')
