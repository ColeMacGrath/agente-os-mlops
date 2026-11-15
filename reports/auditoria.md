# Informe de auditoría técnica

## Integridad de las bitácoras

| Bitácora | Entradas | Íntegra | Alteración de prueba detectada |
|---|---|---|---|
| operacion | 12029 | sí | sí (línea 6015) |
| despliegues | 12 | sí | sí (línea 7) |

## Invariantes de seguridad sobre las decisiones registradas

- Decisiones auditadas: 12,000
- Acciones de riesgo alto: 1,060; sin Touch ID: **0**
- Ejecuciones bloqueadas: 205; bloqueos que llamaron al modelo: **0**
- Respuestas en modo degradado: 11
- Decisiones sin linaje (versiones y modelo): **0**
- Contenido de usuario en la bitácora: **no**

## Linaje de modelos (registro de MLflow)

| Modelo | Versión de registro | Versión | Modo | Compuerta | Alias |
|---|---|---|---|---|---|
| agente-os-riesgo | 1 | riesgo-3.1.0 | aplicar | aprobada | campeon, candidato |
| agente-os-inyeccion | 1 | inyeccion-3.1.0 | sombra | rechazada | sombra |

## Historial de compuertas

- `02_compuerta_rechazada_v3a.json`: 4 criterios fallidos (p. ej. [a9] inyección · FPR global; [ciego_f3] riesgo · recall de riesgo alto; [ciego_f3] riesgo · FPR máximo por grupo)
- `03_compuerta_rechazada_v3_0.json`: 2 criterios fallidos (p. ej. [ciego_f3] inyección · TPR global; [ciego_f3] inyección · FPR global)
- `04_compuerta_v3_1_inyeccion_rechazada.json`: 1 criterios fallidos (p. ej. [ciego_f4] inyección · FPR global)
- `reports/compuerta.json (vigente)`: modos {'riesgo': 'aplicar', 'inyeccion': 'sombra', 'pii': 'aplicar'}
