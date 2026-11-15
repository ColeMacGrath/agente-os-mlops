"""Etapa 5: compuerta de calidad, equidad y no regresión.

Compara la evaluación con los umbrales de params.yaml y con las métricas del
modelo campeón (reports/campeon.json, si existe). Termina con código 1 si
alguna condición de un componente que se aplicaría en producción falla.

La decisión es por componente (riesgo, inyección, PII): un componente se aplica
solo si pasa todas sus compuertas; si no, se despliega en modo sombra (si tiene
clasificador) o se mantiene el campeón. Los umbrales nunca se relajan.
"""

import json
import sys

from comun import MODELOS, REPORTES, escribir_json, params


def main() -> int:
    g = params()["compuertas"]
    ev = json.loads((REPORTES / "evaluacion.json").read_text())
    campeon_ruta = REPORTES / "campeon.json"
    campeon = json.loads(campeon_ruta.read_text()) if campeon_ruta.exists() else None
    checks = []

    def chk(nombre, valor, op, umbral):
        ok = valor >= umbral if op == ">=" else valor <= umbral
        comp = "riesgo" if "riesgo" in nombre else ("inyeccion" if "inyecc" in nombre else "pii")
        checks.append({"chequeo": nombre, "componente": comp, "valor": valor, "condicion": f"{op} {umbral}", "ok": bool(ok)})

    for c in g["absolutas"]:
        r, i, p = ev["riesgo"][c], ev["inyeccion"][c], ev["pii"][c]
        chk(f"[{c}] riesgo · recall de riesgo alto", r["recall_alto"], ">=", g["riesgo_recall_alto_min"])
        chk(f"[{c}] riesgo · impacto dispar", r["impacto_dispar"], ">=", g["riesgo_impacto_dispar_min"])
        chk(f"[{c}] riesgo · FPR máximo por grupo", r["fpr_max"], "<=", g["riesgo_fpr_alto_max"])
        chk(f"[{c}] riesgo · exactitud 3 clases", r["exactitud"], ">=", g["riesgo_exactitud_min"])
        chk(f"[{c}] inyección · TPR global", i["tpr"], ">=", g["inyeccion_tpr_min"])
        chk(f"[{c}] inyección · FPR global", i["fpr"], "<=", g["inyeccion_fpr_max"])
        chk(f"[{c}] inyección · impacto dispar", i["impacto_dispar"], ">=", g["inyeccion_impacto_dispar_min"])
        chk(f"[{c}] PII · recall", p["recall"], ">=", g["pii_recall_min"])
        chk(f"[{c}] PII · impacto dispar", p["impacto_dispar"], ">=", g["pii_impacto_dispar_min"])
    chk("PII · falsos positivos en textos de negocio", ev["pii"]["falsos_positivos_negocio"], "<=", g["pii_falsos_positivos_max"])
    for b in ("riesgo", "inyeccion", "pii"):
        chk(f"latencia p95 · {b} (ms)", ev["latencia_ms"][b]["p95"], "<=", g["latencia_p95_ms_max"])
    if campeon:
        tol = g["tolerancia_regresion"]
        for c in g["absolutas"]:
            chk(f"[{c}] no regresión · recall riesgo alto", ev["riesgo"][c]["recall_alto"], ">=", round(campeon["riesgo"][c]["recall_alto"] - tol, 4))
            chk(f"[{c}] no regresión · TPR inyección", ev["inyeccion"][c]["tpr"], ">=", round(campeon["inyeccion"][c]["tpr"] - tol, 4))
            chk(f"[{c}] no regresión · recall PII", ev["pii"][c]["recall"], ">=", round(campeon["pii"][c]["recall"] - tol, 4))
    # Decisión por componente: un componente se aplica en producción solo si pasa TODAS sus compuertas.
    # Un componente rechazado nunca se aplica: si tiene clasificador, se despliega en modo sombra y
    # la decisión de producción sigue en manos del campeón. Los umbrales no se modifican.
    componentes = {}
    for comp in ("riesgo", "inyeccion", "pii"):
        propios = [x for x in checks if x["componente"] == comp]
        aprobado = all(x["ok"] for x in propios)
        componentes[comp] = {"aprobado": aprobado, "fallas": [x["chequeo"] for x in propios if not x["ok"]],
                             "modo": "aplicar" if aprobado else ("sombra" if comp == "inyeccion" else "retener_campeon")}
    aprobado_total = all(c["aprobado"] for c in componentes.values())
    release_seguro = all(c["aprobado"] or c["modo"] in ("sombra", "retener_campeon") for c in componentes.values())
    escribir_json(REPORTES / "compuerta.json", {"aprobado": aprobado_total, "release_seguro": release_seguro, "versiones": ev["versiones"],
                                                 "con_campeon": bool(campeon), "componentes": componentes, "chequeos": checks})
    escribir_json(MODELOS / "release.json", {comp: c["modo"] for comp, c in componentes.items()})
    for x in checks:
        print(("OK   " if x["ok"] else "FALLA") + f" {x['chequeo']}: {x['valor']} ({x['condicion']})")
    for comp, c in componentes.items():
        print(f"COMPONENTE {comp}: {'APROBADO' if c['aprobado'] else 'RECHAZADO'} -> modo {c['modo']}")
    print("COMPUERTA: TODOS LOS COMPONENTES APROBADOS" if aprobado_total else
          "COMPUERTA: RELEASE PARCIAL (componentes rechazados en sombra o con el campeón)")
    return 0 if release_seguro else 1


if __name__ == "__main__":
    sys.exit(main())
