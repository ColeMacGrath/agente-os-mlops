"""Router de complejidad y política de imagen (decisiones D4 y D6 de la Actividad 9).

Reglas baratas que corren antes de elegir el modelo. El umbral de longitud de la
tarea es configurable porque la simulación de operación mostró que es la
palanca que mueve la mezcla de modelos (ver docs/adr/0004-ajuste-router.md).
"""

import re
from dataclasses import dataclass

_PASOS = re.compile(r"\b(y luego|despu[eé]s|luego|a continuaci[oó]n|then|and then|depois|em seguida)\b", re.I)
_VERBOS = re.compile(
    r"\b(resume|compara|analiza|concilia|identifica|prepara|redacta|env[ií]a|revisa|detecta|busca|exporta|agenda|guarda|paga|abre|copia|extrae|"
    r"summarize|compare|analyze|reconcile|prepare|draft|send|review|export|schedule|save|pay|open|copy|extract|"
    r"resuma|analise|concilie|prepare|redija|envie|revise|exporte|agende|salve|pague|abra|copie|extraia)\w*",
    re.I,
)
# Participios (conciliado, revisada, exportados...) describen un estado, no una acción a ejecutar.
_PARTICIPIO = re.compile(r"\w+(ado|ada|ados|adas|ido|ida|idos|idas)$", re.I)
MODELO_POR_COMPLEJIDAD = {"simple": "claude-haiku-5-5", "media": "claude-sonnet-5-5", "compleja": "claude-opus-5-5"}


@dataclass(frozen=True)
class Ruta:
    complejidad: str
    modelo: str
    enviar_imagen: bool


class Router:
    def __init__(self, largo_tarea_media: int = 70, largo_pantalla_media: int = 6000, modelo_fijo: str | None = None,
                 excluir_participios: bool = False):
        self.excluir_participios = excluir_participios  # ver docs/adr/0004-ajuste-router.md
        self.largo_tarea_media = largo_tarea_media
        self.largo_pantalla_media = largo_pantalla_media
        self.modelo_fijo = modelo_fijo  # emula la arquitectura previa (un solo modelo, imagen siempre)

    def complejidad(self, task: str, screen_text: str, tiene_imagen: bool) -> str:
        pasos = len(_PASOS.findall(task))
        verbos = [m.group(0) for m in _VERBOS.finditer(task)]
        if self.excluir_participios:
            verbos = [v for v in verbos if not _PARTICIPIO.match(v)]
        verbos = len(verbos)
        if pasos >= 1 or verbos >= 3:
            return "compleja"
        if verbos == 2 or tiene_imagen or len(task) > self.largo_tarea_media or len(screen_text) > self.largo_pantalla_media:
            return "media"
        return "simple"

    def decidir(self, task: str, screen_text: str, tiene_imagen: bool) -> Ruta:
        c = self.complejidad(task, screen_text or "", tiene_imagen)
        if self.modelo_fijo:
            return Ruta(c, self.modelo_fijo, tiene_imagen)
        # OCR primero: la imagen solo viaja si la tarea es compleja o la pantalla no trae texto suficiente.
        enviar = tiene_imagen and (c == "compleja" or len(screen_text or "") < 40)
        return Ruta(c, MODELO_POR_COMPLEJIDAD[c], enviar)
