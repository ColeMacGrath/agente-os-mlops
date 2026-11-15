# Bitácora de trabajo · Fase III

Registro de decisiones, iteraciones y problemas encontrados durante la construcción. Los registros de consola citados están en `docs/evidencias/registros/`.

## Día 1 · Diseño y datos

- **Punto de partida.** Backend de la Fase II y rediseño de la Actividad 9. Objetivo: llevar la arquitectura propuesta a producción y resolver el pendiente que dejó la auditoría: el detector de inyección no generalizaba al portugués.
- **Conjunto ciego F3.** Se escribió *antes* del código nuevo para evaluar con honestidad. Al revisar el validador de inyección se detectó que algunas reglas nuevas copiaban frases de F3. Se revirtieron a la versión exacta de la Actividad 9: lo nuevo debía venir del clasificador aprendido.
- **Corpus sintéticos.** Semáforo v3: se agregaron portugués y la traducción completa al inglés del léxico. Clasificador de inyección: corpus multilingüe por categorías de ataque, con negativos difíciles.
- **Primera validación de datos: rechazada** (`01_validacion_datos_fallida.json`). Había 210 duplicados en el corpus de riesgo y un desbalance de 82/18 en el de inyección. Se corrigieron los generadores.

## Día 1 · Iteraciones del modelo

| Iteración | Cambio | Resultado de la compuerta |
|---|---|---|
| v3.0a | primer entrenamiento | rechazada: FPR de inyección 0.46 en F3; el semáforo apenas debajo del umbral |
| v3.0 | se corrigió un error en la corrección tipográfica (prefijo de 4 letras); se agregaron negativos difíciles; calibración con la partición dev | rechazada: detección de inyección 0.73 en F3 |
| análisis | en F3, la FPR era **idéntica** con reglas solas y con el ensamble: los falsos positivos venían de las reglas heredadas | — |
| decisión | se planteó una excepción de riesgo; se descartó por relajar una compuerta. Se escribió el ciego **F4** antes de iterar y F3 pasó a ser de desarrollo | — |
| v3.1 | las reglas bloquean solo si el clasificador las corrobora; calibración con A9 + F3; modismo "luz verde" y excepción "pay stubs" | riesgo y PII aprobados; inyección rechazada por FPR 0.167 en F4 → **modo sombra** |

## Día 1 · Despliegue

- DVC sin Git (`dvc init --no-scm`): el usuario inicializa el repositorio. Después de `git init` hay que quitar `no_scm` de `.dvc/config` (ver guía de GitHub).
- Canary de producción aprobado en los tres pasos. La primera prueba de rollback revirtió por *muestra mínima* y no por la tasa de error (25%): se corrigió para evaluar siempre todos los criterios.
- `promover.py` movió el alias `campeon` del semáforo de riesgo; la inyección quedó en `sombra`.

## Día 1 · Operación y auditoría

- Primera simulación: la alerta de costo nunca se disparó, aunque Sonnet pasó de 45% a 64%. La señal correcta era la mezcla del router (`FIN-MEZCLA`), no el costo absoluto.
- El ajuste del router por longitud no cambió la mezcla. **Causa raíz:** el router contaba "conciliado" como verbo. La acción final combina ambas correcciones (ADR-0004) y reduce el costo por tarea 24%.
- **La auditoría encontró un defecto real:** la bitácora quedaba no íntegra (cadena rota en la entrada 801) cuando dos escritores compartían el archivo. Se corrigió con encadenamiento sobre el archivo bajo bloqueo exclusivo y una prueba de regresión.
- La prueba de alteración del informe de auditoría tampoco detectaba un caso porque no cambiaba el valor. Se corrigió.

## Retrospectiva (técnica del velero, Tema 23)

| Elemento | Qué fue |
|---|---|
| Viento (lo que impulsó) | Partir de la Actividad 9: la arquitectura, los conjuntos de evaluación y las métricas ya existían. Las compuertas automáticas detectaron problemas antes de que llegaran a producción. |
| Anclas (lo que frenó) | Los corpus sintéticos generalizan peor que su validación interna (exactitud 1.0 en entrenamiento, FPR 0.46 en ciego). Las reglas heredadas producían los falsos positivos. |
| Rocas (riesgos) | Ajustar reglas o umbrales mirando el conjunto ciego. Se evitó dos veces: revirtiendo reglas y escribiendo F4 antes de iterar. |
| Isla (meta) | Promover el clasificador de inyección con datos reales etiquetados (F5) en la oleada 3. |
| Acciones | 1) Etiquetar F5 con textos de la oleada 1. 2) Rediseñar la capa de reglas (INC-F3-007). 3) Que el Comité de IA decida la política de compuertas relativa al campeón. |

## Cierre · Entregables

- Documento explicativo del pipeline y documento técnico de operación (Word), con las cifras de `reports/` y las capturas de `docs/evidencias/capturas/`.
- Portfolio técnico-estratégico (PowerPoint, 19 diapositivas con notas del presentador) y simulación de entrevista (Word, modo conversacional de Claude).
- Revisión final: `ruff` sin errores, 54 pruebas aprobadas y `dvc status` sin cambios pendientes. Se volvió a capturar `api_openapi.png` con la versión 3.1.0.
