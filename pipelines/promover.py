"""Promueve la versión candidata a campeona después de un canary exitoso.

Mueve el alias "campeon" en el registro de MLflow y actualiza reports/campeon.json
con las métricas de los componentes que quedaron aplicados (los componentes en
sombra conservan las métricas del campeón anterior).
"""

import json
import sys

from comun import MODELOS, REPORTES, escribir_json
from registrar import configurar


def main() -> int:
    client = configurar()
    release = json.loads((MODELOS / "release.json").read_text())
    ev = json.loads((REPORTES / "evaluacion.json").read_text())
    campeon = json.loads((REPORTES / "campeon.json").read_text())
    for componente, registro in (("riesgo", "agente-os-riesgo"), ("inyeccion", "agente-os-inyeccion")):
        if release[componente] != "aplicar":
            print(f"{registro}: en modo {release[componente]}, no se promueve")
            continue
        v = client.get_model_version_by_alias(registro, "candidato")
        client.set_registered_model_alias(registro, "campeon", v.version)
        campeon[componente] = ev[componente]
        print(f"{registro}: versión {v.version} promovida a campeon")
    if release["pii"] == "aplicar":
        campeon["pii"] = ev["pii"]
    escribir_json(REPORTES / "campeon.json", campeon)
    return 0


if __name__ == "__main__":
    sys.exit(main())
