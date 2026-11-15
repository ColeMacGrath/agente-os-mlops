"""Etapa 2: pruebas de datos (contratos, fuga hacia evaluación y ausencia de PII).

Si alguna verificación falla, termina con código 1 y el pipeline se detiene.
"""

import sys

import pandas as pd
import yaml

from agente_os.guardrails.pii import enmascarar
from comun import DATOS, REPORTES, escribir_json


def validar(nombre: str, df: pd.DataFrame, contrato: dict) -> list[dict]:
    r = []

    def chequeo(desc, ok, detalle=""):
        r.append({"corpus": nombre, "chequeo": desc, "ok": bool(ok), "detalle": str(detalle)})

    chequeo("columnas del contrato", list(df.columns) == contrato["columnas"], list(df.columns))
    chequeo("sin nulos", not df.isna().any().any(), int(df.isna().sum().sum()))
    chequeo("sin duplicados exactos", not df.texto.duplicated().any(), int(df.texto.duplicated().sum()))
    chequeo(f"mínimo {contrato['min_filas']} filas", len(df) >= contrato["min_filas"], len(df))
    etiquetas = {str(x) for x in df.etiqueta.unique()}
    chequeo("etiquetas válidas", etiquetas <= {str(x) for x in contrato["etiquetas"]}, sorted(etiquetas))
    prop = df.etiqueta.astype(str).value_counts(normalize=True)
    chequeo("balance de etiquetas", prop.min() >= contrato["min_por_etiqueta"] and prop.max() <= contrato["max_por_etiqueta"],
            prop.round(3).to_dict())
    base = df.idioma.str.replace("_errores", "", regex=False)
    conteo = base.value_counts()
    faltan = [i for i in contrato["idiomas_minimos"] if conteo.get(i, 0) < contrato["min_por_idioma"]]
    chequeo("cobertura mínima por idioma", not faltan, conteo.to_dict() if not faltan else f"faltan: {faltan}")
    largos = df.texto.str.len()
    lo, hi = contrato["largo_texto"]
    chequeo("largo de texto en rango", largos.between(lo, hi).all(), f"min {largos.min()}, max {largos.max()}")
    return r


def main() -> int:
    resultados = []
    eval_textos = set()
    for f in (DATOS / "evaluacion").glob("*.csv"):
        e = pd.read_csv(f, dtype=str)
        for col in ("texto", "description", "text"):
            if col in e.columns:
                eval_textos |= {t.strip().lower() for t in e[col].dropna()}
    for nombre in ("riesgo", "inyeccion"):
        df = pd.read_csv(DATOS / "procesados" / f"{nombre}.csv")
        contrato = yaml.safe_load((DATOS / "contratos" / f"{nombre}.yaml").read_text())
        resultados += validar(nombre, df, contrato)
        fuga = [t for t in df.texto if t.strip().lower() in eval_textos]
        resultados.append({"corpus": nombre, "chequeo": "sin fuga hacia los conjuntos de evaluación", "ok": not fuga,
                           "detalle": fuga[:5] if fuga else "0 textos compartidos"})
        if nombre == "riesgo":
            con_pii = [t for t in df.texto if enmascarar(t).total]
            resultados.append({"corpus": nombre, "chequeo": "corpus sin datos personales", "ok": not con_pii, "detalle": con_pii[:3] or "0"})
    ok = all(x["ok"] for x in resultados)
    escribir_json(REPORTES / "validacion_datos.json", {"aprobado": ok, "chequeos": resultados})
    for x in resultados:
        print(("OK   " if x["ok"] else "FALLA") + f" [{x['corpus']}] {x['chequeo']}: {x['detalle']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
