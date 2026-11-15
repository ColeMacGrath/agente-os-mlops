"""Validador de inyección de prompts (versión 3).

Dos capas que se combinan:

1. Reglas deterministas (Fase II + mitigaciones de la Actividad 9): patrones en
   español, inglés y portugués sobre texto normalizado y desofuscado, con
   excepciones para roles humanos y material de capacitación.
2. Clasificador multilingüe aprendido (Fase III): n-gramas de caracteres +
   regresión logística, entrenado con un corpus sintético en cuatro idiomas y
   variantes ofuscadas. Resuelve el pendiente de la Actividad 9: las reglas no
   generalizaban a frases nuevas en portugués.

Decisión (v3.1): el clasificador bloquea solo con su umbral; una regla bloquea si el
clasificador la corrobora con una probabilidad mínima. Así se cancela la ejecución
antes de llamar al modelo de lenguaje. Si el texto va dirigido a una
persona (asistente o agente humano) o es material de capacitación, el umbral
del clasificador sube; los umbrales se calibran con la partición dev.
"""

import pickle
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

_ANCHO_CERO = re.compile(r"[​-‏⁠﻿]")
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
_AGENTE = r"(asistente|assistente|agente|ia|ai|llm|assistant|agent|bot|robot|modelo|model|chatbot)"

# Reglas idénticas a la versión mitigada de la Actividad 9 (Fase II + portugués,
# exfiltración por URL y cambio de rol). No se ajustaron con los conjuntos de
# evaluación de la Fase III: lo nuevo lo aporta el clasificador aprendido.
# (patrón, peso, es_dirigido_al_agente)
_PATRONES: list[tuple[str, float, bool]] = [
    (r"\b(ignora|olvida|omite|descarta|ignore|forget|disregard|override)\b.{0,40}\b(instruccion\w*|indicacion\w*|reglas|tarea|solicitud|lo que te pidio|lo anterior|todo|everything|above|instructions|rules|prompt|guidelines|task|request|safety)", 0.8, False),
    (r"\b(nuevas|new|updated|actualizadas)\s+(instrucciones|instructions|orders|ordenes|task|tarea)\b|\b(your new task|tu nueva tarea)\b", 0.6, False),
    (r"\b(system prompt|prompt del sistema|instrucciones del sistema|system override|developer mode|modo desarrollador|jailbreak)\b", 0.7, False),
    (r"\b(ahora eres|a partir de ahora eres|you are now|from now on you are|act as|actua como|pretend you are|finge que eres)\b", 0.4, False),
    (rf"\b(para|for|to|attention|atencion|dear|querido|querida|hey|hola|nota para|mensaje para|a cualquier|any)\s+(el |la |the |un |una |an? )?{_AGENTE}\b", 0.5, True),
    (rf"^\W*{_AGENTE}(\s+(de ia|de ai|virtual|automatico|automatizado))?\s*[:,]", 0.5, True),
    (rf"\b(si eres|if you are|cuando|when|si)\s+(un |una |an? )?{_AGENTE}\b", 0.5, True),
    (rf"\b{_AGENTE}\b.{{0,40}}\b(debes|debe|deberia|tienes que|tiene que|must|should|shall|have to|necesitas)\b", 0.5, True),
    (r"\b(te autoriz\w*|tienes permiso|usuario autoriz\w*|authorized you|you are authorized|you have permission)\b", 0.5, False),
    (r"\b(transfiere|transferir|deposita|envia|paga|wire|transfer|send|pay)\b.{0,40}\b(fondos|dinero|pesos|dolares|usd|mxn|funds|money|bitcoin|btc|\$\s?\d)", 0.4, False),
    (r"\b(borra|elimina|delete|remove|wipe|formatea|format)\b.{0,30}\b(todos|todo|all|every|entire|disco|disk|archivos|files|carpeta|folder|base de datos|database|logs|respaldos)\b", 0.5, False),
    (r"rm\s+-rf|del\s+/[sq]|format\s+c:|sudo\s+", 0.7, False),
    (r"\b(envia|manda|comparte|revela|escribe|ingresa|send|share|reveal|leak|forward|email|write|type|exfiltra|exfiltrate)\b.{0,40}\b(contrasena|contrasenas|password|passwords|credenciales|credentials|token|tokens|api key|llave|claves)\b", 0.7, False),
    (r"\b(no le digas|sin avisar|no informes|sin que el usuario|sin preguntar|do not tell|don't tell|without telling|without the user|silently|en secreto)\b", 0.6, False),
    (r"\b(confirma automaticamente|aprueba automaticamente|auto-?approve|skip confirmation|no need to confirm|omite la confirmacion|sin confirmacion)\b", 0.6, False),
    (r"<\s*/?\s*(system|instructions|admin)\s*>|\[\s*/?\s*(system|inst)\s*\]|###\s*(system|instruction)", 0.7, False),
    # Portugués (Actividad 9)
    (r"\b(ignore|esqueca|desconsidere)\b.{0,40}\b(instrucoes|regras|tudo|o que foi pedido)\b", 0.8, False),
    (r"\b(novas|nova)\s+(instrucoes|ordens|tarefa)\b(?!\s+de\s+(reembolso|pagamento|uso))", 0.6, False),
    (r"\b(envie|mande|compartilhe|revele|encaminhe)\b.{0,40}\b(senha|senhas|credenciais|token|e-?mails?)\b", 0.7, False),
    (r"\b(transfira|pague|deposite|compre)\b.{0,40}\b(r\$|reais|fundos|dinheiro|cartoes|cartao)", 0.5, False),
    (r"\b(apague|exclua|delete)\b.{0,30}\b(todos|tudo|arquivos|pasta)\b", 0.5, False),
    (r"\b(aprove|confirme)\s+automaticamente\b|\bsem (avisar|perguntar)\b", 0.6, False),
    (r"\b(a partir de agora|agora) voce e\b", 0.4, False),
    (r"\b(para|ao|a) (o |a )?(assistente|agente|ia)\b(?!\s+(da|de|do)\s+(diretoria|vendas|administrativ))", 0.5, True),
    (r"\bse voce (e|for) (um |uma )?(agente|assistente|ia)\b", 0.5, True),
    # Exfiltración por URL y cambio de rol (Actividad 9)
    (r"\b(abre|abra|open|visita|visit)\s+https?://\S+\?\w*=", 0.6, False),
    (r"\b(eres|you are|you're|voce e)\s+(el |the |o )?(administrador|administrator|admin)\b", 0.4, False),
]
_COMPILADOS = [(re.compile(p, re.M), w, d) for p, w, d in _PATRONES]

