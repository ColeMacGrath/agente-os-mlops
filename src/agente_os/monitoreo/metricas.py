"""Métricas de operación expuestas en /metrics (formato Prometheus).

Cubre las cuatro familias del documento de operación: servicio (latencia,
errores, disponibilidad), costo (tokens y USD por modelo), seguridad (bloqueos,
PII en servidor, modo degradado) y calidad/equidad (idioma de entrada para
detectar drift, niveles de riesgo).
"""

import re

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

REGISTRO = CollectorRegistry()

SOLICITUDES = Counter("agente_solicitudes_total", "Solicitudes por endpoint y código", ["endpoint", "codigo"], registry=REGISTRO)
LATENCIA = Histogram("agente_latencia_segundos", "Latencia de extremo a extremo", ["endpoint"], registry=REGISTRO,
                     buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 4, 6, 8, 10, 12, 16, 20, 30, 60))
TOKENS = Counter("agente_tokens_total", "Tokens consumidos por modelo y tipo", ["modelo", "tipo"], registry=REGISTRO)
COSTO = Counter("agente_costo_usd_total", "Costo acumulado de la API del modelo", ["modelo"], registry=REGISTRO)
RUTA = Counter("agente_ruta_total", "Tareas por complejidad y modelo", ["complejidad", "modelo"], registry=REGISTRO)
CACHE_PLANES = Counter("agente_cache_planes_total", "Resultado del caché de planes", ["resultado"], registry=REGISTRO)
BLOQUEOS = Counter("agente_bloqueos_total", "Ejecuciones canceladas por barrera", ["motivo"], registry=REGISTRO)
PII_SERVIDOR = Counter("agente_pii_servidor_total", "Datos personales que llegaron sin enmascarar al servidor", ["tipo"], registry=REGISTRO)
DEGRADADO = Counter("agente_modo_degradado_total", "Respuestas servidas por el planificador determinista", registry=REGISTRO)
RIESGO = Counter("agente_acciones_riesgo_total", "Acciones planeadas por nivel de riesgo", ["nivel"], registry=REGISTRO)
IDIOMA = Counter("agente_idioma_entrada_total", "Idioma estimado de la tarea (drift de población)", ["idioma"], registry=REGISTRO)
SOMBRA = Counter("agente_inyeccion_sombra_total", "Concordancia entre el campeón (reglas) y el clasificador en sombra",
                 ["resultado"], registry=REGISTRO)
INFO = Gauge("agente_build_info", "Versión del servicio y de los modelos", ["servicio", "riesgo", "inyeccion", "revision"], registry=REGISTRO)

_PT = re.compile(r"\b(você|voce|não|nao|para o|para a|do|da|das|dos|uma|um|está|esta|são|lembrete|fatura|relatório|planilha|senha|ção|ções)\b", re.I)
_EN = re.compile(r"\b(the|and|please|with|to|for|this|from|your|you|invoice|report|meeting|send|open|copy)\b", re.I)
_ES = re.compile(r"\b(el|la|los|las|por|para|con|del|que|una|un|factura|reporte|junta|envía|abre|copia|favor)\b", re.I)


def estimar_idioma(texto: str) -> str:
    """Heurística ligera por palabras función; suficiente para vigilar la mezcla de idiomas."""
    pt, en, es = len(_PT.findall(texto)), len(_EN.findall(texto)), len(_ES.findall(texto))
    if max(pt, en, es) == 0:
        return "desconocido"
    if pt >= es and pt >= en and re.search(r"[ãõç]|você|voce|não|nao", texto, re.I):
        return "pt"
    if en > es and en >= pt:
        return "en"
    return "es"
