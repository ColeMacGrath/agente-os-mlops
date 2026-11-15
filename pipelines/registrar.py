"""Registra la ejecución en MLflow: parámetros, métricas, artefactos y versiones de modelo.

- Por defecto registra la versión candidata actual y la etiqueta con su modo
  (alias "candidato"; la promoción a "campeon" la hace promover.py tras el canary).
- Con --historico registra las iteraciones previas (v1, v2, v3.0) como ejecuciones
  comparables, para tener la historia completa en un solo experimento.
"""

import json
import os
import pickle
import sys

import mlflow
import yaml
from mlflow.tracking import MlflowClient

from agente_os.auditoria.tarjeta_modelo import generar
from comun import MODELOS, RAIZ, REPORTES, git_sha, params

EXPERIMENTO = "agente-os-fase3"


def configurar() -> MlflowClient:
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", f"sqlite:///{RAIZ / 'mlflow.db'}"))
    if mlflow.get_experiment_by_name(EXPERIMENTO) is None:
        mlflow.create_experiment(EXPERIMENTO, artifact_location=(RAIZ / "mlruns").as_uri())
    mlflow.set_experiment(EXPERIMENTO)
    return MlflowClient()


def aplanar(ev: dict) -> dict:
    out = {}
    for comp, clave in (("riesgo", ("recall_alto", "fpr_alto", "exactitud", "impacto_dispar")),
                        ("inyeccion", ("tpr", "fpr", "impacto_dispar")), ("pii", ("recall", "impacto_dispar"))):
        for conj, vals in ev[comp].items():
            if isinstance(vals, dict):
                for k in clave:
                    if k in vals:
                        out[f"{comp}.{conj}.{k}"] = float(vals[k])
    for b, v in ev.get("latencia_ms", {}).items():
        out[f"latencia_p95_ms.{b}"] = float(v["p95"])
    return out


def historico() -> None:
    configurar()
    for nombre, archivo, desc in [("v1-fase2", "historico_v1.json", "Barreras de la Fase II (MVP del piloto)"),
                                  ("v2-actividad9", "historico_v2.json", "Mitigaciones de fairness de la Actividad 9"),
                                  ("v3.0-fase3", "historico_v3_0.json", "Primera candidata de la Fase III (rechazada)")]:
        ev = json.loads((REPORTES / archivo).read_text())
        with mlflow.start_run(run_name=nombre):
            mlflow.set_tags({"iteracion": nombre, "descripcion": desc, "tipo": "historico"})
            mlflow.log_metrics(aplanar(ev))
            mlflow.log_artifact(str(REPORTES / archivo))
        print("registrada", nombre)


def actual() -> None:
    client = configurar()
    p = params()
    ev = json.loads((REPORTES / "evaluacion.json").read_text())
    comp = json.loads((REPORTES / "compuerta.json").read_text())
    man = json.loads((MODELOS / "manifest.json").read_text())
    release = json.loads((MODELOS / "release.json").read_text())
    nombre_run = f"v{p['riesgo']['version'].split('-')[1]}-candidata"
    with mlflow.start_run(run_name=nombre_run) as run:
        mlflow.set_tags({"iteracion": nombre_run, "git": git_sha(), "compuerta_total": str(comp["aprobado"]),
                         "release_seguro": str(comp["release_seguro"]), "tipo": "candidata",
                         **{f"modo.{k}": v for k, v in release.items()}})
        mlflow.log_params({"riesgo.C": p["riesgo"]["C"], "inyeccion.C": p["inyeccion"]["C"],
                           "inyeccion.umbral": man["inyeccion"]["umbral"], "inyeccion.umbral_corroboracion": man["inyeccion"]["umbral_corroboracion"],
                           "inyeccion.umbral_contexto_humano": man["inyeccion"]["umbral_contexto_humano"],
                           "datos.riesgo_sha256": man["riesgo"]["datos_sha256"][:16], "datos.inyeccion_sha256": man["inyeccion"]["datos_sha256"][:16]})
        mlflow.log_metrics(aplanar(ev))
        for f in ("evaluacion.json", "compuerta.json", "validacion_datos.json"):
            mlflow.log_artifact(str(REPORTES / f), "reportes")
        mlflow.log_artifact(str(MODELOS / "manifest.json"), "linaje")
        mlflow.log_dict(yaml.safe_load((RAIZ / "params.yaml").read_text()), "params.yaml")
        for componente, registro in (("riesgo", "agente-os-riesgo"), ("inyeccion", "agente-os-inyeccion")):
            with open(MODELOS / componente / "model.pkl", "rb") as f:
                art = pickle.load(f)
            info = mlflow.sklearn.log_model(art["pipeline"], name=componente, registered_model_name=registro)
            version = info.registered_model_version
            modo = release[componente]
            tarjeta = generar(registro, art["version"], man, ev, comp, modo)
            mlflow.log_text(tarjeta, f"tarjetas/{componente}.md")
            (REPORTES / f"tarjeta_{componente}.md").write_text(tarjeta)
            client.set_registered_model_alias(registro, "candidato" if modo == "aplicar" else "sombra", version)
            client.set_model_version_tag(registro, version, "version_semantica", art["version"])
            client.set_model_version_tag(registro, version, "modo", modo)
            client.set_model_version_tag(registro, version, "compuerta", "aprobada" if comp["componentes"][componente]["aprobado"] else "rechazada")
            print(f"{registro} v{version} ({art['version']}) -> alias {'candidato' if modo == 'aplicar' else 'sombra'}")
        print("run", run.info.run_id)


if __name__ == "__main__":
    historico() if "--historico" in sys.argv else actual()