_ROL_HUMANO = re.compile(
    r"\b(asistente|assistant|assistente|agente|agent)\s+(de\s+|da\s+|do\s+)?(direccion|diretoria|administrativ\w*|ejecutiv\w*|executive|admin|ventas|vendas|sales|servicio|service|soporte|virtual del banco|virtual)\b|"
    r"\b(executive|administrative|admin|sales|virtual)\s+(assistant|agent)\b|"
    r"\b(hola|hi|ola|ola,)\s+agente?\b,\s+(tu|your|seu)\s+cliente\b"
)
_CAPACITACION = re.compile(
    r"\b(manual|handbook|curso|course|capacitacion|training|politica|policy)\b.{0,40}\b(nunca|never|el atacante|the attacker|o atacante|debe responder|should reply|deve responder)\b|"
    r"\bnunca (compartas|hagas share|compartilhe)\b|\bnever share\b"
)
UMBRAL_REGLAS = 0.5


def normalizar(texto: str) -> str:
    t = _ANCHO_CERO.sub("", texto)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.lower())


def desofuscar(texto: str) -> str:
    t = normalizar(texto)
    t = re.sub(r"(?<=\w)[.\-_*](?=\w)", "", t)
    t = re.sub(r"\b(\w) (?=\w\b)", r"\1", t)
    t = re.sub(r"(?<=\w) (?=\w(\s|$))", "", t)
    if re.search(r"[a-z]\d|\d[a-z]", t):
        t = re.sub(r"\b[\w$@]+\b", lambda m: m.group(0).translate(_LEET) if re.search(r"[a-z]", m.group(0)) else m.group(0), t)
    return t.replace("sys tem", "system").replace("h t t p s", "https")


