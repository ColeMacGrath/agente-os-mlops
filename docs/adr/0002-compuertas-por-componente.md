# ADR-0002 · Compuertas por componente y modo sombra

- **Estado:** aceptada · 2026-11-14
- **Contexto:** la candidata v3.1 pasó todas las compuertas en riesgo y PII, pero el clasificador de inyección no cumplió la FPR máxima en el conjunto ciego F4 (0.167 contra 0.10). Aun así mejora al campeón en detección (0.93 contra 0.53) y en falsos positivos (0.17 contra 0.25).
- **Decisión:** la compuerta decide por componente. Un componente se aplica en producción solo si pasa **todas** sus compuertas. Si no, se despliega en modo sombra (si tiene clasificador) o se mantiene el campeón. Los umbrales no se relajan.
- **Alternativa descartada:** aprobar una excepción formal de riesgo para promover el clasificador. Se consideró y se descartó: relajar una compuerta para un modelo que la reprobó debilita el control.
- **Consecuencias:** el release r-3-1-0 aplica riesgo v3.1 y PII v3, y deja la inyección v3.1 en sombra. La métrica `agente_inyeccion_sombra_total` mide en producción la concordancia con el campeón. La promoción requiere pasar las compuertas en un conjunto nuevo (F5) con textos reales etiquetados.
- **Pendiente para el Comité de IA:** la compuerta absoluta impide promover un modelo que es estrictamente mejor que el campeón. El Comité debe decidir si la política debe ser relativa al campeón en componentes cuyo campeón tampoco cumple el umbral.
