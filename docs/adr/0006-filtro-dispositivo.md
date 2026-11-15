# ADR-0006 · Filtro Ciego v2 también en el dispositivo

- **Estado:** aceptada · día 3 de operación
- **Contexto:** alerta `PRIV-PII` (días 1 y 2 consecutivos). El 0.51% de las solicitudes legítimas trae datos personales sin enmascarar (DNI, SSN, CPF, IBAN). El servidor los tapa con su segunda barrera, pero ya salieron del dispositivo.
- **Decisión:** publicar en la app de macOS los mismos patrones internacionales del Filtro Ciego v3 del servidor.
- **Resultado medido:** la tasa promedio baja de 0.64% (días 1–2) a 0.17% (días 4–30). El residual corresponde a equipos todavía no actualizados; la alerta volvió a dispararse una vez (día 11, al sumarse la oleada 2).
