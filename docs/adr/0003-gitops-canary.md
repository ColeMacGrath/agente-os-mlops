# ADR-0003 · GitOps con despliegue progresivo y rollback automático

- **Estado:** aceptada · 2026-11-14
- **Contexto:** en la Fase II el despliegue era un script manual (`deploy.sh`). No había historial de qué versión corría en cada entorno ni un mecanismo de rollback.
- **Decisión:** el estado deseado de cada entorno vive en `deploy/entornos/<entorno>/release.yaml` y solo cambia por pull request. Un reconciliador lo aplica (Cloud Run con credenciales; simulado en local y en CI sin ellas). El análisis de canary avanza 10% → 50% → 100% si se cumplen la tasa de error, el p95 dentro del SLA y frente a la estable, el costo por tarea, la tasa de bloqueo y la muestra mínima. Si algo falla, regresa el 100% a la estable.
- **Consecuencias:** cada cambio de producción tiene autor, revisión y un commit reversible. Evidencia: promoción de r-3-1-0 sin errores y rollback de r-3-1-1 con 28% de errores (`docs/evidencias/registros/06` y `07`).

## Revisión 2 · 2026-11-14 · criterios estadísticos y ciclo completo en GitHub

- **Contexto:** el primer CD real en GitHub falló: el CI dejaba la revisión nueva de staging al 100% y el análisis esperaba siempre una canary. Al corregirlo, una canary con **el mismo código** que la estable se revirtió en 3 de 3 corridas: el proxy reparte tareas distintas a cada revisión y, como el costo y la latencia dependen de la complejidad de la tarea (Haiku, Sonnet u Opus), muestras de 30–150 solicitudes difieren hasta 58% en costo y 43% en p95 por azar.
- **Decisión:**
  1. El CI propone la revisión nueva como **canary al 10%** frente a la estable de staging. Un release con una sola revisión se **verifica** contra el SLA (error, p95, muestra).
  2. En cada paso, además del tráfico repartido (que mide la tasa de error), se envían **las mismas 150 tareas a ambas revisiones**: costo y bloqueo se comparan con esa muestra pareada.
  3. La latencia relativa usa una **prueba de Mann-Whitney** de una cola: la canary es más lenta solo si p < 0.01 **y** su mediana supera a la estable en más de 5%. El p95 sigue limitado por el SLA de 16 s. El costo tolera 5% (caché y tokens varían ~3%).
  4. El PR de promoción deja staging al 100% en Git y propone la canary de producción; cuando producción aprueba, el CD abre el PR que la fija al 100%. El CD detecta qué entorno cambió para exigir la aprobación de `produccion`.
- **Evidencia (local, `gitops/analisis_canary.py`):** 5 de 5 canaries idénticas promovidas (p = 0.13–0.25); canary 30% más lenta revertida (p = 0.000) y 15% más lenta revertida (p = 0.003); revisión con 15% de errores revertida por la tasa de error. Pruebas en `tests/unit/test_gitops.py`.
- **Consecuencia:** la promoción de r-3-1-0 y el rollback de r-3-1-1 registrados antes se evaluaron con los criterios de la revisión 1; ambos resultados se mantienen con los nuevos (r-3-1-0 cuesta 73% menos y es más rápida; r-3-1-1 falla por errores).
