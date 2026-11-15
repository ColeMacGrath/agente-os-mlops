"""Genera la tarjeta de modelo (model card) de una versión a partir de su evaluación."""


def generar(nombre: str, version: str, manifiesto: dict, evaluacion: dict, compuerta: dict, modo: str) -> str:
    comp = "riesgo" if "riesgo" in nombre else "inyeccion"
    m = manifiesto[comp]
    filas = []
    for c in ("a9", "ciego_f3", "ciego_f4"):
        e = evaluacion[comp].get(c)
        if not e:
            continue
        if comp == "riesgo":
            filas.append(f"| {c} | {e['recall_alto']:.3f} | {e['fpr_alto']:.3f} | {e['exactitud']:.3f} | {e['impacto_dispar']:.3f} |")
        else:
            filas.append(f"| {c} | {e['tpr']:.3f} | {e['fpr']:.3f} | — | {e['impacto_dispar']:.3f} |")
    fallas = compuerta.get("componentes", {}).get(comp, {}).get("fallas", [])
    proposito = ("Clasificar el riesgo (bajo, medio, alto) de cada acción planeada; el nivel alto exige Touch ID."
                 if comp == "riesgo" else
                 "Detectar instrucciones de inyección de prompt en el texto de pantalla antes de llamar al modelo de lenguaje.")
    return f"""# Tarjeta de modelo · {nombre} {version}

**Propósito.** {proposito}
**Modo en producción.** `{modo}`
**Uso fuera de alcance.** No debe usarse para evaluar el desempeño de colaboradores (EU AI Act, Anexo III).

## Datos de entrenamiento
- Corpus sintético composicional ({m['filas']} filas), SHA-256 `{m['datos_sha256'][:16]}…`
- Idiomas: español neutro, español coloquial mexicano, inglés, portugués y Spanglish; variantes con errores tipográficos u ofuscación.
- Sin datos personales (verificado por la etapa de validación de datos).

## Entrenamiento
- Hiperparámetros: `{m['hiperparametros']}` · commit `{manifiesto['git']}` · scikit-learn {manifiesto['sklearn']}
- Validación interna: `{m['metricas_validacion']}`

## Evaluación por conjunto (TPR / FPR de la clase crítica)
| Conjunto | TPR | FPR | Exactitud | Impacto dispar |
|---|---|---|---|---|
{chr(10).join(filas)}

`ciego_f4` es el conjunto ciego de esta versión; `a9` y `ciego_f3` se usaron para desarrollo.

## Compuerta
{"Aprobada en todos los criterios." if not fallas else "Rechazada en: " + "; ".join(fallas) + ". Se despliega en modo sombra hasta pasar sus compuertas."}

## Limitaciones conocidas
- Corpus sintético: la generalización a textos reales se medirá con los datos etiquetados de la oleada 1 (conjunto F5).
- La heurística de errores tipográficos solo cubre raíces de acciones de alto riesgo.
"""
