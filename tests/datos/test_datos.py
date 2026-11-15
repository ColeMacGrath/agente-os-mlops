"""Pruebas de datos: reproducibilidad, contratos y ausencia de fuga hacia evaluación."""

import pandas as pd
import yaml

from agente_os.datos import corpus_inyeccion, corpus_riesgo
from agente_os.evaluacion import DIR_EVAL

RAIZ = DIR_EVAL.parents[1]


def _textos_evaluacion() -> set[str]:
    textos = set()
    for f in DIR_EVAL.glob("*.csv"):
        df = pd.read_csv(f, dtype=str)
        for col in ("texto", "description", "text"):
            if col in df.columns:
                textos |= {t.strip().lower() for t in df[col].dropna()}
    return textos


def test_corpus_reproducible_con_la_misma_semilla():
    assert corpus_riesgo.generar(semilla=1)[:50] == corpus_riesgo.generar(semilla=1)[:50]
    assert corpus_inyeccion.generar(semilla=1, n_por_idioma=50) == corpus_inyeccion.generar(semilla=1, n_por_idioma=50)


def test_corpus_riesgo_cumple_contrato():
    c = yaml.safe_load((RAIZ / "data" / "contratos" / "riesgo.yaml").read_text())
    df = pd.DataFrame(corpus_riesgo.generar())
    assert list(df.columns) == c["columnas"]
    assert set(df.etiqueta) == set(c["etiquetas"])
    assert not df.texto.duplicated().any()
    assert df.etiqueta.value_counts(normalize=True).min() >= c["min_por_etiqueta"]


def test_corpus_sin_fuga_hacia_evaluacion():
    evaluacion = _textos_evaluacion()
    for filas in (corpus_riesgo.generar(), corpus_inyeccion.generar()):
        assert not [f["texto"] for f in filas if f["texto"].strip().lower() in evaluacion]


def test_conjuntos_de_evaluacion_cubren_todos_los_grupos():
    r = pd.read_csv(DIR_EVAL / "riesgo_ciego_f4.csv")
    assert set(r.grupo) == {"es_neutro", "es_mx_coloquial", "ingles", "spanglish", "errores_tipograficos", "portugues"}
    i = pd.read_csv(DIR_EVAL / "inyeccion_ciego_f4.csv")
    assert set(i.grupo) == {"espanol", "ingles", "spanglish", "portugues", "ofuscado"}
    assert i.etiqueta.isin([0, 1]).all()
