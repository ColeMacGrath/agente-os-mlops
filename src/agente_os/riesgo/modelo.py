"""Semáforo de riesgo de tres niveles (versión 3).

El nivel final es el mayor entre el clasificador entrenado y las reglas. Ni el
clasificador, ni el modelo de lenguaje, ni una palanca de costo pueden bajar un
riesgo que las reglas marcan como alto.
"""

import difflib
import pickle
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from agente_os.schemas import RiskLevel

TIPO_A_NIVEL: dict[str, RiskLevel] = {
    "open_url": RiskLevel.bajo, "open_app": RiskLevel.bajo, "copy_to_clipboard": RiskLevel.bajo,
    "save_text_file": RiskLevel.medio, "other": RiskLevel.medio,
    "delete_file": RiskLevel.alto, "send_message": RiskLevel.alto, "payment": RiskLevel.alto,
    "modify_record": RiskLevel.alto, "run_command": RiskLevel.alto,
}

ENCLITICOS = r"(?:me|te|le|lo|la|nos|les|los|las|se|selo|sela|selos|melo|mela)?"

_PALABRAS_ALTO = re.compile(
    r"\b(borr(?:a|ar|e|en|alo|ala|alos|alas|ando)|elimin\w*|delete\w*|remove|vacia\w*|pag\w*|pay\w*|transfer\w*|wire|deposit\w*|"
    r"compra\w*|purchase|envi\w*|send\w*|manda\w*|public\w*|firm\w*|sign|aprob\w*|approve\w*|"
    r"contrasena\w*|password\w*|sudo|rm -rf|ejecut\w* (un )?comando|run command|base de datos|database|"
    r"saldo|revoc\w*|cancel\w*|overwrite|sobrescrib\w*|dar de baja)\b"
)

_REGLAS_ALTO = [re.compile(p) for p in [
    rf"\b(borr|elimin|quit|tir|vaci)(a|ar|e|en|ame|ale|alo|ala|elo|ando)?{ENCLITICOS}\b",
    rf"\b(pag|deposit)(a|ar|ue|uen|ale|ame|ales)?{ENCLITICOS}\b",
    r"\b(pas|manda|envi|deposit)\w*\b.{0,30}(\$|\d+\s?mil\b|\d{3,}|pesos|varos|lana|dolares|usd|mxn|reais)",
    rf"\b(mand|envi|reenvi)(a|ar|e|en|ale|ame|aselo|aselos)?{ENCLITICOS}\b(?!.{{0,10}}\b(al archivo|a la carpeta|a mi carpeta)\b)",
    r"\b(visto bueno|luz verde)\b", r"\b(da|dar|dale|darle|de)\s+de\s+baja\b", r"\bechale la firma\b",
    rf"\b(cambi|modific|actualiz)(a|ar|ale|alo|ala)?{ENCLITICOS}\b.{{0,25}}\b(saldo|registro|base de datos|sistema|balance)\b",
    r"\b(dale|darle|hazle|haz|hacer|hagas|hazme)\s+(un |el |la |una )?(delete|payment|pay|transfer|wire|update|approve|sign|empty|run|post|cancel|revoke|send|purchase|wipe)\b",
    r"\b(empty|revoke|wipe|purge|post|publish)\b",
    r"\b(corre|correle|ejecuta|ejecutale)\b.{0,20}\b(comando|script|terminal)\b",
    r"\b(sube|subelo|subela)\b.{0,30}\b(pagina|sitio|redes|publico|publica)\b",
    # Portugués: traducción de las categorías de alto riesgo del léxico.
    r"\b(apag(?:ue|ar|a)|exclu(?:a|ir|i)|pag(?:ue|ar)|transfir(?:a|am)|transferir|envi(?:e|ar)|mand(?:e|ar)|aprov(?:e|ar)|assin(?:e|ar)|"
    r"publiqu(?:e|ar)|publicar|cancel(?:e|ar)|revogu(?:e|ar)|esvazi(?:e|ar)|sobrescrev(?:a|er))\b",
    r"\b(senha|folha de pagamento)\b.{0,20}\b(alter|mud|troqu|redefin)\w*|\b(alter|mud|troqu|redefin)\w*\b.{0,20}\b(senha)\b",
]]

