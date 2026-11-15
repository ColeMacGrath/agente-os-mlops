"""Actualiza el estado deseado de un entorno (lo usa CI para abrir el pull request GitOps).

- Con --imagen y --revision: nueva revisión al 100% (staging).
- Con --desde y --canary: toma la revisión vigente de otro entorno y la agrega
  como canary con el porcentaje indicado (promoción a producción).
"""

import argparse
import json
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
CABECERA = "# Estado deseado del entorno. Fuente de verdad del despliegue (GitOps):\n# solo se modifica mediante pull request y el reconciliador lo aplica.\n"


def leer(entorno: str) -> dict:
    return yaml.safe_load((RAIZ / "deploy" / "entornos" / entorno / "release.yaml").read_text())


def escribir(entorno: str, release: dict) -> None:
    (RAIZ / "deploy" / "entornos" / entorno / "release.yaml").write_text(CABECERA + yaml.safe_dump(release, allow_unicode=True, sort_keys=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entorno", required=True)
    ap.add_argument("--imagen")
    ap.add_argument("--revision")
    ap.add_argument("--desde")
    ap.add_argument("--canary", type=int, default=10)
    a = ap.parse_args()
    release = leer(a.entorno)
    if a.desde:
        nueva = next(r for r in leer(a.desde)["revisiones"] if r["trafico"] == 100)
        estable = next(r for r in release["revisiones"] if r["trafico"] == max(x["trafico"] for x in release["revisiones"]))
        release["revisiones"] = [dict(estable, trafico=100 - a.canary), dict(nueva, trafico=a.canary, canary=True)]
    else:
        modos = json.loads((RAIZ / "models" / "release.json").read_text())
        man = json.loads((RAIZ / "models" / "manifest.json").read_text())
        release["revisiones"] = [{"nombre": a.revision, "descripcion": "Release generado por CI", "imagen": a.imagen,
                                  "modelos": {"riesgo": f"{man['riesgo']['version']} ({modos['riesgo']})",
                                              "inyeccion": f"{man['inyeccion']['version']} ({modos['inyeccion']})"},
                                  "entorno": {}, "trafico": 100}]
    escribir(a.entorno, release)
    print(yaml.safe_dump(release, allow_unicode=True, sort_keys=False))


if __name__ == "__main__":
    main()
