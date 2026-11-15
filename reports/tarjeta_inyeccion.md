# Tarjeta de modelo · agente-os-inyeccion inyeccion-3.1.0

**Propósito.** Detectar instrucciones de inyección de prompt en el texto de pantalla antes de llamar al modelo de lenguaje.
**Modo en producción.** `sombra`
**Uso fuera de alcance.** No debe usarse para evaluar el desempeño de colaboradores (EU AI Act, Anexo III).

## Datos de entrenamiento
- Corpus sintético composicional (5600 filas), SHA-256 `ee3ba9662672c0ff…`
- Idiomas: español neutro, español coloquial mexicano, inglés, portugués y Spanglish; variantes con errores tipográficos u ofuscación.
- Sin datos personales (verificado por la etapa de validación de datos).

## Entrenamiento
- Hiperparámetros: `{'C': 4.0}` · commit `sin-git` · scikit-learn 1.9.1
- Validación interna: `{'accuracy': 1.0, 'f1': 1.0, 'recall': 1.0}`

## Evaluación por conjunto (TPR / FPR de la clase crítica)
| Conjunto | TPR | FPR | Exactitud | Impacto dispar |
|---|---|---|---|---|
| a9 | 1.000 | 0.000 | — | 1.000 |
| ciego_f3 | 0.867 | 0.125 | — | 0.833 |
| ciego_f4 | 0.933 | 0.167 | — | 0.833 |

`ciego_f4` es el conjunto ciego de esta versión; `a9` y `ciego_f3` se usaron para desarrollo.

## Compuerta
Rechazada en: [ciego_f4] inyección · FPR global. Se despliega en modo sombra hasta pasar sus compuertas.

## Limitaciones conocidas
- Corpus sintético: la generalización a textos reales se medirá con los datos etiquetados de la oleada 1 (conjunto F5).
- La heurística de errores tipográficos solo cubre raíces de acciones de alto riesgo.
