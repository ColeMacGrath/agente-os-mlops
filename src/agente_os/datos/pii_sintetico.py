"""Generador de datos personales sintéticos por país para evaluar el Filtro Ciego.

Los valores son ficticios pero válidos en formato (dígitos verificadores de
tarjeta, CLABE, DNI, IBAN, CPF y CUIT). Se usó en la Actividad 9 y aquí se
reutiliza con otra semilla y otras plantillas para el conjunto ciego de la Fase III.

Uso: python -m agente_os.datos.pii_sintetico salida.csv
"""

import csv
import random
import sys

# --------------------------------------------------------------- PII


def luhn(base: str) -> str:
    digitos = [int(d) for d in base]
    total = 0
    for i, d in enumerate(reversed(digitos)):
        if i % 2 == 0:
            d *= 2
            d -= 9 if d > 9 else 0
        total += d
    return base + str((10 - total % 10) % 10)


def clabe(base17: str) -> str:
    pesos = [3, 7, 1] * 6
    s = sum((int(d) * w) % 10 for d, w in zip(base17, pesos))
    return base17 + str((10 - s % 10) % 10)


def dni_es(n: int) -> str:
    return f"{n:08d}" + "TRWAGMYFPDXBNJZSQVHLCKE"[n % 23]


def nie_es(n: int) -> str:
    return "X" + f"{n:07d}" + "TRWAGMYFPDXBNJZSQVHLCKE"[n % 23]


def cpf_br(base9: str) -> str:
    d = [int(c) for c in base9]
    for _ in range(2):
        s = sum(v * w for v, w in zip(d, range(len(d) + 1, 1, -1)))
        r = (s * 10) % 11
        d.append(0 if r == 10 else r)
    t = "".join(map(str, d))
    return f"{t[:3]}.{t[3:6]}.{t[6:9]}-{t[9:]}"


def cuit_ar(base10: str) -> str:
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    s = sum(int(a) * b for a, b in zip(base10, pesos))
    v = 11 - s % 11
    v = 0 if v == 11 else 9 if v == 10 else v
    t = base10 + str(v)
    return f"{t[:2]}-{t[2:10]}-{t[10]}"


def iban_es(rng: random.Random) -> str:
    bban = "".join(str(rng.randint(0, 9)) for _ in range(20))
    num = int(bban + "142800")  # E=14, S=28, 00
    chk = 98 - num % 97
    t = f"ES{chk:02d}{bban}"
    return " ".join(t[i:i + 4] for i in range(0, len(t), 4))


def curp(rng: random.Random) -> str:
    L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    v = "AEIOU"
    return (rng.choice(L) + rng.choice(v) + rng.choice(L) + rng.choice(L) + f"{rng.randint(60, 99):02d}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}"
            + rng.choice("HM") + rng.choice(["DF", "NL", "JC", "PL", "QT"]) + rng.choice(L) + rng.choice(L) + rng.choice(L) + "0" + str(rng.randint(0, 9)))


def rfc(rng: random.Random) -> str:
    L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(rng.choice(L) for _ in range(4)) + f"{rng.randint(60, 99):02d}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}" + "".join(rng.choice(L + "0123456789") for _ in range(3))


def tarjeta(rng: random.Random) -> str:
    prefijo = rng.choice(["4", "51", "55"])
    t = luhn(prefijo + "".join(str(rng.randint(0, 9)) for _ in range(15 - len(prefijo))))
    return " ".join(t[i:i + 4] for i in range(0, 16, 4))


def digitos(rng, n):
    return "".join(str(rng.randint(0, 9)) for _ in range(n))


def pii_por_pais(rng: random.Random) -> dict[str, list[tuple[str, str]]]:
    """Devuelve (tipo, valor) por país. Un correo y una tarjeta por país como control."""
    return {
        "MX": [("curp", curp(rng)), ("rfc", rfc(rng)), ("clabe", clabe("0121800" + digitos(rng, 10))),
               ("telefono", f"55 {digitos(rng, 4)} {digitos(rng, 4)}"), ("correo", f"lmendez{rng.randint(1, 99)}@empresa.mx"), ("tarjeta", tarjeta(rng))],
        "US": [("ssn", f"{rng.randint(100, 665)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}"), ("telefono", f"+1 (415) {digitos(rng, 3)}-{digitos(rng, 4)}"),
               ("cuenta", f"Routing {digitos(rng, 9)} Account {digitos(rng, 10)}"), ("correo", f"jsmith{rng.randint(1, 99)}@company.com"), ("tarjeta", tarjeta(rng))],
        "CO": [("cedula", f"{rng.randint(1, 1)}.{digitos(rng, 3)}.{digitos(rng, 3)}.{digitos(rng, 3)}"), ("nit", f"900.{digitos(rng, 3)}.{digitos(rng, 3)}-{rng.randint(0, 9)}"),
               ("telefono", f"+57 3{digitos(rng, 2)} {digitos(rng, 3)} {digitos(rng, 4)}"), ("correo", f"cgomez{rng.randint(1, 99)}@empresa.co"), ("tarjeta", tarjeta(rng))],
        "ES": [("dni", dni_es(rng.randint(10_000_000, 99_999_999))), ("nie", nie_es(rng.randint(1_000_000, 9_999_999))), ("iban", iban_es(rng)),
               ("telefono", f"+34 6{digitos(rng, 2)} {digitos(rng, 3)} {digitos(rng, 3)}"), ("correo", f"mruiz{rng.randint(1, 99)}@empresa.es"), ("tarjeta", tarjeta(rng))],
        "AR": [("dni", f"{rng.randint(20, 45)}.{digitos(rng, 3)}.{digitos(rng, 3)}"), ("cuit", cuit_ar("20" + digitos(rng, 8))), ("cbu", digitos(rng, 22)),
               ("telefono", f"+54 9 11 {digitos(rng, 4)}-{digitos(rng, 4)}"), ("correo", f"plopez{rng.randint(1, 99)}@empresa.com.ar"), ("tarjeta", tarjeta(rng))],
        "BR": [("cpf", cpf_br(digitos(rng, 9))), ("telefono", f"+55 11 9{digitos(rng, 4)}-{digitos(rng, 4)}"),
               ("correo", f"asilva{rng.randint(1, 99)}@empresa.com.br"), ("tarjeta", tarjeta(rng))],
    }



PLANTILLAS_F3 = ["Alta de colaborador: {v}", "Dato fiscal o de contacto {v}", "Confirmar {v} con el titular", "Registro interno ({v})"]


def generar_csv(ruta: str, semilla: int = 3131, repeticiones: int = 5, particion: str = "ciego_f3") -> None:
    rng = random.Random(semilla)
    with open(ruta, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["particion", "pais", "tipo", "valor", "texto"])
        for _ in range(repeticiones):
            for pais, items in pii_por_pais(rng).items():
                for tipo, valor in items:
                    w.writerow([particion, pais, tipo, valor, rng.choice(PLANTILLAS_F3).format(v=valor)])


if __name__ == "__main__":
    generar_csv(sys.argv[1])
