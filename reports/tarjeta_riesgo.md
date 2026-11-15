# Tarjeta de modelo · agente-os-riesgo riesgo-3.1.0

**Propósito.** Clasificar el riesgo (bajo, medio, alto) de cada acción planeada; el nivel alto exige Touch ID.
**Modo en producción.** `aplicar`
**Uso fuera de alcance.** No debe usarse para evaluar el desempeño de colaboradores (EU AI Act, Anexo III).

## Datos de entrenamiento
- Corpus sintético composicional (2543 filas), SHA-256 `6c0c5432c656afb1…`
- Idiomas: español neutro, español coloquial mexicano, inglés, portugués y Spanglish; variantes con errores tipográficos u ofuscación.
- Sin datos personales (verificado por la etapa de validación de datos).

## Entrenamiento
- Hiperparámetros: `{'C': 10.0}` · commit `sin-git` · scikit-learn 1.9.1
- Validación interna: `{'accuracy': 0.9969, 'f1_macro': 0.9969, 'recall_alto': 1.0}`

## Evaluación por conjunto (TPR / FPR de la clase crítica)
| Conjunto | TPR | FPR | Exactitud | Impacto dispar |
|---|---|---|---|---|
| a9 | 1.000 | 0.011 | 0.987 | 1.000 |
| ciego_f3 | 0.972 | 0.000 | 0.978 | 0.833 |
| ciego_f4 | 0.972 | 0.111 | 0.917 | 0.833 |

`ciego_f4` es el conjunto ciego de esta versión; `a9` y `ciego_f3` se usaron para desarrollo.

## Compuerta
Aprobada en todos los criterios.

## Limitaciones conocidas
- Corpus sintético: la generalización a textos reales se medirá con los datos etiquetados de la oleada 1 (conjunto F5).
- La heurística de errores tipográficos solo cubre raíces de acciones de alto riesgo.
