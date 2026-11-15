"""Evalúa las versiones históricas con el mismo protocolo que la candidata.

- v1: barreras de la Fase II (MVP desplegado en el piloto).
- v2: barreras mitigadas en la Actividad 9 (en producción al iniciar la Fase III).

La v2 se guarda como campeón inicial (reports/campeon.json) para la compuerta
de no regresión. Se ejecuta una sola vez al iniciar la Fase III.
"""

from agente_os.legado import guardrails_f2 as g1
from agente_os.legado import mitigaciones_a9 as m2
from agente_os.legado import riesgo_f2 as tr1
from agente_os.legado.riesgo_reglas_f2 import RiskClassifier
from agente_os.schemas import RiskLevel
from comun import REPORTES, escribir_json
from evaluar import evaluar_version


def semaforo_v1():
    filas = tr1.generate_dataset()
    pipe = tr1.build_pipeline().fit([f[0] for f in filas], [f[1] for f in filas])
    clf = RiskClassifier.__new__(RiskClassifier)
    clf.pipeline, clf.version, clf.metrics = pipe, tr1.MODEL_VERSION, {}
    return lambda t: clf.classify(t, None).level.value


def main() -> None:
    v1 = evaluar_version(semaforo_v1(), lambda t: g1.detect_injection(t).detected, lambda t: g1.mask_pii(t).masked)
    v1["versiones"] = {"riesgo": "risk-tfidf-lr-1.1 (Fase II)", "inyeccion": "reglas-1.0 (Fase II)", "pii": "pii-1.0 (Fase II)"}
    v2 = evaluar_version(lambda t: m2.clasificar_v2(t, None)[0].value, lambda t: m2.detectar_inyeccion_v2(t)[0],
                         lambda t: m2.enmascarar_v2(t).masked)
    v2["versiones"] = {"riesgo": "riesgo-2.0 (Actividad 9)", "inyeccion": "reglas-2.0 (Actividad 9)", "pii": "pii-2.0 (Actividad 9)"}
    escribir_json(REPORTES / "historico_v1.json", v1)
    escribir_json(REPORTES / "historico_v2.json", v2)
    escribir_json(REPORTES / "campeon.json", v2)
    for nombre, r in (("v1", v1), ("v2", v2)):
        for c in ("a9", "ciego_f3", "ciego_f4"):
            print(f"{nombre} [{c}] riesgo recall={r['riesgo'][c]['recall_alto']} DI={r['riesgo'][c]['impacto_dispar']} | "
                  f"iny tpr={r['inyeccion'][c]['tpr']} fpr={r['inyeccion'][c]['fpr']} | pii={r['pii'][c]['recall']}")
    _ = RiskLevel


if __name__ == "__main__":
    main()
