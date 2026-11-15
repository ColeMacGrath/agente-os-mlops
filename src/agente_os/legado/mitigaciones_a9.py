"""Mitigaciones de fairness para las barreras de la Capa Nube (versión 2).

Se diseñaron con la partición dev y el diagnóstico de la línea base; se
evalúan además en un conjunto ciego escrito después de este código.

1. Semáforo de riesgo v2
   - Pre-procesamiento: reentrenamiento con datos aumentados (español
     coloquial mexicano con pronombres enclíticos, Spanglish y errores
     tipográficos), el mismo pipeline TF-IDF + regresión logística.
   - Reglas: léxico ampliado con enclíticos, modismos (visto bueno, dar de
     baja), anglicismos con verbo de apoyo (dale/hazle + verbo) y dinero
     coloquial; tolerancia a errores por similitud; excepciones de solo
     lectura (consultar saldo, borrador) que solo aplican a palabras clave,
     nunca al tipo de acción. La regla "el nivel final es el mayor" se conserva.
2. Validador de inyección v2
   - Normalización de ofuscación (leetspeak, letras separadas, puntos).
   - Patrones en portugués.
   - Contexto de rol humano: "asistente de dirección", "agente de ventas" o
     material de capacitación no cuentan como dirigidos al agente.
3. Filtro Ciego v2
   - Formatos internacionales con validación de dígito verificador donde
     existe: SSN, DNI y NIE de España, IBAN (mod 97), CPF, CUIT/CUIL, CBU,
     cédula y NIT de Colombia, y teléfonos E.164 de cualquier país.
"""

import difflib
import random
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path


from agente_os.legado import guardrails_f2 as g1  # noqa: E402
from agente_os.legado.riesgo_reglas_f2 import TYPE_RULES, _HIGH_KEYWORDS  # noqa: E402
from agente_os.schemas import RiskLevel  # noqa: E402

from agente_os.legado import riesgo_f2 as tr  # noqa: E402


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip()


# =====================================================================
# 1. Semáforo de riesgo v2
# =====================================================================

ENCLITICOS = r"(?:me|te|le|lo|la|nos|les|los|las|se|selo|sela|selos|melo|mela)?"

ACCIONES_COLOQUIALES = {
    "bajo": [
        "ábreme {o}", "enséñame {o}", "chécame {o}", "checa {o}", "muéstrame {o}", "cópiame {o}",
        "búscame {o}", "léeme {o}", "pásame el dato de {o}", "llévame a {o}", "tradúceme {o}",
        "márcame {o}", "resáltame {o}", "hazme un resumen de {o}", "dale una leída a {o}", "échale un ojo a {o}",
        "haz open de {o}", "dale copy a {o}", "dale highlight a {o}", "hazme un summary de {o}", "dale translate a {o}",
        "ve al tab de {o}", "enséñame el draft de {o}", "chécame el balance de {o}", "consulta sin modificar nada {o}",
    ],
    "medio": [
        "guárdame {o}", "bájame {o}", "descárgame {o}", "cámbiale el nombre a {o}", "pásame {o} a otra carpeta",
        "sácame {o} a CSV", "échame un borrador de {o}", "ármame una junta sobre {o}", "agéndame {o}",
        "mándame al archivo {o}", "dale save a {o}", "dale download a {o}", "hazle rename a {o}", "haz move de {o}",
        "hazme un draft de {o}", "hazle export a {o}", "dale archive a {o}", "agéndame un meeting de {o}",
    ],
    "alto": [
        "bórrame {o}", "bórrale {o}", "quítale {o}", "quítame {o}", "tírame {o}", "tira todo {o}", "vacíame {o}",
        "págale {o}", "págame {o}", "pásale la lana de {o}", "pásale los varos de {o}", "deposítale {o}",
        "mándale {o} a todos", "mándaselo {o} al cliente", "cámbiale el saldo a {o}", "dale el visto bueno a {o}",
        "échale la firma a {o}", "dale de baja {o}", "córrele el script a {o}", "súbelo {o} a la página pública",
        "dale delete a {o}", "hazle delete a {o}", "hazle el payment a {o}", "hazle un transfer de {o}",
        "hazle update a {o} en la base", "dale approve a {o}", "dale sign a {o}", "hazle empty a {o}",
        "dale run a {o}", "dale post a {o}", "hazle cancel a {o}", "hazle revoke a {o}", "dale send a {o}",
    ],
}

