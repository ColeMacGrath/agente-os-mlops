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
- Revisión final (antes de publicar): `ruff` sin errores, 54 pruebas aprobadas y `dvc status` sin cambios pendientes. Se volvió a capturar `api_openapi.png` con la versión 3.1.0.

## Publicación en GitHub (ColeMacGrath/agente-os-mlops)

- Antes del primer push: el nombre de la imagen se calcula en minúsculas (`ghcr.io` rechaza `ColeMacGrath`) y `.gitattributes` evita que Git convierta los saltos de línea de los CSV: la conversión habría roto el sello SHA-256 del conjunto ciego F4.
- **CI #1** en verde en 3 min 58 s (lint y pruebas 85 s, DVC y compuertas 74 s, imagen y prueba de humo 59 s, PR GitOps 12 s). Mostró 4 advertencias de Node.js 20: se actualizaron las acciones (checkout v5, setup-python v6, upload-artifact v6, download-artifact v7, github-script v8, create-pull-request v8) y el CI #3 quedó sin advertencias.
- Los PR de GitOps que abre el bot sí corren el CI (con aprobación del maintainer la primera vez): el PR #2 se fusionó con los 3 checks obligatorios en verde, sin saltar la protección de `main`.
- **Primer CD real: falló.** El CI dejaba la revisión nueva de staging al 100% y el análisis esperaba una canary. Además, cada merge de GitOps volvía a disparar el CI (otro PR de staging) y el CD por push siempre usaba `staging`. Correcciones: el CI ignora `deploy/entornos/**`, propone la revisión como canary; el CD detecta el entorno que cambió.
- Al probar la corrección, una canary con el mismo código se revirtió 3 de 3 veces por diferencias de costo y latencia entre muestras distintas. Se pasó a una muestra pareada y a la prueba de Mann-Whitney (ADR-0003, revisión 2): 5 de 5 canaries idénticas promovidas, canaries 15% y 30% más lentas revertidas. Se agregaron 5 pruebas (59 en total).
- Al revisar el PR #5 se vio que la canary de producción llegaba sin la configuración del router del ADR-0004. El análisis la habría promovido (la muestra pareada casi no tiene tareas de conciliación) y se habría perdido la optimización de −24%. Corrección: al promover, la revisión hereda la configuración del entorno de la estable; se agregó una prueba (60 en total) y se corrigió el PR #5 antes del merge.
- **Ciclo completo en GitHub:** PR #4 (canary en staging, checks en verde) → CD staging aprobado en 10/50/100% → PR #5 (staging al 100% y canary al 10% en producción) → CD producción **aprobado manualmente en el entorno `produccion`** → PR #6 (producción fija al 100%) → CD de verificación. El monitoreo semanal abrió el issue #7 por el validador de inyección en sombra. Paquete `ghcr.io/colemacgrath/agente-os-cloud` con 4 versiones. Capturas en `docs/evidencias/capturas/github_*.png`.
