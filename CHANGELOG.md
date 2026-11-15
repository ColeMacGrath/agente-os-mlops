# Changelog

## 3.1.1 · Publicación en GitHub
- CI/CD funcionando en GitHub Actions; acciones actualizadas a Node.js 24; nombre de imagen en minúsculas para `ghcr.io`.
- El CI propone la revisión nueva como canary de staging y no se dispara con los merges de GitOps; el CD detecta el entorno que cambió y cierra el ciclo con PR de promoción y de fijación al 100%.
- Análisis de canary con muestra pareada y prueba de Mann-Whitney (ADR-0003, revisión 2). 59 pruebas.
- `.gitattributes`: los CSV sellados con SHA-256 no cambian sus saltos de línea.

## 3.1.0 · Fase III
- Semáforo de riesgo 3.1.0: portugués, traducción completa al inglés, modismos y excepciones de solo lectura. Aplicado en producción.
- Filtro Ciego 3: formatos de seis países con dígito verificador. Aplicado.
- Validador de inyección 3.1.0: clasificador multilingüe con corroboración de reglas. **En sombra** (no pasó la FPR máxima en el ciego F4).
- API: endpoint asíncrono, router de modelos, caché de planes, modo degradado, `/metrics`, `/v1/version` con linaje y bitácora encadenada multiescritor.
- Pipeline DVC de 5 etapas, registro en MLflow, compuertas por componente.
- GitOps: estado deseado por entorno, reconciliador, análisis de canary y rollback automático.
- Operación: reglas de alerta, tablero, informe de auditoría. Router configurable (ADR-0004).

## 3.0.0 · Fase III (rechazada por la compuerta)
- Primera candidata. Ver `docs/bitacora.md`.

## 2.0 · Actividad 9
- Mitigaciones de fairness (semáforo v2, inyección v2, Filtro Ciego v2) y rediseño de arquitectura.

## 1.0 · Fase II
- MVP: app de macOS, backend FastAPI en Docker y despliegue manual en Cloud Run.