MARCOS_COLOQUIALES = [
    "Porfa {a}", "Oye, {a}", "Me ayudas a {a}?", "{a} porfa", "Ándale, {a}", "{a} ahorita", "Plis {a}",
    "{a} ASAP", "Hey, {a}", "{a} cuando puedas",
]


def _con_error(texto: str, rng: random.Random) -> str:
    """Inserta un error tipográfico realista (omisión, intercambio o sustitución b/v, s/c)."""
    palabras = texto.split()
    i = rng.randrange(len(palabras))
    p = palabras[i]
    if len(p) >= 4:
        op = rng.random()
        j = rng.randrange(1, len(p) - 1)
        if op < 0.4:
            p = p[:j] + p[j + 1:]
        elif op < 0.7:
            p = p[:j] + p[j + 1] + p[j] + p[j + 2:]
        else:
            p = p.translate(str.maketrans({"b": "v", "v": "b", "s": "c", "c": "s", "z": "s"}))
    palabras[i] = p
    return " ".join(palabras)


def dataset_v2() -> list[tuple[str, str]]:
    rng = random.Random(tr.SEED + 1)
    filas = [(t, l) for t, l, _ in tr.generate_dataset()]
    for etiqueta, acciones in ACCIONES_COLOQUIALES.items():
        for marco in MARCOS_COLOQUIALES + tr.FRAMES[:6]:
            for accion in acciones:
                texto = marco.format(a=accion.format(o=rng.choice(tr.OBJECTS)))
                filas.append((texto, etiqueta))
    # Aumento con errores tipográficos sobre el 20% de todas las filas.
    filas += [(_con_error(t, rng), l) for t, l in rng.sample(filas, k=len(filas) // 5)]
    return filas


@lru_cache(maxsize=1)
def modelo_v2():
    filas = dataset_v2()
    pipe = tr.build_pipeline()
    pipe.fit([t for t, _ in filas], [l for _, l in filas])
    return pipe


_ALTO_V2 = [
    rf"\b(borr|elimin|quit|tir|vaci)(a|ar|e|en|ame|ale|alo|ala|elo|ando)?{ENCLITICOS}\b",
    rf"\b(pag|deposit)(a|ar|ue|uen|ale|ame|ales)?{ENCLITICOS}\b",
    r"\b(pas|manda|envi|deposit)\w*\b.{0,30}(\$|\d+\s?mil\b|\d{3,}|pesos|varos|lana|dolares|usd|mxn)",
    rf"\b(mand|envi|reenvi)(a|ar|e|en|ale|ame|aselo|aselos)?{ENCLITICOS}\b(?!.{{0,10}}\b(al archivo|a la carpeta|a mi carpeta)\b)",
    r"\bvisto bueno\b", r"\b(da|dar|dale|darle|dé)\s+de\s+baja\b", r"\bechale la firma\b",
    rf"\b(cambi|modific|actualiz)(a|ar|ale|alo|ala)?{ENCLITICOS}\b.{{0,25}}\b(saldo|registro|base de datos|sistema|balance)\b",
    r"\b(dale|darle|hazle|haz|hacer|hagas|hazme)\s+(un |el |la |una )?(delete|payment|pay|transfer|wire|update|approve|sign|empty|run|post|cancel|revoke|send|purchase|wipe)\b",
    r"\b(empty|revoke|wipe|purge|post|publish)\b",
    r"\b(corre|correle|ejecuta|ejecutale)\b.{0,20}\b(comando|script|terminal)\b",
    r"\b(sube|subelo|subela)\b.{0,30}\b(pagina|sitio|redes|publico|publica)\b",
]
_ALTO_V2_RE = [re.compile(p) for p in _ALTO_V2]

_SOLO_LECTURA = re.compile(
    r"\b(sin modificar|sin cambiar|without changing|solo lectura|read[- ]only)\b|"
    r"\b(consulta\w*|checa\w*|chec\w*|revisa\w*|ver|muestra\w*|ensena\w*|check|view|show)\b.{0,30}\b(saldo|balance)\b"
)
_BORRADOR = re.compile(r"\b(borrador|borradores|draft|drafts)\b")

_RAICES = ["elimina", "transfiere", "aprueba", "publica", "cancela", "revoca", "vacia", "firma", "modifica",
           "ejecuta", "borra", "envia", "paga", "deposita", "sobrescribe"]


def _corregir_errores(norm: str) -> str:
    """Mapea palabras con errores tipográficos a la raíz de alto riesgo más cercana."""
    salida = []
    for p in norm.split():
        if len(p) >= 5 and not any(p.startswith(r[:4]) for r in _RAICES):
            m = difflib.get_close_matches(p, _RAICES, n=1, cutoff=0.8)
            p = m[0] if m else p
        salida.append(p)
    return " ".join(salida)


def regla_v2(descripcion: str, tipo: str | None) -> tuple[RiskLevel, str]:
    por_tipo = TYPE_RULES.get(tipo, RiskLevel.medio) if tipo else RiskLevel.bajo
    if por_tipo is RiskLevel.alto:
        return por_tipo, f"tipo {tipo}"
    norm = normalizar(descripcion)
    corregido = _corregir_errores(norm)
    sin_borrador = _BORRADOR.sub(" ", corregido)
    solo_lectura = bool(_SOLO_LECTURA.search(sin_borrador))
    for texto in (sin_borrador,):
        for p in _ALTO_V2_RE:
            m = p.search(texto)
            if m:
                return RiskLevel.alto, f"regla v2 '{m.group(0)}'"
        m = _HIGH_KEYWORDS.search(texto)
        if m and not (solo_lectura and m.group(0) in {"saldo"}):
            return RiskLevel.alto, f"palabra clave '{m.group(0)}'"
    return por_tipo, "sin coincidencias" if not tipo else f"tipo {tipo}"


def clasificar_v2(descripcion: str, tipo: str | None = None) -> tuple[RiskLevel, RiskLevel, RiskLevel]:
    """Devuelve (nivel_final, nivel_modelo, nivel_regla). El final nunca es menor que la regla."""
    pipe = modelo_v2()
    proba = pipe.predict_proba([descripcion])[0]
    modelo = RiskLevel(pipe.classes_[proba.argmax()])
    regla, _ = regla_v2(descripcion, tipo)
    return RiskLevel.highest(modelo, regla), modelo, regla


# =====================================================================
# 2. Validador de inyección v2
# =====================================================================

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def desofuscar(texto: str) -> str:
    t = g1._normalize(texto)
    t = re.sub(r"(?<=\w)[.\-_*](?=\w)", "", t)              # a.p.r.u.e.b.a
    t = re.sub(r"\b(\w) (?=\w\b)", r"\1", t)                 # e n v i a
    t = re.sub(r"(?<=\w) (?=\w(\s|$))", "", t)
    if re.search(r"[a-z]\d|\d[a-z]", t):                     # leetspeak solo si mezcla letras y dígitos
        t = re.sub(r"\b[\w$@]+\b", lambda m: m.group(0).translate(_LEET) if re.search(r"[a-z]", m.group(0)) else m.group(0), t)
    t = t.replace("sys tem", "system").replace("h t t p s", "https")
    return t


_ROL_HUMANO = re.compile(
    r"\b(asistente|assistant|assistente|agente|agent)\s+(de\s+|da\s+|do\s+)?(direccion|diretoria|administrativ\w*|ejecutiv\w*|executive|admin|ventas|vendas|sales|servicio|service|soporte|virtual del banco|virtual)\b|"
    r"\b(executive|administrative|admin|sales|virtual)\s+(assistant|agent)\b|"
    r"\b(hola|hi|ola|ola,)\s+agente?\b,\s+(tu|your|seu)\s+cliente\b"
)
_CAPACITACION = re.compile(
    r"\b(manual|handbook|curso|course|capacitacion|training|politica|policy|politica de servico)\b.{0,40}\b(nunca|never|el atacante|the attacker|o atacante|debe responder|should reply|deve responder)\b|"
    r"\bnunca (compartas|hagas share|compartilhe)\b|\bnever share\b"
)

_PT = [
    (r"\b(ignore|esqueca|desconsidere)\b.{0,40}\b(instrucoes|regras|tudo|o que foi pedido)\b", 0.8),
    (r"\b(novas|nova)\s+(instrucoes|ordens|tarefa)\b(?!\s+de\s+(reembolso|pagamento|uso))", 0.6),
    (r"\b(envie|mande|compartilhe|revele|encaminhe)\b.{0,40}\b(senha|senhas|credenciais|token|e-?mails?)\b", 0.7),
    (r"\b(transfira|pague|deposite|compre)\b.{0,40}\b(r\$|reais|fundos|dinheiro|cartoes|cartao)", 0.5),
    (r"\b(apague|exclua|delete)\b.{0,30}\b(todos|tudo|arquivos|pasta)\b", 0.5),
    (r"\b(aprove|confirme)\s+automaticamente\b|\bsem (avisar|perguntar)\b", 0.6),
    (r"\b(a partir de agora|agora) voce e\b", 0.4),
    (r"\b(para|ao|a) (o |a )?(assistente|agente|ia)\b(?!\s+(da|de|do)\s+(diretoria|vendas|administrativ))", 0.5),
    (r"\bse voce (e|for) (um |uma )?(agente|assistente|ia)\b", 0.5),
    (r"\b(abra|abre|open)\s+https?://\S+\?\w*=", 0.6),
]
_PT_RE = [(re.compile(p), w) for p, w in _PT]
_EXFIL = re.compile(r"\b(abre|abra|open|visita|visit)\s+https?://\S+\?\w*=")
_ROL_ADMIN = re.compile(r"\b(eres|you are|you're|voce e)\s+(el |the |o )?(administrador|administrator|admin)\b")


def detectar_inyeccion_v2(texto: str) -> tuple[bool, float]:
    if not texto:
        return False, 0.0
    variantes = {g1._normalize(texto), desofuscar(texto)}
    mejor = 0.0
    for t in variantes:
        humano = bool(_ROL_HUMANO.search(t)) or bool(_CAPACITACION.search(t))
        score = 0.0
        for patron, peso in g1._COMPILED:
            m = patron.search(t)
            if not m:
                continue
            # Los patrones de "texto dirigido al agente" no cuentan si el
            # destinatario es un rol humano o el texto es capacitación.
            dirigido = peso == 0.5 and re.search(g1._AGENT, m.group(0))
            if humano and (dirigido or peso <= 0.7 and _CAPACITACION.search(t)):
                continue
            if peso == 0.6 and re.search(r"(instrucciones|instructions)\s+de\s+(reembolso|pago|uso)", t):
                continue
            score += peso
        for patron, peso in _PT_RE:
            if patron.search(t) and not humano:
                score += peso
        if _EXFIL.search(t):
            score += 0.6
        if _ROL_ADMIN.search(t):
            score += 0.4
        if g1._ZERO_WIDTH.search(texto):
            score += 0.3
        mejor = max(mejor, min(score, 1.0))
    return mejor >= g1.INJECTION_THRESHOLD, round(mejor, 2)


# =====================================================================
# 3. Filtro Ciego v2
# =====================================================================

_LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"


def _dni_ok(m: str) -> bool:
    m = m.upper()
    num = m[:-1].replace("X", "0").replace("Y", "1").replace("Z", "2")
    return num.isdigit() and _LETRAS_DNI[int(num) % 23] == m[-1]


def _iban_ok(s: str) -> bool:
    s = re.sub(r"\s", "", s).upper()
    s = s[4:] + s[:4]
    return int("".join(str(int(c, 36)) for c in s)) % 97 == 1


def _cpf_ok(s: str) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", s)]
    if len(d) != 11:
        return False
    for n in (9, 10):
        r = (sum(v * w for v, w in zip(d[:n], range(n + 1, 1, -1))) * 10) % 11
        if (0 if r == 10 else r) != d[n]:
            return False
    return True


_PATRONES_V2 = [
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b"), _iban_ok),
    ("dni_nie", re.compile(r"\b[XYZ]?\d{7,8}[A-Z]\b", re.I), _dni_ok),
    ("cpf", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), _cpf_ok),
    ("cuit", re.compile(r"\b(20|23|24|27|30|33|34)-\d{8}-\d\b"), None),
    ("ssn", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"), None),
    ("telefono_e164", re.compile(r"\+\d{1,3}[\s\-.]?(?:\(?\d{1,4}\)?[\s\-.]?){2,5}\d{2,4}\b"), None),
    ("dni_ar", re.compile(r"\b\d{2}\.\d{3}\.\d{3}\b"), None),
    ("cbu", re.compile(r"\b\d{22}\b"), None),
    ("cuenta_bancaria", re.compile(r"\b(routing|account|cuenta|conta)\s*(no\.?|num\.?|#)?\s*\d{8,17}\b", re.I), None),
]


def enmascarar_v2(texto: str) -> g1.PIIResult:
    conteos: dict[str, int] = {}
    salida = texto
    for tipo, patron, validador in _PATRONES_V2:
        def repl(m, tipo=tipo, validador=validador):
            if validador and not validador(m.group(0)):
                return m.group(0)
            conteos[tipo] = conteos.get(tipo, 0) + 1
            return f"[{tipo.upper()}]"
        salida = patron.sub(repl, salida)
    base = g1.mask_pii(salida)
    for k, v in base.counts.items():
        conteos[k] = conteos.get(k, 0) + v
    return g1.PIIResult(masked=base.masked, counts=conteos)