def puntaje_reglas(texto: str) -> tuple[float, list[str]]:
    if not texto:
        return 0.0, []
    mejor, coincidencias_mejor = 0.0, []
    for t in {normalizar(texto), desofuscar(texto)}:
        humano = bool(_ROL_HUMANO.search(t)) or bool(_CAPACITACION.search(t))
        score, coincidencias = 0.0, []
        for patron, peso, dirigido in _COMPILADOS:
            m = patron.search(t)
            if not m:
                continue
            if humano and (dirigido or _CAPACITACION.search(t)):
                continue
            # Excepción de la Actividad 9: "nuevas instrucciones de reembolso/pago/uso" es un aviso de proceso.
            if peso == 0.6 and re.search(r"(instrucciones|instructions)\s+de\s+(reembolso|pago|uso)", t):
                continue
            score += peso
            coincidencias.append(m.group(0)[:80])
        if _ANCHO_CERO.search(texto):
            score += 0.3
            coincidencias.append("caracteres invisibles")
        if min(score, 1.0) > mejor:
            mejor, coincidencias_mejor = min(score, 1.0), coincidencias
    return round(mejor, 3), coincidencias_mejor


@dataclass
class ResultadoInyeccion:
    detectado: bool
    puntaje: float
    puntaje_reglas: float
    puntaje_modelo: float
    coincidencias: list[str] = field(default_factory=list)
    decision_sombra: bool | None = None  # decisión del clasificador cuando opera en modo sombra


class DetectorInyeccion:
    """Combina reglas y clasificador. Sin clasificador cargado, opera solo con reglas."""

    def __init__(self, ruta_modelo: Path | None = None, umbral_modelo: float = 0.5, umbral_contexto_humano: float = 0.9,
                 umbral_corroboracion: float = 0.0, modo: str = "aplicar"):
        """modo='aplicar': el ensamble decide. modo='sombra': deciden solo las reglas (campeón) y el
        ensamble se calcula y se reporta sin bloquear, hasta que pase sus compuertas."""
        self.modo = modo
        self.clasificador = None
        self.version = "reglas-3.0"
        self.umbral_modelo = umbral_modelo
        self.umbral_contexto_humano = umbral_contexto_humano
        self.umbral_corroboracion = umbral_corroboracion
        if ruta_modelo and Path(ruta_modelo).exists():
            with open(ruta_modelo, "rb") as f:
                art = pickle.load(f)
            self.clasificador = art["pipeline"]
            self.version = art["version"]
            self.umbral_modelo = art.get("umbral", umbral_modelo)
            self.umbral_contexto_humano = art.get("umbral_contexto_humano", umbral_contexto_humano)
            self.umbral_corroboracion = art.get("umbral_corroboracion", umbral_corroboracion)

    @staticmethod
    def contexto_humano(texto: str) -> bool:
        """Texto dirigido a una persona (asistente o agente humano) o material de capacitación."""
        t = desofuscar(texto)
        return bool(_ROL_HUMANO.search(t)) or bool(_CAPACITACION.search(t))

    def decidir(self, puntaje_reglas: float, prob_modelo: float, humano: bool) -> bool:
        """v3.1: una regla bloquea solo si el clasificador la corrobora con una probabilidad mínima.

        En la v3.0 cualquier regla bloqueaba sola; el análisis de errores mostró que todos los
        falsos positivos venían de reglas que el clasificador no respaldaba (probabilidad < 0.4).
        Sin clasificador cargado, las reglas siguen bloqueando solas.
        """
        umbral = self.umbral_contexto_humano if humano else self.umbral_modelo
        corroborada = self.clasificador is None or prob_modelo >= self.umbral_corroboracion
        return (puntaje_reglas >= UMBRAL_REGLAS and corroborada) or prob_modelo >= umbral

    def probabilidad_modelo(self, textos: list[str]) -> list[float]:
        if self.clasificador is None:
            return [0.0] * len(textos)
        entradas = [desofuscar(t) for t in textos]
        return [float(p[1]) for p in self.clasificador.predict_proba(entradas)]

    def detectar(self, texto: str) -> ResultadoInyeccion:
        if not texto:
            return ResultadoInyeccion(False, 0.0, 0.0, 0.0)
        reglas, coincidencias = puntaje_reglas(texto)
        modelo = self.probabilidad_modelo([texto])[0]
        ensamble = self.decidir(reglas, modelo, self.contexto_humano(texto))
        if self.modo == "sombra" and self.clasificador is not None:
            return ResultadoInyeccion(reglas >= UMBRAL_REGLAS, reglas, reglas, round(modelo, 3), coincidencias, decision_sombra=ensamble)
        if ensamble and reglas < UMBRAL_REGLAS:
            coincidencias = coincidencias + [f"clasificador {modelo:.2f}"]
        return ResultadoInyeccion(ensamble, round(max(reglas, modelo), 3), reglas, round(modelo, 3), coincidencias)
