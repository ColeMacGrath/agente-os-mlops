"""Etapa 4: evalúa los modelos candidatos con los conjuntos de evaluación por grupo."""

import pandas as pd

from agente_os import evaluacion as ev
from agente_os.guardrails.inyeccion import DetectorInyeccion
from agente_os.guardrails.pii import enmascarar
from agente_os.riesgo.modelo import SemaforoRiesgo
from comun import DATOS, MODELOS, REPORTES, escribir_json


def evaluar_version(clasificar, detectar, enmascarar_fn) -> dict:
    textos = pd.read_csv(DATOS / "evaluacion" / "riesgo_grupos_a9.csv").texto.tolist()[:60]
    return {
        "riesgo": ev.evaluar_riesgo(clasificar),
        "inyeccion": ev.evaluar_inyeccion(detectar),
        "pii": ev.evaluar_pii(enmascarar_fn),
        "latencia_ms": {"riesgo": ev.latencia_ms(clasificar, textos), "inyeccion": ev.latencia_ms(detectar, textos),
                        "pii": ev.latencia_ms(enmascarar_fn, textos)},
    }


def main() -> None:
    semaforo = SemaforoRiesgo(MODELOS / "riesgo" / "model.pkl")
    detector = DetectorInyeccion(MODELOS / "inyeccion" / "model.pkl")
    r = evaluar_version(lambda t: semaforo.clasificar(t).nivel.value, lambda t: detector.detectar(t).detectado,
                        lambda t: enmascarar(t).enmascarado)
    r["versiones"] = {"riesgo": semaforo.version, "inyeccion": detector.version}
    escribir_json(REPORTES / "evaluacion.json", r)
    # Resumen pequeño para `dvc metrics show` y para comparar ejecuciones.
    resumen = {}
    for c in ("a9", "ciego_f4"):
        resumen[c] = {"riesgo_recall_alto": r["riesgo"][c]["recall_alto"], "riesgo_impacto_dispar": r["riesgo"][c]["impacto_dispar"],
                      "inyeccion_tpr": r["inyeccion"][c]["tpr"], "inyeccion_fpr": r["inyeccion"][c]["fpr"], "pii_recall": r["pii"][c]["recall"]}
    escribir_json(REPORTES / "metricas.json", resumen)
    for c in ("a9", "ciego_a9", "ciego_f3", "ciego_f4"):
        print(f"[{c}] riesgo recall_alto={r['riesgo'][c]['recall_alto']} DI={r['riesgo'][c]['impacto_dispar']} exact={r['riesgo'][c]['exactitud']}"
              f" | inyeccion tpr={r['inyeccion'][c]['tpr']} fpr={r['inyeccion'][c]['fpr']} DI={r['inyeccion'][c]['impacto_dispar']}"
              f" | pii recall={r['pii'][c]['recall']}")


if __name__ == "__main__":
    main()
