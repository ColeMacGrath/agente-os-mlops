# ADR-0001 · DVC para el pipeline y MLflow para el registro de modelos

- **Estado:** aceptada · 2026-11-14
- **Contexto:** la Fase II entrenaba el modelo dentro del Dockerfile. No había historial de versiones, ni hash de los datos, ni forma de comparar iteraciones.
- **Decisión:** el pipeline se define en `dvc.yaml` (preparar → validar → entrenar → evaluar → compuerta). `dvc.lock` guarda el hash de cada dato, modelo y reporte. MLflow registra parámetros, métricas por grupo, reportes y versiones de modelo con alias (`candidato`, `campeon`, `sombra`).
- **Alternativas:** Kubeflow Pipelines o Vertex AI Pipelines. Se descartaron por el tamaño del equipo y porque requieren infraestructura dedicada; el diseño se puede migrar a ellas sin cambiar las etapas.
- **Consecuencias:** `dvc repro` solo vuelve a ejecutar lo que cambió, y cualquier versión se puede reconstruir desde Git. La imagen ya no entrena: empaqueta modelos aprobados.
