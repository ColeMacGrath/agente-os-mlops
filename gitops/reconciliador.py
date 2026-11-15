"""Reconciliador GitOps local (emula Argo CD / Config Sync sobre Cloud Run).

Compara el estado deseado (deploy/entornos/<entorno>/release.yaml) con el estado
real (procesos en ejecución registrados en gitops/estado/<entorno>.json) y aplica
la diferencia: levanta revisiones nuevas, detiene las que ya no existen y ajusta
los pesos del proxy. Cada acción queda en la bitácora de auditoría.

Uso: python gitops/reconciliador.py --entorno staging [--detener]
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml

RAIZ = Path(__file__).resolve().parents[1]
ESTADO = RAIZ / "gitops" / "estado"
sys.path.insert(0, str(RAIZ / "src"))

from agente_os.auditoria.bitacora import Bitacora  # noqa: E402

PUERTOS = {"staging": 8300, "produccion": 8400}


def deseado(entorno: str) -> dict:
    return yaml.safe_load((RAIZ / "deploy" / "entornos" / entorno / "release.yaml").read_text())


def actual(entorno: str) -> dict:
    ruta = ESTADO / f"{entorno}.json"
    return json.loads(ruta.read_text()) if ruta.exists() else {"revisiones": {}, "proxy": None}


def _vivo(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _esperar(url: str, segundos: float = 20) -> None:
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            if httpx.get(url, timeout=0.5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"no respondió {url}")


def reconciliar(entorno: str, factor_tiempo: float = 0.05, bitacora: Bitacora | None = None) -> list[str]:
    ESTADO.mkdir(parents=True, exist_ok=True)
    bitacora = bitacora or Bitacora(ESTADO / "bitacora_despliegues.jsonl")
    d, a = deseado(entorno), actual(entorno)
    acciones = []
    base = PUERTOS[entorno]
    nombres = [r["nombre"] for r in d["revisiones"]]
    for nombre, info in list(a["revisiones"].items()):
        if nombre not in nombres or not _vivo(info["pid"]):
            if _vivo(info["pid"]):
                os.kill(info["pid"], signal.SIGTERM)
            del a["revisiones"][nombre]
            acciones.append(f"detener revisión {nombre}")
    for i, rev in enumerate(d["revisiones"]):
        if rev["nombre"] in a["revisiones"]:
            continue
        puerto = base + 1 + i + 10 * len(a["revisiones"])
        env = {**os.environ, "PYTHONPATH": str(RAIZ / "src"), "MODEL_DIR": str(RAIZ / "models"), "REVISION": rev["nombre"],
               "PLANNER_MODE": "simulado", "SIM_TIME_FACTOR": str(factor_tiempo), "PYTHONDONTWRITEBYTECODE": "1",
               "LEDGER_PATH": str(ESTADO / f"bitacora_{entorno}_{rev['nombre']}.jsonl"),
               **{k: str(v) for k, v in (rev.get("entorno") or {}).items()}}
        p = subprocess.Popen([sys.executable, "-m", "uvicorn", "agente_os.api.app:app", "--port", str(puerto), "--log-level", "warning"],
                             cwd=RAIZ, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _esperar(f"http://127.0.0.1:{puerto}/health")
        a["revisiones"][rev["nombre"]] = {"pid": p.pid, "url": f"http://127.0.0.1:{puerto}"}
        acciones.append(f"levantar revisión {rev['nombre']} en :{puerto}")
    rutas = {r["nombre"]: {"url": a["revisiones"][r["nombre"]]["url"], "peso": r["trafico"]} for r in d["revisiones"]}
    (ESTADO / f"{entorno}_rutas.json").write_text(json.dumps(rutas, indent=2))
    if not _vivo((a.get("proxy") or {}).get("pid")):
        env = {**os.environ, "GITOPS_RUTAS": str(ESTADO / f"{entorno}_rutas.json"), "PYTHONDONTWRITEBYTECODE": "1"}
        p = subprocess.Popen([sys.executable, "-m", "uvicorn", "proxy:app", "--port", str(base), "--log-level", "warning"],
                             cwd=RAIZ / "gitops", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _esperar(f"http://127.0.0.1:{base}/health")
        a["proxy"] = {"pid": p.pid, "url": f"http://127.0.0.1:{base}"}
        acciones.append(f"levantar proxy en :{base}")
    pesos = ", ".join(f"{n}={v['peso']}%" for n, v in rutas.items())
    acciones.append(f"tráfico: {pesos}")
    (ESTADO / f"{entorno}.json").write_text(json.dumps(a, indent=2))
    bitacora.registrar("reconciliacion", {"entorno": entorno, "acciones": acciones})
    for x in acciones:
        print(f"[reconciliador:{entorno}] {x}")
    return acciones


def detener(entorno: str) -> None:
    a = actual(entorno)
    for info in [*a["revisiones"].values(), a.get("proxy") or {}]:
        if _vivo(info.get("pid")):
            os.kill(info["pid"], signal.SIGTERM)
    (ESTADO / f"{entorno}.json").unlink(missing_ok=True)
    print(f"[reconciliador:{entorno}] entorno detenido")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--entorno", default="staging", choices=list(PUERTOS))
    ap.add_argument("--detener", action="store_true")
    args = ap.parse_args()
    detener(args.entorno) if args.detener else reconciliar(args.entorno)
