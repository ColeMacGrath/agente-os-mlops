# ADR-0003 · GitOps con despliegue progresivo y rollback automático

- **Estado:** aceptada · 2026-11-14
- **Contexto:** en la Fase II el despliegue era un script manual (`deploy.sh`). No había historial de qué versión corría en cada entorno ni un mecanismo de rollback.
- **Decisión:** el estado deseado de cada entorno vive en `deploy/entornos/<entorno>/release.yaml` y solo cambia por pull request. Un reconciliador lo aplica (Cloud Run con credenciales; simulado en local y en CI sin ellas). El análisis de canary avanza 10% → 50% → 100% si se cumplen la tasa de error, el p95 dentro del SLA y frente a la estable, el costo por tarea, la tasa de bloqueo y la muestra mínima. Si algo falla, regresa el 100% a la estable.
- **Consecuencias:** cada cambio de producción tiene autor, revisión y un commit reversible. Evidencia: promoción de r-3-1-0 sin errores y rollback de r-3-1-1 con 28% de errores (`docs/evidencias/registros/06` y `07`).
