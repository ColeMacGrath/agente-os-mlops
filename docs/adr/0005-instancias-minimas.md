# ADR-0005 · Instancia mínima solo en horario laboral

- **Estado:** aceptada · día 11 de operación
- **Contexto:** revisión FinOps semanal. El 100% de las tareas de los primeros diez días ocurrió en horario laboral, y la instancia mínima 24 h solo generaba costo fuera de él.
- **Decisión:** programar la instancia mínima de 7:00 a 18:00 (11 h) en las dos regiones.
- **Validación:** fuera de horario, el arranque en frío medido (1.3 s en la Actividad 9) no afecta el SLA de 16 s.
- **Resultado medido:** el costo de infraestructura por día baja de $5.78 a $4.00 (−31%).
