"""Informe de auditoría técnica de la operación.

1. Verifica la integridad de las bitácoras (operación y despliegues) y comprueba
   que una alteración se detecta (prueba sobre una copia).
2. Comprueba invariantes de seguridad sobre todas las decisiones registradas:
   toda acción de riesgo alto pidió Touch ID; ningún bloqueo llamó al modelo;
   cada decisión registra versiones, ruta y modelo de lenguaje (linaje).
3. Reconstruye el linaje desde el registro de MLflow (versiones, alias y compuertas)
   y el historial de compuertas de las iteraciones.

Uso: python operacion/informe_auditoria.py
"""

import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

from agente_os.auditoria.bitacora import verificar  # noqa: E402

BITACORAS = {"operacion": RAIZ / "operacion" / "salida" / "bitacora.jsonl",
             "despliegues": RAIZ / "gitops" / "estado" / "bitacora_despliegues.jsonl"}


def prueba_alteracion(ruta: Path) -> dict:
    with tempfile.TemporaryDirectory() as d:
        copia = Path(d) / "copia.jsonl"
        shutil.copy(ruta, copia)
        lineas = copia.read_text().splitlines()
        k = len(lineas) // 2
        e = json.loads(lineas[k])
        e["datos"]["riesgo"] = "bajo" if e["datos"].get("riesgo") != "bajo" else "alto"  # intento de cambiar una decisión
        e["datos"]["alterado"] = True
        lineas[k] = json.dumps(e, ensure_ascii=False)
        copia.write_text("\n".join(lineas) + "\n")
        r = verificar(copia)
        return {"linea_alterada": k + 1, "detectada": not r["integra"], "rota_en_linea": r["rota_en_linea"]}


def invariantes(ruta: Path) -> dict:
    eventos = [json.loads(x) for x in ruta.read_text().splitlines() if x.strip()]
    analyze = [e["datos"] for e in eventos if e["evento"] == "analyze"]
    alto_sin_bio = sum(1 for d in analyze for a, b in zip(d["acciones"], d["biometria"]) if a in
                       ("payment", "delete_file", "send_message", "modify_record", "run_command") and not b)
    bloqueos_con_costo = sum(1 for d in analyze if d["bloqueado"] and d["costo_usd"] > 0)
    sin_linaje = sum(1 for d in analyze if not d.get("versiones") or "modelo_lenguaje" not in d)
    return {
        "eventos": dict(Counter(e["evento"] for e in eventos)),
        "decisiones": len(analyze),
        "acciones_alto_riesgo": sum(1 for d in analyze for a in d["acciones"] if a in ("payment", "delete_file", "send_message", "modify_record", "run_command")),
        "acciones_alto_riesgo_sin_touch_id": alto_sin_bio,
        "bloqueos": sum(1 for d in analyze if d["bloqueado"]),
        "bloqueos_que_llamaron_al_modelo": bloqueos_con_costo,
        "respuestas_degradadas": sum(1 for d in analyze if d["degradado"]),
        "decisiones_sin_linaje": sin_linaje,
        "contenido_de_usuario_en_bitacora": any(k in json.dumps(analyze[:200], ensure_ascii=False) for k in ('"task"', '"screen_text"')),
        "riesgo": dict(Counter(d["riesgo"] for d in analyze)),
    }


def linaje_mlflow() -> list[dict]:
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
    except ImportError:
        return []
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", f"sqlite:///{RAIZ / 'mlflow.db'}"))
    c = MlflowClient()
    filas = []
    for nombre in ("agente-os-riesgo", "agente-os-inyeccion"):
        rm = c.get_registered_model(nombre)
        alias = {v: k for k, v in (rm.aliases or {}).items()}
        for v in c.search_model_versions(f"name='{nombre}'"):
            filas.append({"modelo": nombre, "version_registro": v.version, "version": v.tags.get("version_semantica"),
                          "modo": v.tags.get("modo"), "compuerta": v.tags.get("compuerta"), "alias": [k for k, val in (rm.aliases or {}).items() if val == v.version],
                          "run_id": v.run_id})
        _ = alias
    return filas


def main() -> None:
    informe = {"bitacoras": {}, "invariantes": invariantes(BITACORAS["operacion"]), "linaje": linaje_mlflow(), "compuertas": []}
    for nombre, ruta in BITACORAS.items():
        informe["bitacoras"][nombre] = {**verificar(ruta), "prueba_alteracion": prueba_alteracion(ruta)}
    for f in sorted((RAIZ / "docs" / "evidencias" / "registros").glob("*compuerta*.json")):
        c = json.loads(f.read_text())
        fallas = [x["chequeo"] for x in c["chequeos"] if not x["ok"]]
        informe["compuertas"].append({"registro": f.name, "versiones": c.get("versiones"), "fallas": len(fallas), "ejemplos": fallas[:3]})
    actual = json.loads((RAIZ / "reports" / "compuerta.json").read_text())
    informe["compuertas"].append({"registro": "reports/compuerta.json (vigente)", "versiones": actual["versiones"],
                                  "componentes": {k: v["modo"] for k, v in actual["componentes"].items()}})
    (RAIZ / "reports" / "auditoria.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False))
    inv = informe["invariantes"]
    md = ["# Informe de auditoría técnica", "",
          "## Integridad de las bitácoras", "", "| Bitácora | Entradas | Íntegra | Alteración de prueba detectada |", "|---|---|---|---|"]
    for n, b in informe["bitacoras"].items():
        md.append(f"| {n} | {b['entradas']} | {'sí' if b['integra'] else 'no'} | {'sí' if b['prueba_alteracion']['detectada'] else 'no'} (línea {b['prueba_alteracion']['rota_en_linea']}) |")
    md += ["", "## Invariantes de seguridad sobre las decisiones registradas", "",
           f"- Decisiones auditadas: {inv['decisiones']:,}",
           f"- Acciones de riesgo alto: {inv['acciones_alto_riesgo']:,}; sin Touch ID: **{inv['acciones_alto_riesgo_sin_touch_id']}**",
           f"- Ejecuciones bloqueadas: {inv['bloqueos']:,}; bloqueos que llamaron al modelo: **{inv['bloqueos_que_llamaron_al_modelo']}**",
           f"- Respuestas en modo degradado: {inv['respuestas_degradadas']:,}",
           f"- Decisiones sin linaje (versiones y modelo): **{inv['decisiones_sin_linaje']}**",
           f"- Contenido de usuario en la bitácora: **{'sí' if inv['contenido_de_usuario_en_bitacora'] else 'no'}**",
           "", "## Linaje de modelos (registro de MLflow)", "", "| Modelo | Versión de registro | Versión | Modo | Compuerta | Alias |", "|---|---|---|---|---|---|"]
    for f in informe["linaje"]:
        md.append(f"| {f['modelo']} | {f['version_registro']} | {f['version']} | {f['modo']} | {f['compuerta']} | {', '.join(f['alias'])} |")
    md += ["", "## Historial de compuertas", ""]
    for c in informe["compuertas"]:
        md.append(f"- `{c['registro']}`: " + (f"{c['fallas']} criterios fallidos (p. ej. {'; '.join(c['ejemplos'])})" if "fallas" in c else f"modos {c['componentes']}"))
    (RAIZ / "reports" / "auditoria.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
