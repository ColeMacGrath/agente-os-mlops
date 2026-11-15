"""Actualiza el estado deseado de un entorno (lo usa CI para abrir el pull request GitOps).

- Con --imagen y --revision: nueva revisión como canary (--canary %) frente a la
  estable vigente; si el entorno no tiene estable o se pasa --canary 100, queda al 100%.
- Con --desde y --canary: toma la revisión aprobada de otro entorno (la canary o la
  que está al 100%) y la agrega como canary en este entorno (promoción a producción).
- Con --finalizar: deja al 100% la revisión canary del entorno (después de que el
  análisis de canary la aprobó) y retira la anterior.
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


def estable_de(release: dict) -> dict | None:
    fijas = [r for r in release.get("revisiones", []) if not r.get("canary")]
    return max(fijas, key=lambda r: r["trafico"]) if fijas else None


def aprobada_de(release: dict) -> dict:
    """Revisión que se promueve: la canary si existe; si no, la que está al 100%."""
    revs = release["revisiones"]
    r = next((x for x in revs if x.get("canary")), None) or next(x for x in revs if x["trafico"] == 100)
    return {k: v for k, v in r.items() if k != "canary"}


def con_canary(release: dict, nueva: dict, pct: int) -> list[dict]:
    estable = estable_de(release)
    if estable is not None:   # la configuración del entorno (p. ej. el router del ADR-0004) se conserva al promover
        nueva = dict(nueva, entorno={**(estable.get("entorno") or {}), **(nueva.get("entorno") or {})})
    if estable is None or estable["nombre"] == nueva["nombre"] or pct >= 100:
        return [dict(nueva, trafico=100)]
    return [dict(estable, trafico=100 - pct), dict(nueva, trafico=pct, canary=True)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entorno", required=True)
    ap.add_argument("--imagen")
    ap.add_argument("--revision")
    ap.add_argument("--desde")
    ap.add_argument("--canary", type=int, default=10)
    ap.add_argument("--finalizar", action="store_true")
    a = ap.parse_args()
    release = leer(a.entorno)
    if a.finalizar:
        release["revisiones"] = [dict(aprobada_de(release), trafico=100)]
    elif a.desde:
        release["revisiones"] = con_canary(release, aprobada_de(leer(a.desde)), a.canary)
    else:
        modos = json.loads((RAIZ / "models" / "release.json").read_text())
        man = json.loads((RAIZ / "models" / "manifest.json").read_text())
        nueva = {"nombre": a.revision, "descripcion": "Release generado por CI", "imagen": a.imagen,
                 "modelos": {"riesgo": f"{man['riesgo']['version']} ({modos['riesgo']})",
                             "inyeccion": f"{man['inyeccion']['version']} ({modos['inyeccion']})"},
                 "entorno": {}}
        release["revisiones"] = con_canary(release, nueva, a.canary)
    escribir(a.entorno, release)
    print(yaml.safe_dump(release, allow_unicode=True, sort_keys=False))


if __name__ == "__main__":
    main()
