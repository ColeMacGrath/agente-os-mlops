"""Etapa 3: entrena el semáforo de riesgo y el clasificador de inyección.

Guarda los artefactos en models/ junto con un manifiesto de linaje: versión,
hiperparámetros, hash de los datos de entrenamiento y commit de Git.
"""

import pickle
from datetime import UTC, datetime

import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

from agente_os.guardrails.inyeccion import desofuscar
from agente_os.riesgo.modelo import construir_pipeline
from comun import DATOS, MODELOS, escribir_json, git_sha, params, sha256


def entrenar_riesgo(p: dict) -> dict:
    df = pd.read_csv(DATOS / "procesados" / "riesgo.csv")
    # Validación interna: partición por marco de frase (la prueba solo tiene marcos no vistos).
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42).split(df, df.etiqueta, df.marco))
    m = construir_pipeline(C=p["C"]).fit(df.texto.iloc[tr], df.etiqueta.iloc[tr])
    pred = m.predict(df.texto.iloc[te])
    y = df.etiqueta.iloc[te]
    metricas = {"accuracy": round(accuracy_score(y, pred), 4), "f1_macro": round(f1_score(y, pred, average="macro"), 4),
                "recall_alto": round(recall_score(y, pred, labels=["alto"], average="macro"), 4)}
    final = construir_pipeline(C=p["C"]).fit(df.texto, df.etiqueta)
    ruta = MODELOS / "riesgo" / "model.pkl"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "wb") as f:
        pickle.dump({"pipeline": final, "version": p["version"], "metricas": metricas}, f)
    return {"version": p["version"], "metricas_validacion": metricas, "sha256": sha256(ruta), "filas": len(df)}


def entrenar_inyeccion(p: dict) -> dict:
    df = pd.read_csv(DATOS / "procesados" / "inyeccion.csv")
    df["entrada"] = df.texto.map(desofuscar)

    def pipe():
        return Pipeline([
            ("rasgos", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2)),
            ("clf", LogisticRegression(max_iter=3000, C=p["C"], class_weight="balanced", random_state=7)),
        ])

    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=7).split(df, df.etiqueta, df.idioma + df.variante))
    m = pipe().fit(df.entrada.iloc[tr], df.etiqueta.iloc[tr])
    pred = (m.predict_proba(df.entrada.iloc[te])[:, 1] >= p["umbral"]).astype(int)
    y = df.etiqueta.iloc[te]
    metricas = {"accuracy": round(accuracy_score(y, pred), 4), "f1": round(f1_score(y, pred), 4), "recall": round(recall_score(y, pred), 4)}
    final = pipe().fit(df.entrada, df.etiqueta)
    umbral, umbral_humano, umbral_corr, calib = calibrar_umbrales(final, p)
    ruta = MODELOS / "inyeccion" / "model.pkl"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "wb") as f:
        pickle.dump({"pipeline": final, "version": p["version"], "umbral": umbral, "umbral_contexto_humano": umbral_humano,
                     "umbral_corroboracion": umbral_corr, "metricas": metricas, "calibracion": calib}, f)
    return {"version": p["version"], "umbral": umbral, "umbral_contexto_humano": umbral_humano, "umbral_corroboracion": umbral_corr,
            "calibracion": calib,
            "metricas_validacion": metricas, "sha256": sha256(ruta), "filas": len(df)}


def calibrar_umbrales(pipeline, p: dict) -> tuple[float, float, float, dict]:
    """Elige los umbrales con los conjuntos de desarrollo (Actividad 9 completo y ciego F3).

    El conjunto ciego F4 nunca se usa aquí. Criterio: máximo TPR con FPR <= fpr_objetivo;
    a igualdad, menor FPR y umbrales más altos (más conservadores).
    """
    from agente_os.guardrails.inyeccion import DetectorInyeccion, puntaje_reglas

    dev = pd.concat([pd.read_csv(DATOS / "evaluacion" / f) for f in p["conjuntos_calibracion"]])
    det = DetectorInyeccion()
    det.clasificador = pipeline
    probs = det.probabilidad_modelo(dev.texto.tolist())
    reglas = [puntaje_reglas(t)[0] for t in dev.texto]
    humano = [det.contexto_humano(t) for t in dev.texto]
    y = dev.etiqueta.astype(int).tolist()
    mejor = None
    for u in [x / 100 for x in range(40, 96, 5)]:
        for uh in [x / 100 for x in range(50, 100, 5)]:
            if uh < u:
                continue
            for c in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]:
                det.umbral_modelo, det.umbral_contexto_humano, det.umbral_corroboracion = u, uh, c
                pred = [det.decidir(r, pr, h) for r, pr, h in zip(reglas, probs, humano)]
                tp = sum(1 for a, b in zip(y, pred) if a and b)
                fp = sum(1 for a, b in zip(y, pred) if not a and b)
                tpr, fpr = tp / max(sum(y), 1), fp / max(len(y) - sum(y), 1)
                clave = (fpr <= p["fpr_objetivo"], round(tpr, 4), -round(fpr, 4), u, uh, c)
                if mejor is None or clave > mejor[0]:
                    mejor = (clave, u, uh, c, {"tpr_dev": round(tpr, 4), "fpr_dev": round(fpr, 4), "n_dev": len(y),
                                               "conjuntos": p["conjuntos_calibracion"]})
    return mejor[1], mejor[2], mejor[3], mejor[4]


def main() -> None:
    p = params()
    manifiesto_datos = (DATOS / "procesados" / "manifiesto.json").read_text()
    import json
    datos = json.loads(manifiesto_datos)
    r = entrenar_riesgo(p["riesgo"])
    i = entrenar_inyeccion(p["inyeccion"])
    escribir_json(MODELOS / "manifest.json", {
        "entrenado": datetime.now(UTC).isoformat(timespec="seconds"), "git": git_sha(), "sklearn": sklearn.__version__,
        "riesgo": {**r, "datos_sha256": datos["riesgo"]["sha256"], "hiperparametros": {"C": p["riesgo"]["C"]}},
        "inyeccion": {**i, "datos_sha256": datos["inyeccion"]["sha256"], "hiperparametros": {"C": p["inyeccion"]["C"]}},
    })
    print("riesgo", r["metricas_validacion"], "| inyeccion", i["metricas_validacion"])


if __name__ == "__main__":
    main()