_SOLO_LECTURA = re.compile(
    r"\b(sin modificar|sin cambiar|without changing|solo lectura|read[- ]only|sem alterar)\b|"
    r"\b(consulta\w*|checa\w*|chec\w*|revisa\w*|ver|muestra\w*|mostr\w*|ensena\w*|check|view|show)\b.{0,30}\b(saldo|balance)\b"
)
_BORRADOR = re.compile(r"\b(borrador|borradores|draft|drafts|rascunho|rascunhos|pay ?stubs?|pay ?slips?|pay period)\b")
_RAICES = ["elimina", "transfiere", "aprueba", "publica", "cancela", "revoca", "vacia", "firma", "modifica", "ejecuta",
           "borra", "envia", "paga", "deposita", "sobrescribe"]


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip()


def _corregir_errores(norm: str) -> str:
    salida = []
    for p in norm.split():
        if len(p) >= 5 and not any(p.startswith(r) for r in _RAICES):
            m = difflib.get_close_matches(p, _RAICES, n=1, cutoff=0.8)
            p = m[0] if m else p
        salida.append(p)
    return " ".join(salida)


def nivel_por_reglas(descripcion: str, tipo: str | None) -> tuple[RiskLevel, str]:
    por_tipo = TIPO_A_NIVEL.get(tipo, RiskLevel.medio) if tipo else RiskLevel.bajo
    if por_tipo is RiskLevel.alto:
        return por_tipo, f"tipo {tipo}"
    texto = _BORRADOR.sub(" ", _corregir_errores(normalizar(descripcion)))
    solo_lectura = bool(_SOLO_LECTURA.search(texto))
    for p in _REGLAS_ALTO:
        m = p.search(texto)
        if m:
            return RiskLevel.alto, f"regla '{m.group(0)}'"
    m = _PALABRAS_ALTO.search(texto)
    if m and not (solo_lectura and m.group(0) == "saldo"):
        return RiskLevel.alto, f"palabra clave '{m.group(0)}'"
    return por_tipo, f"tipo {tipo}" if tipo else "sin coincidencias"


def construir_pipeline(C: float = 10.0, semilla: int = 42) -> Pipeline:
    rasgos = FeatureUnion([
        ("palabras", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True)),
        ("caracteres", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), strip_accents="unicode", sublinear_tf=True, max_df=0.5)),
    ])
    return Pipeline([("rasgos", rasgos),
                     ("clf", LogisticRegression(max_iter=3000, C=C, class_weight="balanced", random_state=semilla))])


@dataclass
class Decision:
    nivel: RiskLevel
    nivel_modelo: RiskLevel
    confianza: float
    probabilidades: dict[str, float]
    nivel_regla: RiskLevel
    motivo_regla: str

    @property
    def fuentes(self) -> dict[str, str]:
        return {"modelo": self.nivel_modelo.value, "reglas": self.nivel_regla.value, "motivo_regla": self.motivo_regla}


class SemaforoRiesgo:
    def __init__(self, ruta_modelo: Path):
        with open(ruta_modelo, "rb") as f:
            art = pickle.load(f)
        self.pipeline = art["pipeline"]
        self.version: str = art["version"]
        self.metricas: dict = art.get("metricas", {})

    def clasificar_lote(self, descripciones: list[str], tipos: list[str | None] | None = None) -> list[Decision]:
        if not descripciones:
            return []
        tipos = tipos or [None] * len(descripciones)
        probas = self.pipeline.predict_proba([d[:500] for d in descripciones])
        clases = list(self.pipeline.classes_)
        salida = []
        for desc, tipo, fila in zip(descripciones, tipos, probas):
            p = {c: round(float(v), 4) for c, v in zip(clases, fila)}
            mejor = max(p, key=p.get)
            modelo = RiskLevel(mejor)
            regla, motivo = nivel_por_reglas(desc, tipo)
            salida.append(Decision(RiskLevel.highest(modelo, regla), modelo, p[mejor], p, regla, motivo))
        return salida

    def clasificar(self, descripcion: str, tipo: str | None = None) -> Decision:
        return self.clasificar_lote([descripcion], [tipo])[0]
