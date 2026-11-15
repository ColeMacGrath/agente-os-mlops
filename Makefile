# Atajos locales. En CI se ejecutan los mismos comandos (ver .github/workflows).
PY ?= python

.PHONY: instalar lint pruebas pipeline registrar promover servir carga operar reconciliar canary auditoria todo

instalar:            ## Dependencias de desarrollo
	$(PY) -m pip install -r requirements-dev.txt

lint:                ## Estilo y errores comunes
	ruff check src pipelines tests

pruebas:             ## Pruebas unitarias, de datos, de modelo y de API
	$(PY) -m pytest -q

pipeline:            ## Datos -> validación -> entrenamiento -> evaluación -> compuerta (DVC)
	dvc repro

registrar:           ## Registro de la candidata en MLflow
	$(PY) pipelines/registrar.py

promover:            ## Mueve el alias "campeon" tras un canary exitoso
	$(PY) pipelines/promover.py

servir:              ## API local en el puerto 8000
	PYTHONPATH=src uvicorn agente_os.api.app:app --port 8000

reconciliar:         ## GitOps local: aplica el estado deseado de deploy/entornos/$(ENV)
	$(PY) gitops/reconciliador.py --entorno $(or $(ENV),staging)

canary:              ## Análisis del canary y decisión promover/revertir
	$(PY) gitops/analisis_canary.py --entorno $(or $(ENV),produccion)

operar:              ## Simulación de 30 días de operación con monitoreo y alertas
	$(PY) operacion/simular_operacion.py

auditoria:           ## Verifica la bitácora y genera el informe de auditoría
	$(PY) operacion/informe_auditoria.py

todo: lint pruebas pipeline registrar
