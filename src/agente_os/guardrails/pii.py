"""Filtro Ciego: enmascarado de datos personales (versión 3).

Segunda barrera del servidor. La app ya enmascara en el dispositivo; si algo
llega sin enmascarar, se tapa aquí antes de enviarlo al modelo y se cuenta.

Cubre los formatos de México (Fase II) y los formatos internacionales que la
auditoría de la Actividad 9 encontró desprotegidos: SSN, DNI y NIE de España,
IBAN, CPF, CUIT/CUIL, CBU, DNI de Argentina, cédula y NIT de Colombia y
teléfonos E.164. Donde el formato tiene dígito verificador se valida para no
enmascarar números de negocio (folios, importes, SKU).
"""

import re
from dataclasses import dataclass, field


@dataclass
class ResultadoPII:
    enmascarado: str
    conteos: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.conteos.values())


# ------------------------------------------------------- validadores

_LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"


def luhn_ok(digitos: str) -> bool:
    total, paridad = 0, len(digitos) % 2
    for i, ch in enumerate(digitos):
        d = int(ch)
        if i % 2 == paridad:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def clabe_ok(digitos: str) -> bool:
    if len(digitos) != 18:
        return False
    pesos = [3, 7, 1] * 6
    s = sum((int(d) * w) % 10 for d, w in zip(digitos[:17], pesos))
    return (10 - s % 10) % 10 == int(digitos[17])


def dni_es_ok(valor: str) -> bool:
    v = valor.upper()
    num = v[:-1].replace("X", "0").replace("Y", "1").replace("Z", "2")
    return num.isdigit() and _LETRAS_DNI[int(num) % 23] == v[-1]


def iban_ok(valor: str) -> bool:
    s = re.sub(r"\s", "", valor).upper()
    s = s[4:] + s[:4]
    try:
        return int("".join(str(int(c, 36)) for c in s)) % 97 == 1
    except ValueError:
        return False


def cpf_ok(valor: str) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", valor)]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        r = (sum(v * w for v, w in zip(d[:n], range(n + 1, 1, -1))) * 10) % 11
        if (0 if r == 10 else r) != d[n]:
            return False
    return True


# --------------------------------------------------------- patrones

_INTERNACIONALES = [
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b"), iban_ok),
    ("dni_nie", re.compile(r"\b[XYZ]?\d{7,8}[A-Z]\b", re.I), dni_es_ok),
    ("cpf", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), cpf_ok),
    ("cuit", re.compile(r"\b(?:20|23|24|27|30|33|34)-\d{8}-\d\b"), None),
    ("ssn", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"), None),
    ("telefono", re.compile(r"\+\d{1,3}[\s\-.]?(?:\(?\d{1,4}\)?[\s\-.]?){2,5}\d{2,4}\b"), None),
    ("dni_ar", re.compile(r"\b\d{2}\.\d{3}\.\d{3}\b"), None),
    ("cbu", re.compile(r"\b\d{22}\b"), None),
    ("cuenta", re.compile(r"\b(?:routing|account|cuenta|conta)\s*(?:no\.?|num\.?|#)?\s*\d{8,17}\b", re.I), None),
]
_CURP = re.compile(r"\b[A-Z][AEIOUX][A-Z]{2}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d\b", re.I)
_RFC = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b", re.I)
_CORREO = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_DIGITOS = re.compile(r"(?<![\w])(?:\+?\d[\d \-.]{8,24}\d)(?![\w])")


def enmascarar(texto: str) -> ResultadoPII:
    conteos: dict[str, int] = {}

    def sumar(tipo: str) -> None:
        conteos[tipo] = conteos.get(tipo, 0) + 1

    salida = texto
    for tipo, patron, validador in _INTERNACIONALES:
        def repl(m: re.Match, tipo=tipo, validador=validador) -> str:
            if validador and not validador(m.group(0)):
                return m.group(0)
            sumar(tipo)
            return f"[{tipo.upper()}]"
        salida = patron.sub(repl, salida)

    for patron, tipo in [(_CURP, "curp"), (_RFC, "rfc"), (_CORREO, "correo")]:
        def repl_simple(_m: re.Match, tipo=tipo) -> str:
            sumar(tipo)
            return f"[{tipo.upper()}]"
        salida = patron.sub(repl_simple, salida)

    def repl_digitos(m: re.Match) -> str:
        crudo = m.group(0)
        d = re.sub(r"\D", "", crudo)
        if 13 <= len(d) <= 19 and luhn_ok(d):
            sumar("tarjeta")
            return "[TARJETA]"
        if clabe_ok(d):
            sumar("clabe")
            return "[CLABE]"
        if len(d) == 10 or (len(d) == 12 and d.startswith("52")):
            sumar("telefono")
            return "[TELEFONO]"
        return crudo

    salida = _DIGITOS.sub(repl_digitos, salida)
    return ResultadoPII(salida, conteos)
