"""Etapa 1: genera los corpus de entrenamiento versionados."""

import pandas as pd

from agente_os.datos import corpus_inyeccion, corpus_riesgo
from comun import DATOS, escribir_json, params, sha256


def main() -> None:
    p = params()["datos"]
    salida = DATOS / "procesados"
    salida.mkdir(parents=True, exist_ok=True)
    riesgo = pd.DataFrame(corpus_riesgo.generar(semilla=p["semilla_riesgo"], proporcion_errores=p["proporcion_errores"]))
    iny = pd.DataFrame(corpus_inyeccion.generar(semilla=p["semilla_inyeccion"], n_por_idioma=p["inyeccion_por_idioma"],
                                                prop_ofuscado=p["inyeccion_prop_ofuscado"]))
    riesgo.to_csv(salida / "riesgo.csv", index=False)
    iny.to_csv(salida / "inyeccion.csv", index=False)
    escribir_json(salida / "manifiesto.json", {
        "riesgo": {"filas": len(riesgo), "sha256": sha256(salida / "riesgo.csv"), "por_idioma": riesgo.idioma.value_counts().to_dict()},
        "inyeccion": {"filas": len(iny), "sha256": sha256(salida / "inyeccion.csv"), "por_idioma": iny.idioma.value_counts().to_dict()},
    })
    print(f"riesgo: {len(riesgo)} filas · inyeccion: {len(iny)} filas")


if __name__ == "__main__":
    main()
