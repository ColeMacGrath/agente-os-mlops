# ADR-0004 · Ajuste del router: participios y umbral de longitud

- **Estado:** aceptada · día 17 de operación
- **Contexto:** alerta `FIN-MEZCLA` en los días 15 y 16. Sonnet pasó de 45% a 64% de las llamadas cuando un área adoptó un flujo de conciliación ("Copia el total conciliado de la cuenta…").
- **Análisis de causa raíz:** dos causas. (1) La expresión de verbos `concilia\w*` contaba el participio "conciliado" como un segundo verbo, por lo que la tarea se clasificaba como media. (2) Las tareas miden ~114 caracteres, por encima del umbral de 70.
- **Decisión:** excluir participios del conteo de verbos (`ROUTER_IGNORE_PARTICIPLES=1`) y subir el umbral de longitud a 120 (`ROUTER_TASK_LEN_MEDIUM=120`). El cambio se aplica por PR al release de producción.
- **Validación:** las barreras no dependen del router; el semáforo de riesgo y Touch ID siguen aplicando a toda acción. La prueba `test_umbral_de_largo_configurable` cubre el comportamiento.
- **Resultado medido** (días 1–16 frente a 18–30): Haiku sube de 28% a 52% de las llamadas, Sonnet baja de 64% a 41%, el costo por tarea baja de $0.0043 a $0.0032 (−24%) y la latencia p95 promedio pasa de 10.5 s a 9.1 s.
