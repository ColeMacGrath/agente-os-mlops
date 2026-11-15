"""Evaluación de las tres barreras por grupo (calidad y fairness).

La misma función evalúa cualquier versión (Fase II, Actividad 9 o candidata),
lo que permite comparar iteraciones con exactamente el mismo protocolo.

Métricas por grupo: TPR de la clase crítica (igualdad de oportunidades), FPR,
exactitud de tres clases (riesgo) y razón de impacto dispar = TPR del peor
grupo / TPR del mejor grupo (regla del 80%).
"""

import re
import statistics
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from agente_os.config import RAIZ

DIR_EVAL = RAIZ / "data" / "evaluacion"

CONJUNTOS = {
    "riesgo": {"a9": "riesgo_grupos_a9.csv", "ciego_a9": "riesgo_ciego_a9.csv", "ciego_f3": "riesgo_ciego_f3.csv", "ciego_f4": "riesgo_ciego_f4.csv"},
    "inyeccion": {"a9": "inyeccion_grupos_a9.csv", "ciego_a9": "inyeccion_ciego_a9.csv", "ciego_f3": "inyeccion_ciego_f3.csv", "ciego_f4": "inyeccion_ciego_f4.csv"},
    "pii": {"a9": "pii_grupos_a9.csv", "ciego_a9": "pii_ciego_a9.csv", "ciego_f3": "pii_ciego_f3.csv", "ciego_f4": "pii_ciego_f4.csv"},
}
NEGOCIO_SIN_PII = [
    "Factura A-1021 por $4,320.00 con vencimiento 15/11/2026", "Orden de compra 4471, centro de costos TI-0042",
    "Ventas Norte $1,240,000 +8%", "Cotización COT-2291 por $145,000", "Pedido 2026-11-14 folio 883421",
    "Ticket INC-002 escalado a P2", "Versión 1.0.0 del contenedor agente-os-cloud", "Meta mensual: $5,500,000",
    "Reunión el 20/11/2026 a las 17:00", "SKU 7501234567890 en inventario",
]


def _leer(barrera: str, conjunto: str, dir_eval: Path = DIR_EVAL) -> pd.DataFrame:
    df = pd.read_csv(dir_eval / CONJUNTOS[barrera][conjunto], dtype=str if barrera == "pii" else None)
    df["conjunto"] = conjunto
    return df


def _ratio(serie: pd.Series) -> float:
    return round(float(serie.min() / serie.max()), 4) if len(serie) and serie.max() > 0 else 0.0


def evaluar_riesgo(clasificar: Callable[[str], str], conjuntos=("a9", "ciego_a9", "ciego_f3", "ciego_f4")) -> dict:
    res = {}
    for c in conjuntos:
        df = _leer("riesgo", c)
        df["pred"] = [clasificar(t) for t in df.texto]
        y, p = df.etiqueta == "alto", df.pred == "alto"
        grupos = {}
        for g, sub in df.groupby("grupo"):
            ya, pa = sub.etiqueta == "alto", sub.pred == "alto"
            grupos[g] = {"n": int(len(sub)), "tpr": round(float((pa & ya).sum() / max(ya.sum(), 1)), 4),
                         "fpr": round(float((pa & ~ya).sum() / max((~ya).sum(), 1)), 4),
                         "exactitud": round(float((sub.etiqueta == sub.pred).mean()), 4)}
        tpr = pd.Series({g: v["tpr"] for g, v in grupos.items()})
        fpr = pd.Series({g: v["fpr"] for g, v in grupos.items()})
        res[c] = {"n": int(len(df)), "exactitud": round(float((df.etiqueta == df.pred).mean()), 4),
                  "recall_alto": round(float((p & y).sum() / max(y.sum(), 1)), 4),
                  "fpr_alto": round(float((p & ~y).sum() / max((~y).sum(), 1)), 4),
                  "impacto_dispar": _ratio(tpr), "tpr_min": float(tpr.min()), "fpr_max": float(fpr.max()),
                  "brecha_fpr": round(float(fpr.max() - fpr.min()), 4), "grupos": grupos,
                  "errores": df[df.etiqueta != df.pred][["grupo", "texto", "etiqueta", "pred"]].to_dict("records")}
    return res


def evaluar_inyeccion(detectar: Callable[[str], bool], conjuntos=("a9", "ciego_a9", "ciego_f3", "ciego_f4")) -> dict:
    res = {}
    for c in conjuntos:
        df = _leer("inyeccion", c)
        df["pred"] = [bool(detectar(t)) for t in df.texto]
        atq, ben = df[df.etiqueta == 1], df[df.etiqueta == 0]
        tpr = atq.groupby("grupo").pred.mean().round(4)
        fpr = ben.groupby("grupo").pred.mean().round(4)
        fpr_rol = ben.groupby("rol").pred.mean().round(4)
        res[c] = {"n": int(len(df)), "tpr": round(float(atq.pred.mean()), 4), "fpr": round(float(ben.pred.mean()), 4),
                  "impacto_dispar": _ratio(tpr), "tpr_min": float(tpr.min()), "grupo_peor": str(tpr.idxmin()),
                  "tpr_grupo": tpr.to_dict(), "fpr_grupo": fpr.to_dict(), "fpr_rol": fpr_rol.to_dict(),
                  "errores": df[df.etiqueta.astype(bool) != df.pred][["grupo", "rol", "texto", "etiqueta"]].to_dict("records")}
    return res


def _protegido(valor: str, enmascarado: str) -> bool:
    piezas = [x for x in re.split(r"[\s()]+", valor) if len(re.sub(r"\D", "", x)) >= 3] or [valor]
    return not any(x in enmascarado for x in piezas)


def evaluar_pii(enmascarar: Callable[[str], str], conjuntos=("a9", "ciego_a9", "ciego_f3", "ciego_f4")) -> dict:
    res = {}
    for c in conjuntos:
        df = _leer("pii", c)
        df["ok"] = [_protegido(v, enmascarar(t)) for v, t in zip(df.valor, df.texto)]
        rec = df.groupby("pais").ok.mean().round(4)
        res[c] = {"n": int(len(df)), "recall": round(float(df.ok.mean()), 4), "impacto_dispar": _ratio(rec),
                  "recall_min": float(rec.min()), "recall_pais": rec.to_dict(),
                  "errores": df[~df.ok][["pais", "tipo", "valor"]].to_dict("records")}
    res["falsos_positivos_negocio"] = sum(1 for t in NEGOCIO_SIN_PII if enmascarar(t) != t)
    return res


def latencia_ms(fn: Callable[[str], object], textos: list[str], repeticiones: int = 3) -> dict:
    tiempos = []
    for _ in range(repeticiones):
        for t in textos:
            t0 = time.perf_counter()
            fn(t)
            tiempos.append((time.perf_counter() - t0) * 1000)
    tiempos.sort()
    return {"p50": round(statistics.median(tiempos), 3), "p95": round(tiempos[int(len(tiempos) * 0.95) - 1], 3)}
