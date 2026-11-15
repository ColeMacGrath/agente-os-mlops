"""Aplica el release de un entorno en Cloud Run (camino real, con credenciales de GCP).

Por cada región: despliega cada revisión del release con su etiqueta y luego fija
el reparto de tráfico. Requiere gcloud autenticado (Workload Identity en CI).
"""

import argparse
import subprocess
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]


def gcloud(*args: str) -> None:
    print("+ gcloud", " ".join(args))
    subprocess.run(["gcloud", *args], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entorno", required=True)
    ap.add_argument("--proyecto", required=True)
    ap.add_argument("--regiones", default="us-central1,us-east1")
    a = ap.parse_args()
    release = yaml.safe_load((RAIZ / "deploy" / "entornos" / a.entorno / "release.yaml").read_text())
    servicio = f"{release['servicio']}-{a.entorno}"
    for region in a.regiones.split(","):
        for rev in release["revisiones"]:
            env = ",".join(f"{k}={v}" for k, v in {"PLANNER_MODE": "claude", "REVISION": rev["nombre"], **(rev.get("entorno") or {})}.items())
            gcloud("run", "deploy", servicio, f"--project={a.proyecto}", f"--region={region}", f"--image={rev['imagen']}",
                   f"--revision-suffix={rev['nombre']}", f"--tag={rev['nombre']}", "--no-traffic", f"--set-env-vars={env}",
                   "--set-secrets=ANTHROPIC_API_KEY=anthropic-api-key:latest,AGENT_TOKEN=agent-token:latest",
                   "--min-instances=1", "--max-instances=20", "--concurrency=80", "--memory=512Mi", "--cpu=1")
        reparto = ",".join(f"{servicio}-{r['nombre']}={r['trafico']}" for r in release["revisiones"] if r["trafico"] > 0)
        gcloud("run", "services", "update-traffic", servicio, f"--project={a.proyecto}", f"--region={region}", f"--to-revisions={reparto}")


if __name__ == "__main__":
    main()
