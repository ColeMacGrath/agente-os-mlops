# Historial de commits del repositorio de despliegue (GitOps)

Cada línea corresponde a un cambio del estado deseado en `deploy/entornos/`, hecho por el análisis de canary o por un pull request.

- `2026-11-14 20:20:21 UTC` **deploy/produccion**: avanzar canary r-3-1-0 al 50%
- `2026-11-14 20:20:28 UTC` **deploy/produccion**: avanzar canary r-3-1-0 al 100%
- `2026-11-14 20:20:31 UTC` **deploy/produccion**: promover r-3-1-0 al 100% y retirar r-2-0 (canary aprobado en todos los pasos)
- `2026-11-14 20:20:31 UTC` **deploy/staging**: desplegar canary r-3-1-1-defectuosa al 10% (prueba de rollback)
- `2026-11-14 20:20:38 UTC` **deploy/staging**: rollback: r-3-1-1-defectuosa no cumplió el análisis al 10% (tasa de error)
- `2026-11-14 20:28:27 UTC` **deploy/produccion**: configurar router: excluir participios y umbral de longitud 120 (ADR-0004, alerta FIN-MEZCLA)
